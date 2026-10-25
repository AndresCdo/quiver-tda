"""paper_obligation: what a diagram must contain, read off the contract's
own `figure:` declaration and never hardcoded against a section or block id
(`diagram-obligation` spec, `Requirement: Obligations Read From Contract
Front Matter`).

Pure functions over already-parsed data — a `figure` obligation dict
(`paper_contract._parse_figure`'s own shape), a manifest's component list,
an ordered fact-resolution list, caption text, and (for the cross-diagram
check) every diagram's own component set. No disk I/O, no subprocess, no
`PATH` needed to test any of it (design.md, "`paper_obligation.py` is pure
functions over parsed headers and manifests").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402


def check_components(figure: dict, manifest_components: list, fact_value: list) -> None:
    """`diagram-obligation` spec, `Requirement: Components Check`: the
    diagram's declared labels MUST equal `fact_value`; when `ordered` is
    true the sequence MUST also match. Refuses `COMPONENT_MISMATCH` naming
    what's missing and what's extra."""
    declared = list(manifest_components)
    expected = list(fact_value)
    if figure["ordered"]:
        if declared == expected:
            return
    else:
        if set(declared) == set(expected):
            return
    missing = [item for item in expected if item not in declared]
    extra = [item for item in declared if item not in expected]
    detail = f"missing={missing} extra={extra}"
    if figure["ordered"] and set(declared) == set(expected) and declared != expected:
        detail = f"same set, wrong order: declared={declared} expected={expected}"
    raise Refused("COMPONENT_MISMATCH", detail)


def check_excluded(figure: dict, manifest_components: list) -> None:
    """`diagram-obligation` spec, `Requirement: Separation Check` (own
    `excludes`): refuses `EXCLUDED_COMPONENT` naming the offending label
    and the excluded class it matches."""
    for excluded_class in figure["excludes"]:
        for component in manifest_components:
            if excluded_class.lower() in component.lower():
                raise Refused(
                    "EXCLUDED_COMPONENT",
                    f"{component!r} matches excluded class {excluded_class!r}",
                )


def check_shared_components(diagrams: dict) -> None:
    """`diagram-obligation` spec, `Requirement: Separation Check`
    (cross-diagram intersection): every PAIR of declared diagrams' component
    sets MUST NOT intersect. `diagrams` is `{figure_id: [components]}`.
    Refuses `SHARED_COMPONENT` naming the label and both diagram ids."""
    ids = sorted(diagrams)
    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1:]:
            shared = sorted(set(diagrams[left_id]) & set(diagrams[right_id]))
            if shared:
                raise Refused(
                    "SHARED_COMPONENT",
                    f"{shared} shared between {left_id!r} and {right_id!r}",
                )


def check_caption(
    figure: dict, manifest_components: list, manifest_encodings: list, caption_text: str,
) -> None:
    """`diagram-obligation` spec, `Requirement: Caption Check`: when
    `caption_enumerates`, every component MUST appear in the caption in the
    diagram's own order; when `caption_decodes`, every declared encoding
    MUST be decoded in the caption text. Either omission refuses
    `CAPTION_INCOMPLETE` naming what's missing."""
    if figure["caption_enumerates"]:
        missing = [c for c in manifest_components if c not in caption_text]
        if missing:
            raise Refused("CAPTION_INCOMPLETE", f"caption never names {missing}")
        positions = [caption_text.index(c) for c in manifest_components]
        if positions != sorted(positions):
            raise Refused(
                "CAPTION_INCOMPLETE",
                f"components appear out of the diagram's own order: {manifest_components}",
            )
    if figure["caption_decodes"]:
        undecoded = [encoding for encoding in manifest_encodings if encoding not in caption_text]
        if undecoded:
            raise Refused("CAPTION_INCOMPLETE", f"caption never decodes {undecoded}")


def check_mandatory(
    figure: dict, pdf_exists: bool, block_id: str, manifest_components: list,
) -> None:
    """`diagram-obligation` spec, `Requirement: Mandatory Diagram
    Presence`: refuses `MANDATORY_DIAGRAM_ABSENT` naming `block_id` when
    `mandatory: true` and either no compiled diagram exists, or one exists
    but declares zero components.

    The zero-components case (W2, `a-diagram-that-compiles-or-says-why`'s
    corrective re-verify, WARNING): a PDF's mere existence was the ONLY
    thing this check ever verified. Every other check in this module is
    satisfied vacuously by an empty manifest --
    `check_excluded`/`check_caption` iterate `manifest_components` and
    simply never run their own loop bodies when it is empty, and
    `check_components` does not run at all for a block with no
    `components_from`. A `mandatory: true` block with a manifest of zero
    components therefore compiled and passed every obligation check that
    existed before this fix -- an obligation any empty thing satisfies is
    not an obligation. `manifest_components` is REQUIRED, not defaulted,
    so a caller cannot silently opt back into the old, PDF-existence-only
    behaviour."""
    if figure["mandatory"] and not pdf_exists:
        raise Refused(
            "MANDATORY_DIAGRAM_ABSENT",
            f"block {block_id!r} declares figure.mandatory=true with no compiled diagram",
        )
    if figure["mandatory"] and not manifest_components:
        raise Refused(
            "MANDATORY_DIAGRAM_ABSENT",
            f"block {block_id!r} declares figure.mandatory=true, but the compiled diagram's "
            "own manifest declares zero components -- a diagram that shows nothing does not "
            "satisfy the obligation",
        )
