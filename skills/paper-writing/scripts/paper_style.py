"""paper_style: register, not content — resolves and records the equivalent
block from each `style-reference`-classed guidance folder (`style-channel`
spec).

The style-sampler agent (`.claude/agents/style-sampler.md`) proposes
`{reference, source_md, span}` per style-reference entry; this module
verifies residency (the proposed span is byte-present, verbatim, at that
locator in the ingested `.md`, reusing `paper_evidence.EvidenceSpan.locate`
and its `SPAN_NOT_IN_SOURCE` refusal rather than inventing a second one) and
records the result as `R` — the sampler's own account is never trusted
about the reference file directly (`design.md`, Decision D5).

Shared token normalization (case-fold, collapse whitespace, strip LaTeX
commands, exclude math) lives here once, so `paper_leak.py`'s tripwire and
proof both read identically (`design.md`, Decision D6).

Public surface:

    resolve_style_set(guidance_dir, proposals) -> (R, no_equivalent)
    normalize_tokens(text)                     -> list[str]
    strip_math(text)                           -> str
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_evidence  # noqa: E402
import paper_guidance  # noqa: E402

_MATH_INLINE_RE = re.compile(r"\$[^$]*\$|\\\(.*?\\\)")
_MATH_DISPLAY_RE = re.compile(
    r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(equation|align|gather|math)\*?\}.*?\\end\{\1\*?\}",
    re.DOTALL,
)
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?")
_TOKEN_RE = re.compile(r"[a-z0-9']+")


def strip_math(text: str) -> str:
    """Removes every math environment (`$...$`, `\\[...\\]`,
    `\\begin{equation|align|gather|math}...\\end{...}`) so a shared run of
    notation never trips the leak tripwire (`style-leak-detection` spec,
    `Requirement: The Eight-Token Tripwire`, "Shared math notation does not
    trip the tripwire")."""
    text = _MATH_DISPLAY_RE.sub(" ", text)
    text = _MATH_INLINE_RE.sub(" ", text)
    return text


def normalize_tokens(text: str) -> list[str]:
    """Case-fold, collapse whitespace, strip LaTeX commands, exclude math —
    the one normalization both the tripwire and the overlap proof read
    identically (`design.md`, Decision D6). Never re-implemented in
    `paper_leak.py`."""
    text = strip_math(text)
    text = _LATEX_CMD_RE.sub(" ", text)
    return _TOKEN_RE.findall(text.lower())


def resolve_style_set(guidance_dir: Path, proposals: list[dict]) -> tuple[list[dict], list[str]]:
    """`proposals`: the style-sampler agent's account, one entry per
    `style-reference`-classed guidance folder — either `{"reference":
    <folder>, "source_md": <path>, "span": <verbatim whole equivalent
    block>}` or `{"reference": <folder>, "noEquivalent": true}`.

    Returns `(R, no_equivalent)`. `R` holds one recorded, residency-verified
    sample per resolved reference — the span passed WHOLE, exactly as the
    agent returned it, never excerpted or truncated here (`style-channel`
    spec, `Requirement: Whole-Block Passing`). `no_equivalent` names every
    style-reference the agent could not resolve; every reference lacking one
    degrades the style set toward empty, never an error (`style-channel`
    spec, `Requirement: Recorded Sample Set Is The Only Admissible
    Reference`).

    A reference the guidance registry classes `style-reference` but for
    which `proposals` carries no entry at all is treated the same as an
    explicit `noEquivalent` — the sampler simply did not resolve one.
    """
    registry = paper_guidance.read_registry(guidance_dir)
    style_references = sorted(name for name, cls in registry.items() if cls == "style-reference")
    by_reference = {entry["reference"]: entry for entry in proposals}

    recorded: list[dict] = []
    no_equivalent: list[str] = []
    for reference in style_references:
        proposal = by_reference.get(reference)
        if proposal is None or proposal.get("noEquivalent"):
            no_equivalent.append(reference)
            continue
        span = paper_evidence.EvidenceSpan.locate(Path(proposal["source_md"]), proposal["span"])
        recorded.append({
            "reference": reference,
            "source_md": proposal["source_md"],
            "span": proposal["span"],
            "locator": {
                "byte_start": span.byte_start,
                "byte_end": span.byte_end,
                "file_sha256": span.file_sha256,
            },
        })
    return recorded, no_equivalent
