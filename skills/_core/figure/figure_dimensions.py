"""figure_dimensions: the visual-dimension roster and its reason-code
vocabulary, declared exactly once so the producer (`figure-review`) and
the consumer (`paper-writing`'s `audit_semantics` default) cannot drift
apart (design.md, Decision 4: "The dimension roster and reason-code
vocabulary are declared once, in a shared `skills/_core/figure/` shelf
both sides import").

Zero imports, by construction and by test: this module's AST is checked
for zero `Import`/`ImportFrom` nodes (design.md lock 12), which is what
makes the forge gate's `IMPORT_SCOPE_PATHSPECS` scan (scoped to
`skills/*/scripts/*.py`, and therefore blind to `skills/_core/figure/`)
unnecessary rather than merely absent -- a module that cannot import
anything needs no import scan. That is also why this file carries no
`from __future__ import annotations`: that statement is itself an
`ImportFrom` node.

Three tiers (`visual-finding-boundary` spec, `Requirement: Every Visual
Dimension Is Classified Into Exactly One Tier`):

    VERDICT_DIMENSIONS  -- a computed pass/fail, naming an edge or a
                            collision when it fails.
    EVIDENCE_DIMENSIONS -- a number worth reporting, carrying no verdict.
    SILENT_DIMENSIONS   -- an announced silence: unmeasured, with a
                            named reason, because the thing it would
                            answer is a judgement, not a pixel property.
"""

VERDICT_DIMENSIONS = ("out-of-bounds", "overlap")
EVIDENCE_DIMENSIONS = ("canvas-occupancy",)
SILENT_DIMENSIONS = (
    "legibility",
    "connection-correctness",
    "style-quality",
    "overlap-ownership",
)

#: Every classified dimension, in the fixed order the roster declares
#: them. `default_visual` and every consumer that iterates "every
#: dimension" reads this tuple rather than re-deriving it.
ALL_DIMENSIONS = VERDICT_DIMENSIONS + EVIDENCE_DIMENSIONS + SILENT_DIMENSIONS

#: The reason a dimension is `unmeasured` by default. `legibility`'s
#: reason is `LEGIBILITY_IS_A_THRESHOLD_JUDGEMENT` per design.md Decision
#: 7 (glyph metrics ARE measurable from the PDF's text layer; legibility
#: itself is a judgement about a reader, not a pixel property) -- the
#: same amendment `visual-finding-boundary`'s spec carries.
DEFAULT_REASONS = {
    "out-of-bounds": "RASTER_NOT_MEASURED",
    "overlap": "RASTER_NOT_MEASURED",
    "canvas-occupancy": "RASTER_NOT_MEASURED",
    "legibility": "LEGIBILITY_IS_A_THRESHOLD_JUDGEMENT",
    "connection-correctness": "VISUAL_MEANING_NOT_A_PIXEL_PROPERTY",
    "style-quality": "VISUAL_JUDGEMENT_NOT_MEASURED",
    "overlap-ownership": "UNATTRIBUTED_INK",
}


def default_visual():
    """Every classified dimension, present and unmeasured -- the shape
    `audit_semantics` returns when no caller supplies a `visual` dict
    (`diagram-obligation` spec, `Requirement: Figure-Prose Semantic
    Audit`), and the shape `figure-review`'s own `findings.py` starts
    from before it overwrites what it actually measured. Reading any
    dimension by key never raises (`visual-finding-boundary`,
    `Requirement: Every Dimension Is Always Present, Never Absent or
    Null`)."""
    dimensions = {
        name: {"verdict": "unmeasured", "reason": DEFAULT_REASONS[name]}
        for name in ALL_DIMENSIONS
    }
    return {"provenance": None, "dimensions": dimensions}
