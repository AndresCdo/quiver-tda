"""paper_marker: the shared seal convention every `.paper-writing.json`
marker uses -- one key, one canonicalization rule, one digest, one atomic
write. `paper_declarations.py` (the `revisions` marker) and
`paper_guidance.py` (the `class` marker) are the only consumers; both
markers share this file's own NAME (`paper_declarations._SOURCE_MARKER_NAME`,
`paper_guidance._MARKER_NAME`) but keep disjoint key sets of their own --
this module owns neither grammar, only the seal both admit (design.md
Decision A/B).

SEAL_STRENGTH states the seal's real strength, byte-identically, right here:
This seal detects an unaware edit. It is self-consistency, not tamper-proofing: the convention has no secret, so anyone who reproduces it can edit the file and recompute a matching seal.

This module NEVER raises a consumer's own refusal code -- `paper_region.py`'s
own split, verbatim (design.md Decision B): `seal_shape_error` returns the
detail string a caller raises under ITS OWN malformed code, or `None`; a
present, shape-valid seal that does not match is a comparison the CALLER
performs itself (`computed_seal(obj) != obj[SEAL_KEY]`) and raises its own
`*_HAND_EDITED` code for.

Public surface:

    SEAL_KEY                          -> "seal_sha256"
    SEAL_STRENGTH                     -> the one sentence, interpolated everywhere (Decision G)
    canonical_bytes(obj)   -> bytes   (sorted-keys JSON, one trailing newline)
    computed_seal(obj)     -> str     (sha256 over canonical_bytes(obj minus SEAL_KEY))
    is_sealed(obj)         -> bool    (SEAL_KEY present)
    seal_shape_error(obj)  -> str | None
    write(path, obj, *, sealed=True) -> dict
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402,F401 -- this module raises nothing of its own
                                     # (design.md Decision B, the paper_region.py split); the
                                     # import states the dependency boundary both marker
                                     # modules rely on ("stdlib + impl_refusals only, so both
                                     # marker modules can import it with no cycle in either
                                     # direction") rather than a symbol this file calls.

#: The one key both marker grammars admit for the seal (design.md Decision B).
SEAL_KEY = "seal_sha256"

#: Decision G's exact sentence -- quoted verbatim in this module's own
#: docstring above, both `*_HAND_EDITED` refusal details
#: (`paper_declarations.read_revisions_marker`, `paper_guidance._classify`),
#: `SKILL.md` and `references/usage.md`. A test derives its expectation from
#: THIS constant and asserts byte-identical presence in all four surfaces,
#: so weakening the claim anywhere is a red test, never a review miss.
SEAL_STRENGTH = (
    "This seal detects an unaware edit. It is self-consistency, not "
    "tamper-proofing: the convention has no secret, so anyone who "
    "reproduces it can edit the file and recompute a matching seal."
)

_SEAL_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(obj: dict) -> bytes:
    """Sorted-keys JSON, one trailing newline -- `sort_keys=True` is
    load-bearing for the identical reason `paper_region.serialize_body`
    documents: without it the same declaration serializes differently
    between runs, and every second `plan` would report a phantom hand
    edit."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"


def computed_seal(obj: dict) -> str:
    """sha256 over `canonical_bytes` of `obj` with `SEAL_KEY` excluded --
    the seal never covers its own recorded value."""
    without_seal = {key: value for key, value in obj.items() if key != SEAL_KEY}
    return hashlib.sha256(canonical_bytes(without_seal)).hexdigest()


def is_sealed(obj: dict) -> bool:
    """`True` iff `SEAL_KEY` is a top-level key of `obj` -- shape-blind on
    purpose; `seal_shape_error` is the caller's separate shape check."""
    return SEAL_KEY in obj


def seal_shape_error(obj: dict) -> str | None:
    """`None` when `SEAL_KEY` is absent, or present as a 64-character
    lowercase hex string; otherwise the detail a CONSUMER raises under its
    OWN malformed code -- this module never invents a consumer's refusal
    (`paper_region.py`'s own split, verbatim)."""
    if SEAL_KEY not in obj:
        return None
    value = obj[SEAL_KEY]
    if not isinstance(value, str) or not _SEAL_HEX_RE.match(value):
        return f"{SEAL_KEY!r} must be a 64-character lowercase hex string, got {value!r}"
    return None


def _atomic_replace(path: Path, data: bytes) -> None:
    """A fourth copy of the same same-directory temp-file-then-`os.replace`
    shape `paper_block.py`, `paper_contract.py` and `paper_declarations.py`
    each already carry their own of (design.md Decision B) -- copied rather
    than imported from `paper_declarations`, which would create the exact
    import cycle Decision A's own reasoning rejects."""
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def write(path: Path, obj: dict, *, sealed: bool = True) -> dict:
    """Writes `obj` to `path`, atomically. `sealed=True` (the default) sets
    `SEAL_KEY` to `computed_seal` of everything else; `sealed=False` (the
    `--unsealed` rollback path, design.md Decision K) leaves `SEAL_KEY`
    absent entirely, so the written bytes match the pre-seal grammar an
    unmodified older reader still accepts. `obj`'s own `SEAL_KEY`, if any,
    is never trusted -- it is always recomputed or dropped, never carried
    through unchanged. Returns the object exactly as written."""
    to_write = {key: value for key, value in obj.items() if key != SEAL_KEY}
    if sealed:
        to_write[SEAL_KEY] = computed_seal(to_write)
    _atomic_replace(path, canonical_bytes(to_write))
    return to_write
