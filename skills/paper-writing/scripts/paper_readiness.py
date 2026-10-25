"""paper_readiness: per-block readiness given satisfied facts and
declarations.

Separable from `paper_graph.py` because readiness and order are two
different questions — back matter proves they differ: zero missing facts
(it requires none), every declaration missing (design.md, `Internal
layering`).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_graph  # noqa: E402


def _iter_blocks_in_declared_order(corpus: "paper_graph.Corpus"):
    """Sections by `position`, blocks within a section in declaration
    order — a stable, human-readable iteration order for a report. Never
    used for the writing order itself, which is `paper_graph.derive_order`'s
    job alone."""
    for section_id in sorted(corpus.sections, key=lambda sid: corpus.sections[sid].position):
        for qualified_id in corpus.order_by_section[section_id]:
            yield corpus.blocks[qualified_id]


def compute_block_readiness(
    block,
    satisfied_facts: set,
    satisfied_declarations: set,
    *,
    opened: bool | None = None,
    basis: str = "supposed-only",
    declined_facts: dict | None = None,
    produced_by: dict | None = None,
) -> dict:
    """Given one `BlockRecord`, report `writable`/`blocked`/`not-applicable`
    naming each still-missing fact and declaration separately. A block whose
    facts are all satisfied but whose declarations are not reports
    `blocked`, never `writable` (`writing-readiness` spec, `Requirement:
    Per-Block Readiness`).

    `optional` is read verbatim off `block.optional`
    (`optional-block-semantics` spec, `Requirement: Readiness Reports The
    Optional Flag`).

    `opened` and `basis` are pure inputs, never a disk read performed here.
    `not-applicable` fires only when the block is `optional`, `opened is
    False` (a caller who does not know openness at all passes `opened=None`,
    which never triggers it), and `basis == "declaration-backed"` — the
    fork the paper chose not to take, not merely a fork this call happens
    not to have satisfied yet. Under `basis="supposed-only"` (the default,
    and `cmd_readiness`'s own flags-only call today), the status is always
    computed from `missing_facts`/`missing_declarations` exactly as before
    this function grew these two keyword-only parameters — `cmd_readiness`
    itself calls this with neither argument, so its behaviour is unchanged.

    `basis="declaration-backed"` and real `opened` values are not resolved
    anywhere yet — that resolution (reading `main.tex`'s opened block ids,
    behind a `readiness --paper` invocation) is Work Unit 6's job
    (`READINESS_BASIS_REQUIRED`, design.md D3). This function accepts the
    values so that caller can be wired later with no change to this
    function's shape (tasks.md, Work Unit 3, 3.2).

    `declined_facts`, when given, maps a fact id the operator has DECLINED
    to `paper_declarations.read_declined`'s own per-fact dict --
    `{"reason": str, "condition": dict, "holds": bool, "detail": str}`,
    re-evaluated fresh from disk on every `read_declined` call. Three
    buckets partition `missing_facts`: `declined_missing` (in
    `declined_facts` and `holds` True -- the decline still stands),
    `stale_missing` (in `declined_facts` and `holds` False -- the decline's
    own condition has LAPSED), and `live_missing` (never declined at all).
    A block reports `"declined"` only when `missing_facts` is non-empty and
    made up ENTIRELY of currently-holding declines (no stale, no live) and
    no declaration is missing either; a block missing even one live fact, or
    one whose decline has lapsed, or any declaration at all, still reports
    `"blocked"` — a decline must never mask a real gap, and a LAPSED decline
    is reported, never silently treated as still `"declined"` nor silently
    auto-unblocked into `"writable"`. The returned dict carries
    `declined_facts` (currently-holding declines named on this block, as
    `[{"fact": <id>, "reason": <reason>}, ...]`) whenever any exist, and
    `stale_declines` (lapsed ones, as
    `[{"fact": <id>, "reason": <reason>, "condition": <dict>, "detail":
    <str>}, ...]`) whenever any exist — the two keys are independent and a
    block can carry either, both, or neither. `declined_facts=None` (the
    default) behaves exactly as an empty dict: no block can ever report
    `"declined"` and neither key is ever added, matching every existing
    caller's behavior unchanged.

    `produced_by`, when given, maps a fact id whose producer is one or more
    blocks (`fact-production` spec) to the tuple of those blocks' own
    qualified ids (`paper_graph.producers_by_fact`) — a plain, static,
    caller-supplied mapping, the same pure-input pattern `declined_facts`
    already uses (design.md, Decision E). For every fact still in
    `missing_facts` that is also a key of `produced_by`, the result gains a
    `blocked_on_produced` entry naming both the fact and every one of its
    producers — so a `blocked` report tells the operator to WRITE the
    producer, never to `declare` it (`writing-readiness` spec, `Requirement:
    Per-Block Readiness`). `produced_by=None` (the default) behaves exactly
    as an empty dict: `blocked_on_produced` is never added, reproducing
    today's behaviour byte for byte.
    """
    declined_facts = declined_facts or {}
    produced_by = produced_by or {}
    missing_facts = [fact for fact in block.requires_facts if fact not in satisfied_facts]
    missing_declarations = [
        declaration for declaration in block.requires_declarations
        if declaration not in satisfied_declarations
    ]
    declined_missing = [
        fact for fact in missing_facts if fact in declined_facts and declined_facts[fact]["holds"]
    ]
    stale_missing = [
        fact for fact in missing_facts
        if fact in declined_facts and not declined_facts[fact]["holds"]
    ]
    live_missing = [fact for fact in missing_facts if fact not in declined_facts]

    if block.optional and basis == "declaration-backed" and opened is False:
        status = "not-applicable"
    elif missing_declarations:
        status = "blocked"
    elif missing_facts:
        status = (
            "declined" if (declined_missing and not stale_missing and not live_missing)
            else "blocked"
        )
    else:
        status = "writable"
    result = {
        "block": block.qualified_id,
        "status": status,
        "missing_facts": missing_facts,
        "missing_declarations": missing_declarations,
        "optional": block.optional,
    }
    if declined_missing:
        result["declined_facts"] = [
            {"fact": fact, "reason": declined_facts[fact]["reason"]} for fact in declined_missing
        ]
    if stale_missing:
        result["stale_declines"] = [
            {
                "fact": fact, "reason": declined_facts[fact]["reason"],
                "condition": declined_facts[fact]["condition"],
                "detail": declined_facts[fact]["detail"],
            }
            for fact in stale_missing
        ]
    blocked_on_produced = [
        {"fact": fact, "producers": list(produced_by[fact])}
        for fact in missing_facts if fact in produced_by
    ]
    if blocked_on_produced:
        result["blocked_on_produced"] = blocked_on_produced
    return result


def compute_readiness(
    corpus: "paper_graph.Corpus",
    satisfied_facts: set,
    satisfied_declarations: set,
    *,
    opened_blocks: set | None = None,
    basis: str = "supposed-only",
    declined_facts: dict | None = None,
    produced_by: dict | None = None,
) -> list:
    """Every block of every section, in a stable declared order (see
    `_iter_blocks_in_declared_order`).

    `opened_blocks`, when given, is the set of qualified block ids known to
    be opened in `main.tex` — a pure set the caller resolved, never read
    here. `opened_blocks=None` (the default) means openness is unknown for
    every block, which `compute_block_readiness` treats as `opened=None`
    and therefore never reports `not-applicable`, regardless of `basis`.

    `produced_by`, when given, is threaded unchanged into every block's own
    `compute_block_readiness` call — the same global, fact-keyed mapping
    every block consults (`declined_facts`'s own pattern)."""
    return [
        compute_block_readiness(
            block, satisfied_facts, satisfied_declarations,
            opened=(None if opened_blocks is None else block.qualified_id in opened_blocks),
            basis=basis,
            declined_facts=declined_facts,
            produced_by=produced_by,
        )
        for block in _iter_blocks_in_declared_order(corpus)
    ]
