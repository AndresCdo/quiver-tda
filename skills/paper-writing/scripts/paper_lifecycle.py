"""paper_lifecycle: two read-only reports over one lifecycle, stated by the
operator (2026-09-19) and never enforced by code before this:

    downloaded -> ingested -> candidate for every claim with no record yet
                                  |
                       validate -> holds          -> cited, counts toward coverage
                                -> does-not-hold  -> still a candidate for the others
                                  |
            when EVERY open claim has its does-not-hold -> exhausted -> operator deletes

**The skill NEVER deletes on its own.** Both reports below only list; the
operator deletes with their own explicit command
(`a-leftover-paper-is-offered-before-it-is-lost`).

Public surface:

    evidence_classed_papers(guidance_dir) -> list[dict]     # {root, folder, markdown}
    open_claims_for_block(records, *, min_sources=...) -> list[str]
    reuse_report(paper_dir, guidance_dir, block_id, *, min_sources=...) -> dict
    corpus_open_claims(paper_dir, *, min_sources=...) -> list[dict]  # [{"block", "claim"}, ...]
    exhaustion_report(paper_dir, guidance_dir, *, min_sources=...) -> dict

No new `Refused` code is raised anywhere in this module: every disk read
here goes through `paper_guidance.py`/`paper_evidence.py`, whose own
refusals (`GUIDANCE_OUTSIDE_REPOSITORY`, `MALFORMED_GUIDANCE_MARKER`,
`UNKNOWN_GUIDANCE_CLASS`) are already classified in `paper_cli.
REFUSAL_CLASSIFICATION`; there is no invocation shape or work state this
module's own two pure reports need a new vocabulary word for.

Both `--source-md` gating (`no-claim-without-a-source-that-holds-it`) and
`validate --source-md`'s own reuse potential were already true the day that
change shipped: `validate --source-md` is not section-scoped
(`paper_guidance.classify_source_md` reads a folder's own registered class,
never the citing block's section), so a paper ingested under ANY
`evidence`-classed root is already citable from any block, corpus-wide.
This module is what finally DISCOVERS that reuse, rather than relocating a
folder nothing needed moved (`SKILL.md`, "Reuse needs NO move").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_evidence  # noqa: E402
import paper_guidance  # noqa: E402
import paper_validate  # noqa: E402


def evidence_classed_papers(guidance_dir: Path) -> list[dict]:
    """Every ingested paper (`paper_guidance.ingested_papers`'s own
    `{"folder", "markdown"}` shape, plus its own `root`) sitting under a
    `guidance/<root>` this repository's registry classes `"evidence"` --
    never `"style-reference"` and never `"unclassified"` (`plan`'s own
    registry, reused verbatim; no second classifier).

    Sorted by `(root, folder)` -- `ingested_papers`/`read_registry` already
    walk in sorted order, this only threads the same order through the
    filter rather than introducing a new one.
    """
    registry = paper_guidance.read_registry(guidance_dir)
    ingested = paper_guidance.ingested_papers(guidance_dir)
    papers: list[dict] = []
    for root in sorted(ingested):
        if registry.get(root) != "evidence":
            continue
        for entry in ingested[root]:
            papers.append({"root": root, "folder": entry["folder"], "markdown": entry["markdown"]})
    return papers


def open_claims_for_block(
    records: list[dict], *, min_sources: int = paper_validate.DEFAULT_MIN_SOURCES_PER_CLAIM,
) -> list[str]:
    """Every claim `records` has ever been asked about for one block, minus
    the ones already `satisfied_claims`-covered (`paper_validate.py`) --
    sorted, so a claim registered but never yet given `min_sources` distinct
    `holds` sources is still "open" no matter how many `does-not-hold`
    verdicts already sit against it (`SKILL.md`: "A `does-not-hold` IS a
    recorded negative judgment ... still a candidate for the others").

    A block with no records at all reports an empty list -- nothing has
    been asked yet, so there is nothing open to reuse a paper against
    (the same honest-empty precedent `paper_guidance.ingested_papers`
    already sets for an empty root).
    """
    claims = sorted({record["claim"] for record in records})
    satisfied = paper_validate.satisfied_claims(records, min_sources=min_sources)
    return [claim for claim in claims if claim not in satisfied]


def _resolve_or_none(raw: str) -> Path | None:
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except OSError:
        return None


def _tested_sources_for_claim(claim: str, records: list[dict]) -> set[Path]:
    tested = set()
    for record in records:
        if record["claim"] != claim:
            continue
        resolved = _resolve_or_none(record.get("source_md", ""))
        if resolved is not None:
            tested.add(resolved)
    return tested


def reuse_candidates_for_claim(claim: str, records: list[dict], papers: list[dict]) -> list[dict]:
    """The subset of `papers` carrying NO verdict yet -- `holds` or
    `does-not-hold` alike -- for `claim`, in `papers`'s own given order.
    "No verdict yet" is decided by `source_md` identity (the exact path an
    evidence span was already located against), never by cite key or
    folder-name similarity -- the same exact-link discipline `paper_bib.
    entry_from_record` already uses for `no-citation-before-its-paper-is-
    ingested`, item 2."""
    tested = _tested_sources_for_claim(claim, records)
    candidates = []
    for paper in papers:
        resolved = _resolve_or_none(paper["markdown"])
        if resolved is not None and resolved not in tested:
            candidates.append(paper)
    return candidates


def reuse_report(
    paper_dir: Path, guidance_dir: Path, block_id: str,
    *, min_sources: int = paper_validate.DEFAULT_MIN_SOURCES_PER_CLAIM,
) -> dict:
    """`SKILL.md` capability A -- what stops the operator re-downloading a
    paper they already have. For `block_id`'s own open claims, names which
    already-ingested, evidence-classed papers have no verdict yet for each
    one. Read-only: `paper_evidence.read_records` and `paper_guidance`'s own
    readers never write."""
    records = paper_evidence.read_records(paper_dir, block_id)
    claims = open_claims_for_block(records, min_sources=min_sources)
    papers = evidence_classed_papers(guidance_dir)
    candidates = {claim: reuse_candidates_for_claim(claim, records, papers) for claim in claims}
    return {"block": block_id, "openClaims": claims, "candidates": candidates}


def corpus_open_claims(
    paper_dir: Path, *, min_sources: int = paper_validate.DEFAULT_MIN_SOURCES_PER_CLAIM,
) -> list[dict]:
    """Every `{"block", "claim"}` pair still open, ACROSS EVERY BLOCK's own
    evidence store (`paper_evidence.read_all_records`) -- corpus-wide, never
    one section's blocks alone (`SKILL.md`: "The deletion criterion is
    corpus-wide, never per section"). Sorted by `(block, claim)`."""
    by_block: dict[str, list[dict]] = {}
    for record in paper_evidence.read_all_records(paper_dir):
        by_block.setdefault(record["block_id"], []).append(record)
    open_claims = []
    for block_id in sorted(by_block):
        for claim in open_claims_for_block(by_block[block_id], min_sources=min_sources):
            open_claims.append({"block": block_id, "claim": claim})
    return open_claims


def exhaustion_report(
    paper_dir: Path, guidance_dir: Path,
    *, min_sources: int = paper_validate.DEFAULT_MIN_SOURCES_PER_CLAIM,
) -> dict:
    """`SKILL.md` capability B -- the exhaustion criterion, computed, never
    guessed. A paper carrying a `holds` verdict ANYWHERE is never exhausted
    (it is cited; deleting it would break that citation), regardless of what
    every other claim decided about it. Otherwise, a paper is `exhausted`
    only when EVERY corpus-wide open claim carries a `does-not-hold` from
    it -- an EMPTY open-claim set never counts as "every" (nothing has been
    tried yet is not evidence of uselessness), so a freshly-ingested,
    never-tested paper is reported active, with the corpus's own open claims
    as its full remaining list, not exhausted by vacuous truth.

    For an active (non-exhausted) paper, `remaining` names every open claim
    this paper carries no verdict for yet -- naming the operator's own
    remaining work (`SKILL.md`: "for a paper that is NOT exhausted, report
    which claims still have no verdict").

    Never restricted to one `evidence`-classed root's own papers being
    tested against one section's claims -- `evidence_classed_papers` and
    `corpus_open_claims` are both already corpus-wide reads."""
    all_records = paper_evidence.read_all_records(paper_dir)
    open_claims = corpus_open_claims(paper_dir, min_sources=min_sources)
    papers = evidence_classed_papers(guidance_dir)

    exhausted: list[dict] = []
    active: list[dict] = []
    for paper in papers:
        resolved = _resolve_or_none(paper["markdown"])
        paper_records = [
            record for record in all_records
            if resolved is not None and _resolve_or_none(record.get("source_md", "")) == resolved
        ]
        if any(record["verdict"] == "holds" for record in paper_records):
            active.append({**paper, "exhausted": False, "reason": "holds", "remaining": []})
            continue

        does_not_hold_pairs = {
            (record["block_id"], record["claim"])
            for record in paper_records if record["verdict"] == "does-not-hold"
        }
        remaining = [
            open_claim for open_claim in open_claims
            if (open_claim["block"], open_claim["claim"]) not in does_not_hold_pairs
        ]
        if open_claims and not remaining:
            exhausted.append({**paper, "exhausted": True, "remaining": []})
        else:
            reason = "no-open-claims" if not open_claims else "remaining-claims"
            active.append({**paper, "exhausted": False, "reason": reason, "remaining": remaining})

    return {"openClaims": open_claims, "exhausted": exhausted, "active": active}
