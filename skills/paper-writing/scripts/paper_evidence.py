"""paper_evidence: the claim<->source record whose load-bearing element is a
verbatim quoted span of an ingested `.md` -- the thing that turns a citation
verdict from an opinion into a measurement anyone can re-check
(`no-claim-without-a-source-that-holds-it`, `evidence-set` spec).

Public surface:

    EvidenceSpan.locate(md_path, quote)  -> EvidenceSpan   (raises SPAN_NOT_IN_SOURCE)
    Verdict.holds(span, reason="")        -> Verdict
    Verdict.does_not_hold(span, reason="") -> Verdict
    Verdict.insufficient(reason)          -> Verdict
    EvidenceRecord.from_verdict(...)      -> EvidenceRecord
    append_record(paper_dir, record, ...) -> dict
    read_records(paper_dir, block_id)     -> list[dict]
    read_all_records(paper_dir)           -> list[dict]
    write_evidence_manifest(folder, section_id, papers) -> dict
    append_grounding_run(paper_dir, block_id, report, ...) -> dict

No I/O toward the network anywhere in this module -- resolution and metadata
live in `paper_resolve.py`; this module only ever reads bytes already on
disk (`design.md`, Decision 2 and 6).

**`classify_guidance_child` was removed** (zero-production-caller
corrective): it was a second, competing `guidance/` classifier alongside
`paper_guidance.read_registry` -- name-plus-manifest here versus a
per-folder `.paper-writing.json` marker there. `plan` and the
`style-sampler` agent (`.claude/agents/style-sampler.md`: "that
classification belongs to `plan`'s own registry") both already resolve the
evidence/style distinction through `paper_guidance.py`, so this function
was a duplicate mechanism with no consumer, never the missing wire.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_region  # noqa: E402
import paper_vocabulary  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: The manifest a folder under `guidance/<section-id>/` carries when this
#: capability -- and only this capability -- uses it as an evidence source
#: (`evidence-set`, Requirement: Evidence Folders Carry a Producer-Written
#: Manifest). Deliberately a different file from `paper_guidance.py`'s own
#: `.paper-writing.json` style-reference/evidence marker: that registry
#: belongs to a sibling capability this change does not touch, and design.md
#: Decision 6 is explicit that unifying the two discriminators into one
#: shared registry is a later change's work, not this one's.
_EVIDENCE_MANIFEST_NAME = ".papersmith-evidence.json"

#: Sentinel object only `Verdict`'s own factory methods hold a reference to.
#: `Verdict(value="holds", span=None, reason=None)` -- a direct call bypassing
#: `.holds()`/`.does_not_hold()`/`.insufficient()` -- carries no `_token` and
#: is refused in `__post_init__` below. This is what makes "no public
#: string-taking constructor exists" (design.md, Decision 2) a property the
#: interpreter enforces rather than a convention a docstring merely asks for.
_TOKEN = object()


@dataclass(frozen=True)
class EvidenceSpan:
    """A verbatim byte span inside one ingested `.md` file, located by
    search rather than trusted from a caller-supplied offset. Frozen and
    buildable only through `.locate()` -- there is no constructor a caller
    can hand a fabricated `(start, end)` pair to."""

    source_md: str
    byte_start: int
    byte_end: int
    file_sha256: str
    quote: str

    @staticmethod
    def locate(md_path: Path, quote: str) -> "EvidenceSpan":
        """Byte-searches `md_path` for `quote`, encoded as UTF-8. Refuses
        `SPAN_NOT_IN_SOURCE` (work-state) when the quote is not literally
        present -- a paraphrase can never become a span, which is what makes
        a spanless `Verdict.holds`/`.does_not_hold` structurally impossible
        (`design.md`, Decision 2; `evidence-set`, Requirement: A Spanless
        Record Is Insufficient By Construction).

        The searched bytes are exactly `md_path`'s own on-disk content --
        nothing here ever re-serializes the claim, the quote, or any value
        under test back into the bytes being searched, which is the
        transcription-lock failure mode this design explicitly guards
        against (`sdd-apply` launch context, defect 1).
        """
        data = md_path.read_bytes()
        needle = quote.encode("utf-8")
        if not needle:
            raise Refused("SPAN_NOT_IN_SOURCE", f"{md_path}: an empty quote locates nothing")
        idx = data.find(needle)
        if idx == -1:
            raise Refused(
                "SPAN_NOT_IN_SOURCE",
                f"{md_path}: quote not found verbatim in the ingested source",
            )
        digest = hashlib.sha256(data).hexdigest()
        return EvidenceSpan(
            source_md=str(md_path),
            byte_start=idx,
            byte_end=idx + len(needle),
            file_sha256=digest,
            quote=quote,
        )


@dataclass(frozen=True)
class Verdict:
    """`holds` | `does-not-hold` | `insufficient` -- never constructed with
    a bare verdict string (see `_TOKEN` above). `holds`/`does_not_hold`
    require a real, located `EvidenceSpan` positionally; `insufficient`
    takes no span at all, because there is nothing to cite
    (`citation-validation`, Requirement: The Verdict Is Decided Against the
    Stored Span)."""

    value: str
    span: EvidenceSpan | None
    reason: str | None
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _TOKEN:
            raise TypeError(
                "Verdict has no public constructor; use "
                "Verdict.holds()/.does_not_hold()/.insufficient()"
            )
        paper_vocabulary.validate_verdict(self.value)

    @staticmethod
    def holds(span: EvidenceSpan, reason: str = "") -> "Verdict":
        if span is None:
            raise Refused("VERDICT_SPAN_REQUIRED", "Verdict.holds() requires a located span")
        return Verdict(value="holds", span=span, reason=reason or None, _token=_TOKEN)

    @staticmethod
    def does_not_hold(span: EvidenceSpan, reason: str = "") -> "Verdict":
        if span is None:
            raise Refused(
                "VERDICT_SPAN_REQUIRED", "Verdict.does_not_hold() requires a located span"
            )
        return Verdict(value="does-not-hold", span=span, reason=reason or None, _token=_TOKEN)

    @staticmethod
    def insufficient(reason: str) -> "Verdict":
        return Verdict(value="insufficient", span=None, reason=reason, _token=_TOKEN)


@dataclass(frozen=True)
class EvidenceRecord:
    """One claim<->source pair (`evidence-set`, Requirement: The Claim<->
    Source Record Shape). `locator`/`source_md`/`quote` are empty exactly
    when `verdict == "insufficient"` -- there is no other way to reach that
    state, since `Verdict.holds`/`.does_not_hold` cannot be built without a
    span (see `Verdict` above)."""

    block_id: str
    regime: str
    claim: str
    cite_key: str
    identifier: str
    resolver: str
    metadata_digest: str
    source_md: str
    quote: str
    locator: dict
    verdict: str
    round: int

    def to_json(self) -> dict:
        return {
            "block_id": self.block_id,
            "regime": self.regime,
            "claim": self.claim,
            "cite_key": self.cite_key,
            "identifier": self.identifier,
            "resolver": self.resolver,
            "metadata_digest": self.metadata_digest,
            "source_md": self.source_md,
            "quote": self.quote,
            "locator": dict(self.locator),
            "verdict": self.verdict,
            "round": self.round,
        }

    @staticmethod
    def from_verdict(
        *,
        block_id: str,
        regime: str,
        claim: str,
        cite_key: str,
        identifier: str,
        resolver: str,
        metadata_digest: str,
        verdict: Verdict,
        round: int,
    ) -> "EvidenceRecord":
        if verdict.span is not None:
            source_md = verdict.span.source_md
            quote = verdict.span.quote
            locator = {
                "byte_start": verdict.span.byte_start,
                "byte_end": verdict.span.byte_end,
                "file_sha256": verdict.span.file_sha256,
            }
        else:
            source_md = ""
            quote = ""
            locator = {}
        return EvidenceRecord(
            block_id=block_id,
            regime=regime,
            claim=claim,
            cite_key=cite_key,
            identifier=identifier,
            resolver=resolver,
            metadata_digest=metadata_digest,
            source_md=source_md,
            quote=quote,
            locator=locator,
            verdict=verdict.value,
            round=round,
        )


def _store_path(paper_dir: Path, block_id: str) -> Path:
    return paper_dir / ".paper-writing" / "evidence" / f"{block_id}.jsonl"


def append_record(paper_dir: Path, record: EvidenceRecord, *, guidance_dir: Path | None = None) -> dict:
    """Appends one JSON line to `paper/.paper-writing/evidence/<block-id>.jsonl`
    (`evidence-set`, Requirement: The Claim<->Source Record Shape). Never
    rewrites a prior line -- an evidence record documents a search round
    that really happened, so an existing line is a record, not a value to
    edit (`sdd-apply` Step 4a).

    When `guidance_dir` is given and this record carries a real span, also
    marks the guidance folder the source `.md` sits under as evidence-typed
    (`write_evidence_manifest` below) -- the producer side of `evidence-set`'s
    manifest requirement, exercised by the same call that proves a claim has
    a real span rather than a second, disconnected write path.
    """
    path = _store_path(paper_dir, record.block_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_json()) + "\n")
    result = {"path": str(path), "block": record.block_id}
    if guidance_dir is not None and record.source_md:
        marked = _mark_evidence_folder(Path(record.source_md), guidance_dir, record.cite_key)
        if marked is not None:
            result["manifest"] = marked
    return result


def read_records(paper_dir: Path, block_id: str) -> list[dict]:
    """Every record written so far for `block_id`, oldest first. A block
    with no store yet reports an empty list -- nothing has been searched,
    which is different from having searched and found nothing."""
    path = _store_path(paper_dir, block_id)
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def read_all_records(paper_dir: Path) -> list[dict]:
    """Every evidence record across every block's own store, oldest first
    within each block. `paper_bib.build_refs_bib` (WU2) is the real caller:
    assembling `refs.bib` needs every block's cited sources in one pass, not
    one block at a time."""
    store_dir = paper_dir / ".paper-writing" / "evidence"
    if not store_dir.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(store_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_evidence_manifest(folder: Path, *, section_id: str, papers: list[str],
                             created_by: str = "paper-writing") -> dict:
    """Writes/updates `folder/.papersmith-evidence.json`: `{kind, section,
    created_by, blocks}` (`design.md`, Decision 6). Idempotent per paper
    name -- re-marking a folder that already names a paper does not
    duplicate it. Never called on a folder whose name is not a section id;
    callers that want a section-scoped evidence folder resolve that
    themselves (`_mark_evidence_folder` below is the one caller in this
    module).
    """
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / _EVIDENCE_MANIFEST_NAME
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            existing = {}
    else:
        existing = {}
    blocks = list(existing.get("blocks", [])) if isinstance(existing, dict) else []
    for paper in papers:
        if paper not in blocks:
            blocks.append(paper)
    manifest = {
        "kind": "evidence",
        "section": section_id,
        "created_by": created_by,
        "blocks": blocks,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"path": str(manifest_path), "manifest": manifest}


def _grounding_runs_path(paper_dir: Path) -> Path:
    return paper_dir / ".paper-writing" / "grounding-runs.jsonl"


def append_grounding_run(
    paper_dir: Path, block_id: str, report: dict, *, clock=paper_region.default_clock,
) -> dict:
    """Appends one JSON line to `paper/.paper-writing/grounding-runs.jsonl`,
    the recorder the `the-block-asserts-only-what-its-section-carries`
    skill's own falsifier depends on: "over ten or more recorded real
    `write` runs against genuine document-rooted bindings, if any block
    reaches `written` with `downgraded > 0`, or with `subjects > 0` and
    `decided == 0`, the no-ratio-threshold ruling is wrong...". Without a
    place to accumulate those runs, the falsifier is undischargeable no
    matter how many real runs actually happen -- an unrecorded run and a
    run that never happened are indistinguishable, which is exactly the
    "unmeasured looks like measured" failure mode this whole change exists
    to remove.

    `report` is recorded verbatim -- `paper_grounding.source_grounding_report`'s
    own return value, or `paper_write.write_block`'s interim
    `{"status": "unmeasured", "subjects": 0}` envelope for a non-
    transposition or unbound block -- never reshaped or recomputed here;
    this module only ever records what a run already produced (`design.md`,
    Decision 2 and 6, the same discipline `append_record` above follows).

    Never rewrites a prior line, following `append_record`'s own
    convention exactly: a line documents one `write` run that really
    happened, so an existing line is a record, not a value to edit.

    Deliberately lets a write failure (`OSError`) propagate rather than
    catching it. This ledger lives in the same sidecar the evidence store
    already trusts with real records; silently swallowing a failed append
    would leave a real `written` run with no line at all -- indistinguishable
    from a run that reported `unmeasured` on purpose -- which is precisely
    the ambiguity this recorder exists to close. A caller that cannot
    tolerate the ledger being unwritable must decide that itself; this
    function never decides it silently.
    """
    path = _grounding_runs_path(paper_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"timestamp": clock(), "block_id": block_id, **report}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")
    return {"path": str(path), "block": block_id}


def _mark_evidence_folder(source_md: Path, guidance_dir: Path, cite_key: str) -> dict | None:
    """Resolves `source_md`'s immediate parent folder under `guidance_dir`
    and marks it evidence-typed. Returns `None` (never refuses) when
    `source_md` does not sit under `guidance_dir` at all -- a fixture
    ingested source outside `guidance/` is a legitimate test shape
    (design.md, `evidence-set` domain-independence fixture) and marking
    nothing is correct, not a silent failure.
    """
    try:
        resolved_source = source_md.resolve()
        resolved_guidance = guidance_dir.resolve()
        relative = resolved_source.relative_to(resolved_guidance)
    except ValueError:
        return None
    if not relative.parts:
        return None
    folder = resolved_guidance / relative.parts[0]
    return write_evidence_manifest(folder, section_id=relative.parts[0], papers=[cite_key])
