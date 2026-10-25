"""paper_validate: verdict accounting, regime-dispatched placement, and the
bounded three-round search loop that never lets a half-cited block reach
disk (`no-claim-without-a-source-that-holds-it`, `citation-validation` and
`citation-placement` specs).

Public surface:

    HOLDS, MAX_ROUNDS, DEFAULT_MIN_SOURCES_PER_CLAIM
    distinct_sources_by_claim(records)        -> dict[str, set[str]]
    claim_coverage(claims, records, *, min_sources=DEFAULT_MIN_SOURCES_PER_CLAIM) -> list[dict]
    satisfied_claims(records, *, min_sources=DEFAULT_MIN_SOURCES_PER_CLAIM) -> set[str]
    finalize_block(paper_dir, block_id, claims, records, new_body=None, *,
                   min_sources=DEFAULT_MIN_SOURCES_PER_CLAIM) -> dict  (raises EVIDENCE_EXHAUSTED)
    Citation, Sentence
    validate_placement(regime, sentence)       -> dict   (raises placement codes)
    read_citations_regime(section_path, block_id) -> str  (raises CONTRACT_HEADER_ABSENT)

`the-pdf-arrives-or-the-operator-is-told`, item 2 ("Coverage counted per
claim, not per folder"): a claim's `holds` record COUNT was never proof of
independent support -- one paper quoted twice satisfied it exactly as well
as two different papers did. `distinct_sources_by_claim`/`claim_coverage`
count DISTINCT `source_md` values among `holds` records only (`does-not-
hold`/`insufficient` still contribute nothing, per `HOLDS` below,
unchanged); `finalize_block` gates on that count against `min_sources`
rather than bare membership, and reports it as `coverage` in every branch
it returns -- the DATA an operator-facing report renders per claim
(required vs. satisfied), never something this module composes into prose
itself.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_block  # noqa: E402
import paper_contract  # noqa: E402
import paper_vocabulary  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: `citation-validation`, Requirement: Three Verdicts, `insufficient` Is Not
#: Lenient. Only this exact string satisfies a claim -- `does-not-hold` and
#: `insufficient` are identical to the accounting below, one derivation,
#: never a per-verdict branch (`design.md`, Decision 5).
HOLDS = "holds"

#: `citation-validation`, Requirement: Three Search Rounds Per Block, Then
#: Exhaustion.
MAX_ROUNDS = 3

#: `the-pdf-arrives-or-the-operator-is-told`, item 2: the default minimum
#: DISTINCT source papers a claim needs before it counts as covered.
#: Two, not one: a single source is exactly the "one paper, unquestioned"
#: shape this feature exists to stop treating as proof (project only one
#: retracted, mis-scraped, or simply mis-read source away from a claim with
#: zero real support); two independent sources is the smallest number that
#: buys real redundancy without demanding a search budget most claims in
#: this bounded, `MAX_ROUNDS`-limited loop could never afford. It is also
#: exactly the threshold the operator's own approved report shape uses
#: ("afirmación A ██ 2/2"). Configurable per call (`--min-sources` on
#: `validate`) for a claim that genuinely needs more, or a fixture that
#: deliberately needs fewer.
DEFAULT_MIN_SOURCES_PER_CLAIM = 2


def distinct_sources_by_claim(records: list[dict]) -> dict[str, set[str]]:
    """`{claim: {distinct r.source_md for r in records if r.verdict ==
    HOLDS and r.claim == claim}}`. Two `holds` records sharing one
    `source_md` are ONE distinct source, not two -- the exact property
    that makes a folder filled with the same paper twice, or a block
    quoting one paper twice, unable to fake a minimum of more than one
    (`the-pdf-arrives-or-the-operator-is-told`, "The guarantee is built by
    COUNTING instead"). `does-not-hold`/`insufficient` records are excluded
    the same way `satisfied_claims` below always has -- only `HOLDS`
    contributes anything to either derivation, never a per-verdict branch.
    """
    sources: dict[str, set[str]] = {}
    for record in records:
        if record["verdict"] == HOLDS:
            sources.setdefault(record["claim"], set()).add(record.get("source_md", ""))
    return sources


def claim_coverage(
    claims: list[str], records: list[dict], *, min_sources: int = DEFAULT_MIN_SOURCES_PER_CLAIM,
) -> list[dict]:
    """Per-claim `{"claim", "required", "satisfied"}` for every claim in
    `claims`, in the given order -- the DATA an operator-facing coverage
    report renders (`afirmacion A ██ 2/2`), computed once here rather than
    re-derived per renderer. A claim absent from `records` entirely reports
    `satisfied: 0`, not an absence -- the same "a real, honestly reported
    zero" precedent `paper_guidance.ingested_papers` already establishes
    for an empty root."""
    sources = distinct_sources_by_claim(records)
    return [
        {"claim": claim, "required": min_sources, "satisfied": len(sources.get(claim, set()))}
        for claim in claims
    ]


def satisfied_claims(records: list[dict], *, min_sources: int = DEFAULT_MIN_SOURCES_PER_CLAIM) -> set[str]:
    """A claim is satisfied when it has at least `min_sources` DISTINCT
    `holds`-verdict source papers (`design.md`, Decision 5, extended by
    `the-pdf-arrives-or-the-operator-is-told`, item 2) -- never bare
    membership in a `holds` record set. `does-not-hold`/`insufficient`
    still contribute nothing, since `distinct_sources_by_claim` itself
    never counts them; there is no second code path that could
    special-case either into passing."""
    sources = distinct_sources_by_claim(records)
    return {claim for claim, distinct in sources.items() if len(distinct) >= min_sources}


def finalize_block(
    paper_dir: Path, block_id: str, claims: list[str], records: list[dict],
    new_body: bytes | None = None, *, min_sources: int = DEFAULT_MIN_SOURCES_PER_CLAIM,
) -> dict:
    """The single gate: given every claim a block needs support for and
    every evidence record gathered so far, decide `pending` (rounds
    remain), refuse `EVIDENCE_EXHAUSTED` naming every unsupported claim and
    its own shortfall (round budget spent), or -- only when every claim
    has `min_sources` distinct sources -- write the block via
    `paper_block.substitute`.

    The write sits strictly inside the all-satisfied branch: `substitute`
    is never even reached while `unsupported` is non-empty, so "the block
    is not written" on exhaustion is control flow, not a policy this
    function merely promises (`citation-validation`, Requirement: Three
    Search Rounds Per Block, Then Exhaustion). Every branch also returns
    `coverage` (`claim_coverage`'s own per-claim `{claim, required,
    satisfied}` list) -- the DATA a coverage report renders, whether or not
    this call ends up writing anything.
    """
    coverage = claim_coverage(claims, records, min_sources=min_sources)
    unsupported = sorted(entry["claim"] for entry in coverage if entry["satisfied"] < entry["required"])
    max_round = max((record.get("round", 0) for record in records), default=0)

    if unsupported:
        if max_round >= MAX_ROUNDS:
            shortfalls = ", ".join(
                f"{entry['claim']!r} ({entry['satisfied']}/{entry['required']} sources)"
                for entry in coverage if entry["satisfied"] < entry["required"]
            )
            raise Refused(
                "EVIDENCE_EXHAUSTED",
                f"block {block_id!r}: unsupported after {MAX_ROUNDS} rounds: {shortfalls}",
            )
        return {
            "status": "pending", "block": block_id, "unsupported": unsupported,
            "round": max_round, "coverage": coverage,
        }

    if new_body is None:
        return {
            "status": "satisfied", "block": block_id, "unsupported": [],
            "round": max_round, "coverage": coverage,
        }

    result = paper_block.substitute(paper_dir, block_id, new_body=new_body)
    return {"status": "written", **result, "coverage": coverage}


@dataclass(frozen=True)
class Citation:
    """One citation occurrence inside a `Sentence` (`citation-placement`
    spec). `position` is `"sentence-end"` or `"mid-sentence"`;
    `attached_to_object` is true when the citation sits immediately beside
    the object it credits; `is_noun_phrase` is true when the citation
    itself functions as the sentence's subject (e.g. "the work in [N] does
    X")."""

    text: str
    position: str
    attached_to_object: bool
    is_noun_phrase: bool


@dataclass(frozen=True)
class Sentence:
    text: str
    citations: tuple[Citation, ...]


def _validate_discovery(sentence: Sentence) -> dict:
    if len(sentence.citations) > 1:
        raise Refused(
            "CITATION_MULTI_CLAIM_SENTENCE",
            f"{sentence.text!r}: two citations in one discovery sentence; split into two sentences",
        )
    for citation in sentence.citations:
        if citation.is_noun_phrase:
            raise Refused(
                "CITATION_NOUN_PHRASE",
                f"{sentence.text!r}: {citation.text!r} is a noun-phrase citation, prohibited under discovery",
            )
        if citation.position != "sentence-end":
            raise Refused(
                "CITATION_NOT_AT_SENTENCE_END",
                f"{sentence.text!r}: {citation.text!r} must sit at the end of the sentence it supports",
            )
    return {"regime": "discovery", "sentence": sentence.text, "result": "pass"}


def _validate_resolution(sentence: Sentence) -> dict:
    for citation in sentence.citations:
        if not citation.attached_to_object:
            raise Refused(
                "CITATION_DETACHED_FROM_OBJECT",
                f"{sentence.text!r}: {citation.text!r} is not attached to the object it credits",
            )
    return {"regime": "resolution", "sentence": sentence.text, "result": "pass"}


def _validate_none(sentence: Sentence) -> dict:
    if sentence.citations:
        raise Refused(
            "CITATION_UNDER_NONE_REGIME",
            f"{sentence.text!r}: a citations:none block cites {[c.text for c in sentence.citations]}",
        )
    return {"regime": "none", "sentence": sentence.text, "result": "pass"}


#: `citation-placement`, Requirement: Placement Dispatches On Regime -- a
#: table, never one universal rule (`proposal.md`, "The governing rule").
_PLACEMENT_RULES = {
    "discovery": _validate_discovery,
    "resolution": _validate_resolution,
    "none": _validate_none,
}


def validate_placement(regime: str, sentence: Sentence) -> dict:
    paper_vocabulary.validate_citations(regime)
    return _PLACEMENT_RULES[regime](sentence)


def read_citations_regime(section_path: Path, block_id: str) -> str:
    """Reads one block's `citations` regime from an already-headered
    `sections/*.md` file. Refuses `CONTRACT_HEADER_ABSENT` (work-state) when
    the file carries no front-matter fence at all -- never a defaulted
    regime (`design.md`, `What Breaks`: none of the ten shipped
    `sections/*.md` carry front matter yet, so every real block refuses
    this until `the-contract-is-data-not-code` lands; tests build their own
    headered fixtures). Reuses `BLOCK_ABSENT` (already classified,
    `paper_block.py`) for a block id the header simply does not declare --
    the same "requested id does not exist" condition, not a second code for
    it.
    """
    data = section_path.read_bytes()
    if not (data.startswith(b"---\n") or data.startswith(b"---\r\n")):
        raise Refused(
            "CONTRACT_HEADER_ABSENT",
            f"{section_path} carries no front-matter header; the citations regime cannot be read",
        )
    header, _body = paper_contract.parse(data)
    for block in header.blocks:
        if block["id"] == block_id:
            return block["citations"]
    raise Refused("BLOCK_ABSENT", f"{block_id!r} is not declared in {section_path}'s header")
