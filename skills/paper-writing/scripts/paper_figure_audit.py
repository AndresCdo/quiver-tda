"""paper_figure_audit: semantic parity between a TikZ figure and the prose
that describes it — `figure audit`'s engine, and `verify`'s eighth check's.

**The audit's unit of truth is the manifest's `components`**, never every
string inside a `\\node{}`. Decorative labels (`x`, `y`, `\\small`) are not
components and must never be reported as phantom ones; `node_texts` and
`edges` are corroborating evidence in the report, never the verdict's
subject. That boundary is what keeps this module from colliding with
`paper_obligation.check_components` (manifest ↔ fact-derived expected list)
and `check_excluded` (manifest ↔ contract `excludes`), which this module
**reuses rather than re-derives**.

**A content finding is never a CLI refusal.** `check_excluded` raises
`Refused`; this module catches it, records the code and a `fail` verdict as
a finding, and lets the call exit 0. Only an unreadable invocation refuses,
and it reuses `DIAGRAM_SOURCE_ABSENT` / `SECTION_CONTRACTS_UNREADABLE`
rather than inventing a second code for a condition the repo already names.

**The verdict is `paper_verify`'s own closed vocabulary** — `pass` | `fail`
| `unmeasured`. Warnings ride in a separate `warnings` list; there is no
uppercase `WARN` status, and no `status` key at all, because
`paper_cli.main` spreads a result over its own framework `status`
(`paper_cli.py`, `{"status": "ok", ..., **result}`) and a result field named
`status` would silently override it. `unmeasured` exists for the same reason
it exists in `paper_verify.py`: folding "could not check" into `pass` is the
exact false-green this repository builds tests to catch.

Dependency direction is one-way and enforced by construction:
`paper_coupling_evidence.py` MAY import this module;
this module MUST NOT import `paper_verify.py` or
`paper_coupling_evidence.py` (`paper_verify.py` is AST-locked to `re`, so
it could not import this one even if it wanted to).

Public surface:

    FigureEntities                                     -> what was extracted
    extract_entities(tex, manifest) -> FigureEntities
    normalize(token) -> str
    audit_semantics(*, tex, manifest, section_text, contract_figure,
                    expected_components=None, visual=None) -> dict

**The `visual` argument (Commit 3, design.md Decision 4) is plain data
only** -- a caller-supplied, already-computed dict, never resolved by this
function reading disk or spawning a process, the same way
`expected_components` is already supplied. It defaults to every classified
visual dimension present as `{"verdict": "unmeasured", "reason": <code>}`,
read from the one shared roster both this module and `figure-review` import
(`skills/_core/figure/figure_dimensions.py`) so the two sides cannot drift
apart. No value inside `visual` may change this module's own semantic
`verdict`: it is written into the report in exactly one place, placed AFTER
the semantic verdict is already bound to a local `str` (`visual-finding-
boundary`, `Requirement: A Visual Verdict Never Changes The Semantic
Verdict`).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_figure  # noqa: E402
import paper_obligation  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "figure"))
import figure_dimensions  # noqa: E402

#: `\node[options] (name) {text}` — the shallow, explicitly non-AST grammar
#: this module reads. Optional option list, optional node name.
_NODE_RE = re.compile(
    r"\\node\s*(?:\[[^\]]*\])?\s*(?:\([^)]*\))?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
)

#: `\draw[->] (a) -- (b)` — a dataflow edge between two node names.
_EDGE_RE = re.compile(r"\\draw\s*\[[^\]]*->[^\]]*\]\s*\(([^)]+)\)\s*--\s*\(([^)]+)\)")

#: A LaTeX command with a braced argument, e.g. `\textbf{Deep}` -> `Deep`.
_COMMAND_ARG_RE = re.compile(r"\\[A-Za-z]+\s*\{([^{}]*)\}")
#: A bare LaTeX command, e.g. `\small` -> removed.
_COMMAND_RE = re.compile(r"\\[A-Za-z]+")
#: An ALL-CAPS acronym of two or more characters, e.g. `CNN`, `F1`, `TSNE`.
_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
#: Inline math, `$...$` — a variable name the prose must also name.
_MATH_RE = re.compile(r"\$([^$]+)\$")
#: Characters that carry no meaning to a comparison and are DELETED rather
#: than turned into a space: `$F_1$` and `F1` must normalize alike, so the
#: math delimiters and the subscript separator may not become word breaks.
_DELETE_RE = re.compile(r"[{}$~^_\\`\"']+")
#: Characters that ARE a word break: punctuation between two words.
_SPACE_RE = re.compile(r"[,\;:!?\.()\[\]<>/|+\-*=]+")

#: Every reason `audit_semantics` may report `unmeasured` for. Deliberately
#: a different roster from `paper_verify.UNMEASURED_REASONS`: these name what
#: the AUDIT could not compare, and the verify check folds them into its own
#: vocabulary at the boundary.
UNMEASURED_REASONS: tuple[str, ...] = (
    "NO_COMPONENTS_DECLARED",
    "NO_COMPONENTS_FROM",
    "COMPONENTS_FACT_UNRESOLVED",
    "CONTRACT_FIGURE_ABSENT",
)

_VERDICTS = ("pass", "fail", "unmeasured")


@dataclass(frozen=True)
class FigureEntities:
    """What the shallow grammar found. `markers` is authoritative — it is
    this skill's own declaration grammar, the same one
    `paper_figure.cross_check_manifest` reads. `node_texts` and `edges` are
    evidence, never the verdict's subject."""

    markers: tuple[str, ...] = ()
    node_texts: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    caption: str = ""


def extract_entities(tex: str, manifest: dict) -> FigureEntities:
    """Every structural entity this module's grammar can name."""
    markers = tuple(sorted(set(paper_figure._NODE_MARKER_RE.findall(tex))))
    node_texts = tuple(match.strip() for match in _NODE_RE.findall(tex))
    edges = tuple(
        (left.strip(), right.strip()) for left, right in _EDGE_RE.findall(tex)
    )
    return FigureEntities(
        markers=markers,
        node_texts=node_texts,
        edges=edges,
        caption=str(manifest.get("caption") or ""),
    )


def normalize(token: str) -> str:
    """A comparable form of one label or one span of prose.

    Deliberately lossy in the same way on BOTH sides: this module never
    rewrites the figure or the prose, it only asks whether the same thing is
    named in both. Case, LaTeX escaping, math delimiters, and punctuation
    are not meaning, so they are all folded away — while an acronym's own
    letters are NOT (`CNN` stays `cnn`, so a prose mention of
    "convolutional neural network" alone does not silently satisfy it).
    """
    text = _COMMAND_ARG_RE.sub(r" \1 ", token)
    text = _COMMAND_RE.sub(" ", text)
    text = text.replace("\\%", "%").replace("\\_", "_").replace("\\&", "&")
    text = _DELETE_RE.sub("", text)
    text = _SPACE_RE.sub(" ", text)
    return " ".join(text.split()).casefold()


def _descriptive_words(component: str) -> list:
    """A component's words once its acronyms and inline math are removed.

    This is what separates the two failure shapes the plan distinguishes:
    a component with descriptive content that the prose does not carry is a
    genuinely **missing component** (`fail`), while a component whose only
    content is an acronym or a variable — or whose descriptive words the
    prose does carry — is a **naming drift** (`label_mismatches`, warning
    only). "CNN" against prose that says "convolutional neural network" is
    the second shape; a phantom box labelled `bogus` is the first.
    """
    stripped = _MATH_RE.sub(" ", component)
    stripped = _ACRONYM_RE.sub(" ", stripped)
    return [word for word in normalize(stripped).split() if word]


def _label_tokens(component: str) -> list:
    """The tokens inside one component whose verbatim presence in prose is
    required: its ALL-CAPS acronyms and its inline-math variable names."""
    tokens: list = []
    for match in _MATH_RE.finditer(component):
        inner = match.group(1).strip()
        if inner and normalize(inner):
            tokens.append(inner)
    for match in _ACRONYM_RE.finditer(_MATH_RE.sub(" ", component)):
        tokens.append(match.group(0))
    return tokens


def _excluded_finding(contract_figure: dict, components: list) -> dict | None:
    """Reuse `paper_obligation.check_excluded` — and convert its `Refused`
    into a finding, so a content problem never becomes a CLI exit 2."""
    try:
        paper_obligation.check_excluded(contract_figure, components)
    except Refused as exc:
        return {"code": exc.code, "detail": exc.detail}
    return None


def audit_semantics(
    *, tex: str, manifest: dict, section_text: str,
    contract_figure: dict | None, expected_components: list | None = None,
    visual: dict | None = None,
) -> dict:
    """The whole audit: what the figure declares, against what the prose says.

    `contract_figure` is the block's own `figure:` dict when the caller
    knows which block this figure belongs to, and `None` when it does not —
    which is why an unknown binding reports `unmeasured` rather than
    guessing one. `expected_components` is the `components_from` fact's
    already-resolved value, supplied by the caller because resolving a fact
    is a disk read and this function performs none.

    `visual` is the figure pipeline's already-computed visual findings
    (`figure-review measure`'s output shape), supplied by the caller the
    same way `expected_components` is — never resolved here. When `None`,
    the report's `visual` key defaults to every classified dimension
    `unmeasured` (`figure_dimensions.default_visual()`). No value inside
    `visual` changes this function's own semantic `verdict`.
    """
    components = [str(item) for item in (manifest.get("components") or [])]
    entities = extract_entities(tex, manifest)
    prose = normalize(section_text)

    warnings: list = []
    label_mismatches: list = []
    unmatched_nodes: list = []
    matched_nodes: list = []

    for component in components:
        normalized = normalize(component)
        if normalized and normalized in prose:
            matched_nodes.append(component)
            continue
        words = _descriptive_words(component)
        if words and not all(word in prose for word in words):
            # Descriptive content the prose never carries: a phantom component.
            unmatched_nodes.append(component)
            continue
        # Either the descriptive words are all present, or the component has
        # no descriptive content at all — so what drifted is the acronym or
        # the variable name, not the component. A warning, never a failure.
        matched_nodes.append(component)
        for token in _label_tokens(component):
            if normalize(token) not in prose:
                label_mismatches.append({"component": component, "token": token})

    for mismatch in label_mismatches:
        warnings.append(
            f"{mismatch['component']!r} names {mismatch['token']!r}, which the prose "
            "never names: state the acronym or variable in the text, or use the text's own form"
        )

    findings: list = []
    excluded = None
    if contract_figure is not None:
        excluded = _excluded_finding(contract_figure, components)
        if excluded is not None:
            findings.append(excluded)

    # The pipeline-step pair is DIFFERENT from `check_components`'s: this
    # compares the fact's own list against the manifest AND the prose,
    # whereas `check_components` compares it against the manifest alone.
    #
    # `pipeline_steps_reason` is deliberately separate from
    # `unmeasured_reason`: when no contract binding is known (the aggregate
    # `verify` path, which cannot bind a figure id to a block because no such
    # binding is declared anywhere), the pipeline-step comparison is
    # unmeasurable while the component comparison is still perfectly
    # measurable. Collapsing the two would let an unknown binding poison a
    # verdict that was in fact reached — the mirror image of the false-green
    # `unmeasured` exists to prevent.
    missing_pipeline_steps: list = []
    unmeasured_reason: str | None = None
    pipeline_steps_reason: str | None = None
    if not components:
        unmeasured_reason = "NO_COMPONENTS_DECLARED"
    elif contract_figure is None:
        pipeline_steps_reason = "CONTRACT_FIGURE_ABSENT"
    elif contract_figure.get("components_from") is None:
        unmeasured_reason = "NO_COMPONENTS_FROM"
    elif expected_components is None:
        unmeasured_reason = "COMPONENTS_FACT_UNRESOLVED"
    else:
        manifest_norms = {normalize(component) for component in components}
        for step in expected_components:
            normalized = normalize(str(step))
            if normalized in manifest_norms or (normalized and normalized in prose):
                continue
            missing_pipeline_steps.append(str(step))

    if unmatched_nodes or missing_pipeline_steps or findings:
        verdict = "fail"
        unmeasured_reason = None
    elif unmeasured_reason is not None:
        verdict = "unmeasured"
    else:
        verdict = "pass"

    remediation = _remediation(unmatched_nodes, missing_pipeline_steps, findings, label_mismatches)

    report = {
        "verdict": verdict,
        "warnings": warnings,
        "unmatched_nodes": unmatched_nodes,
        "missing_pipeline_steps": missing_pipeline_steps,
        "label_mismatches": label_mismatches,
        "matched_nodes": matched_nodes,
        "remediation": remediation,
        "unmeasured_reason": unmeasured_reason,
        "pipeline_steps_reason": pipeline_steps_reason,
        "evidence": {
            "components": components,
            "markers": list(entities.markers),
            "node_texts": list(entities.node_texts),
            "edges": [list(edge) for edge in entities.edges],
            "caption": entities.caption,
            "proseChars": len(section_text),
        },
    }
    # Structural isolation (design.md, Decision 4, mechanism 1): `visual`
    # is read in exactly ONE place, placed AFTER `verdict` is already
    # bound to the local `str` above -- there is no code path from a
    # caller-supplied visual finding to this function's own semantic
    # verdict.
    report["visual"] = visual if visual is not None else figure_dimensions.default_visual()
    return report


def _remediation(unmatched: list, missing: list, findings: list, mismatches: list) -> list:
    actions: list = []
    for node in unmatched:
        actions.append(f"name or contextualize {node!r} in the section prose, or drop it from the manifest")
    for step in missing:
        actions.append(f"add {step!r} to the figure (and its manifest), or to the prose that justifies it")
    for finding in findings:
        actions.append(f"{finding['code']}: {finding['detail']}")
    for mismatch in mismatches:
        actions.append(
            f"reconcile the acronym/variable {mismatch['token']!r} between the figure and the prose"
        )
    return actions
