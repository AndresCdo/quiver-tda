"""paper_region: the shared grammar `declarations`/`provenance` regions in
`main.tex` are written in.

One marker vocabulary, two kinds (`KINDS`); `paper_declarations.py` and
`paper_provenance.py` are the only consumers. Neither kind's marker prefix
collides with Phase 1's own `paper_block.MARKER_PREFIX`
(`b"%% paper-writing block"`) — proven in
`tests/test_paper_decisions.py::DisjointGrammarTests`, derived from
`paper_block.MARKER_PREFIX` and `KINDS` below rather than asserted in prose.
Phase 1's `scan_markers` skips any line that does not start with its own
exact prefix, which is the entire mechanism that keeps a region readable as
prose to Phase 1; this module's parser mirrors that discipline in reverse,
anchoring on each kind's own full prefix and never on the shared
`%% paper-writing ` lead-in, so it cannot mistake a block marker for a
region marker either.

Grammar: `%% paper-writing <kind> begin sha256=<hex>` ... `%% paper-writing
<kind> end`, at most one pair per kind in a document. The body between the
two markers is canonical JSON (`json.dumps(indent=2, sort_keys=True,
ensure_ascii=False)`), with every line — never only the first — carrying
its own `%% ` prefix, so the JSON is never typeset into the rendered
document. The digest in the begin marker covers the raw prefixed body
bytes, prefixes included: the same rule `paper_block.py` applies to a block
body, no exception (design.md, `The digest covers the region body, and a
mismatch never heals itself`).

This module owns only the marker grammar and the digest: `REGION_MALFORMED`,
`REGION_DUPLICATED`, `REGION_UNPAIRED`. A digest MISMATCH between a begin
marker's recorded value and the body's actual bytes is not this module's
refusal — `paper_declarations.py` and `paper_provenance.py` each raise their
own kind-specific code (`DECLARATIONS_HAND_EDITED` /
`PROVENANCE_HAND_EDITED`) after calling `read_region` and comparing
`current_digest(body_bytes)` against `digest` themselves.

Public surface:

    KINDS                                  -> ("declarations", "provenance")
    find_region(data, kind)   -> dict|None  (raises REGION_MALFORMED,
                                               REGION_DUPLICATED,
                                               REGION_UNPAIRED)
    read_region(data, kind)   -> dict|None  (find_region + decoded body)
    current_digest(body_bytes) -> str
    build_region_bytes(kind, body_obj) -> (bytes, str)
    replace_or_append(data, kind, region_bytes, existing) -> bytes
    serialize_body(obj)  -> bytes
    deserialize_body(body_bytes) -> dict
    default_clock()      -> str
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: Both region kinds this grammar admits. `b"block"` (Phase 1's own slot-2
#: literal) is deliberately absent, and neither entry is a prefix of the
#: other — `DisjointGrammarTests` holds both properties, derived from this
#: tuple rather than hand-asserted.
KINDS: tuple[str, ...] = ("declarations", "provenance")

_LINE_PREFIX = b"%% "


def region_prefix(kind: str) -> bytes:
    """The exact line-start bytes for `kind`'s markers: `%% paper-writing
    <kind>` — the same whitespace-delimited slot 2 Phase 1's literal
    `block` occupies."""
    return f"%% paper-writing {kind}".encode("ascii")


def _begin_re(kind: str) -> re.Pattern:
    return re.compile(
        rb"^%% paper-writing " + kind.encode("ascii")
        + rb" begin sha256=(?P<digest>[0-9a-f]{64})$"
    )


def _end_re(kind: str) -> re.Pattern:
    return re.compile(rb"^%% paper-writing " + kind.encode("ascii") + rb" end$")


def _iter_lines(data: bytes):
    """Same shape as `paper_block._iter_lines`: yields `(start, end,
    content)` per line, recognizing only `\\n`/`\\r\\n`. Duplicated rather
    than imported — this module has no other reason to depend on
    `paper_block.py`, and importing it purely for a private helper would
    introduce a coupling neither module's own docstring claims."""
    start = 0
    length = len(data)
    while start < length:
        nl = data.find(b"\n", start)
        if nl == -1:
            end = length
            content_end = length
        else:
            end = nl + 1
            content_end = nl - 1 if (nl > start and data[nl - 1:nl] == b"\r") else nl
        yield start, end, data[start:content_end]
        start = end


def find_region(data: bytes, kind: str) -> dict | None:
    """Locate the single `kind` region in `data`, if any.

    Returns `None` when no marker line of this kind is present at all —
    absence is generation 0, never an error (design.md, `Products`: "an
    absent region is generation 0, never an error"). Refuses
    `REGION_MALFORMED` (work-state) for a line starting with this kind's
    prefix but not matching its exact begin/end grammar, `REGION_DUPLICATED`
    (work-state) for a second begin or a second end, and `REGION_UNPAIRED`
    (work-state) for a begin with no matching end or an end with no
    matching begin.
    """
    if kind not in KINDS:
        raise Refused(
            "REGION_MALFORMED", f"{kind!r} is not one of the declared region kinds {KINDS}"
        )
    prefix = region_prefix(kind)
    begin_re = _begin_re(kind)
    end_re = _end_re(kind)

    begin_marker = None
    end_marker = None
    for line_no, (start, end, content) in enumerate(_iter_lines(data), start=1):
        if not content.startswith(prefix):
            continue
        m = begin_re.match(content)
        if m:
            if begin_marker is not None:
                raise Refused(
                    "REGION_DUPLICATED", f"a second {kind!r} begin marker at line {line_no}"
                )
            begin_marker = {
                "start": start,
                "end": end,
                "digest": m.group("digest").decode("ascii"),
            }
            continue
        m = end_re.match(content)
        if m:
            if end_marker is not None:
                raise Refused(
                    "REGION_DUPLICATED", f"a second {kind!r} end marker at line {line_no}"
                )
            end_marker = {"start": start, "end": end}
            continue
        raise Refused(
            "REGION_MALFORMED",
            f"line {line_no} matches the {kind!r} region prefix but not its grammar: {content!r}",
        )

    if begin_marker is None and end_marker is None:
        return None
    if begin_marker is None or end_marker is None:
        found = "end" if begin_marker is None else "begin"
        raise Refused(
            "REGION_UNPAIRED",
            f"{kind!r} region has a {found} marker with no matching counterpart",
        )
    if end_marker["start"] < begin_marker["end"]:
        raise Refused(
            "REGION_UNPAIRED", f"{kind!r} region's end marker precedes its begin marker"
        )

    return {
        "kind": kind,
        "digest": begin_marker["digest"],
        "begin_start": begin_marker["start"],
        "body_start": begin_marker["end"],
        "body_end": end_marker["start"],
        "end_end": end_marker["end"],
    }


def serialize_body(obj: dict) -> bytes:
    """Canonical JSON, one `%% ` prefix per line, one trailing newline.

    `sort_keys=True` is load-bearing: without it the same content
    serializes differently between runs and every second `plan` would
    report a phantom hand edit (design.md, `JSON region bodies,
    comment-prefixed, canonically serialized`).
    """
    json_bytes = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
    lines = json_bytes.split(b"\n")
    prefixed = b"\n".join(
        (_LINE_PREFIX + line) if line else _LINE_PREFIX.rstrip() for line in lines
    )
    return prefixed + b"\n"


def deserialize_body(body_bytes: bytes) -> dict:
    """The inverse of `serialize_body`: strips the `%% ` prefix from every
    line, then `json.loads`s the result — all-or-nothing, so a body whose
    prefix was hand-edited away never parses partially. Refuses
    `REGION_MALFORMED` for a line missing the prefix, or for a body that is
    not valid JSON once every prefix is stripped.
    """
    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refused("REGION_MALFORMED", f"region body is not valid utf-8: {exc}")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    stripped = []
    for line in lines:
        if line.startswith("%% "):
            stripped.append(line[3:])
        elif line == "%%":
            stripped.append("")
        else:
            raise Refused(
                "REGION_MALFORMED", f"region body line does not carry the '%% ' prefix: {line!r}"
            )
    try:
        return json.loads("\n".join(stripped))
    except json.JSONDecodeError as exc:
        raise Refused("REGION_MALFORMED", f"region body is not valid JSON: {exc.msg}")


def build_region_bytes(kind: str, body_obj: dict) -> tuple[bytes, str]:
    """Returns `(full_region_bytes, digest_hex)`: begin marker, prefixed
    body, end marker, each line ending its own. The digest covers the raw
    prefixed body bytes, prefixes included — byte-for-byte Phase 1's rule
    for a block body, no exception.
    """
    body_bytes = serialize_body(body_obj)
    digest = hashlib.sha256(body_bytes).hexdigest()
    begin_line = f"%% paper-writing {kind} begin sha256={digest}\n".encode("ascii")
    end_line = f"%% paper-writing {kind} end\n".encode("ascii")
    return begin_line + body_bytes + end_line, digest


def read_region(data: bytes, kind: str) -> dict | None:
    """The disk-reading counterpart to `build_region_bytes`: locates the
    region, decodes its body, and hands back everything a caller needs to
    both read it and verify + replace it later.

    Returns `None` when absent (generation 0). The returned dict's
    `body_bytes` is the raw prefixed bytes exactly as found on disk — pass
    it to `current_digest` and compare against `digest` before trusting
    `body`; that comparison is the caller's own kind-specific refusal, not
    this module's.
    """
    span = find_region(data, kind)
    if span is None:
        return None
    body_bytes = data[span["body_start"]:span["body_end"]]
    return {
        "kind": kind,
        "digest": span["digest"],
        "body_bytes": body_bytes,
        "body": deserialize_body(body_bytes),
        "begin_start": span["begin_start"],
        "end_end": span["end_end"],
    }


def current_digest(body_bytes: bytes) -> str:
    return hashlib.sha256(body_bytes).hexdigest()


def replace_or_append(data: bytes, kind: str, region_bytes: bytes, existing: dict | None) -> bytes:
    """Splice `region_bytes` into `data`: replaces `existing`'s exact span
    when given, else appends at the end of the file — the same
    never-insert-a-blank-line-not-asked-for discipline
    `paper_block.build_open_candidate` uses for its own end-of-file
    insertion.
    """
    if existing is not None:
        return data[:existing["begin_start"]] + region_bytes + data[existing["end_end"]:]
    gap = b"\n" if data and not data.endswith(b"\n") else b""
    return data + gap + region_bytes


def default_clock() -> str:
    """UTC ISO-8601 timestamp. Every record-stamping caller (
    `paper_declarations.py`'s `recorded`, `paper_provenance.py`'s
    `written`) accepts a `clock` callable defaulting to this one, so the
    two share one implementation instead of two, and a test can inject a
    fixed one for determinism (design.md, `Timestamps come from an
    injectable clock so the suite is deterministic`).
    """
    return datetime.now(timezone.utc).isoformat()
