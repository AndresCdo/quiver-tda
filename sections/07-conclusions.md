---
{
  "section": "conclusions",
  "position": 9,
  "mode": {
    "value": "transposition",
    "source": {
      "file": "sections/07-conclusions.md",
      "quote": "They add nothing — every claim here already exists earlier, in more detail."
    }
  },
  "blocks": [
    {
      "id": "concl-block-1",
      "requires_facts": [
        {
          "value": "contributions",
          "source": {
            "file": "sections/07-conclusions.md",
            "quote": "The contributions, as defined — same count, order, and names as the introduction and the methods section"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "none",
      "after": [
        {
          "target": "materials-and-methods.mm-proposal",
          "source": {
            "file": "sections/07-conclusions.md",
            "quote": "The contributions, as defined — same count, order, and names as the introduction and the methods section"
          }
        }
      ]
    },
    {
      "id": "concl-block-2",
      "requires_facts": [
        {
          "value": "results",
          "source": {
            "file": "sections/07-conclusions.md",
            "quote": "The results, and the number of experimental scenarios, which decides one paragraph or two"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "none"
    },
    {
      "id": "concl-block-3",
      "requires_facts": [],
      "requires_declarations": [],
      "citations": "none"
    },
    {
      "id": "concl-block-4",
      "requires_facts": [
        {
          "value": "limitations",
          "source": {
            "file": "sections/07-conclusions.md",
            "quote": "The limitations, which it is the relevant subset of, and one reference per direction"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "resolution",
      "after": [
        {
          "target": "limitations.lim-proposal-items",
          "source": {
            "file": "sections/07-conclusions.md",
            "quote": "The limitations, which it is the relevant subset of, and one reference per direction"
          }
        }
      ]
    }
  ]
}
---
# Conclusions

**Extent** 375–500 words · 3 or 4 paragraphs
**Does not carry** equations, figures, or tables
**Carries** citations in one place only: the future-work block

The conclusions are read by people who will not read the paper. They must stand
alone. They add nothing — every claim here already exists earlier, in more detail.

## Four functional blocks

| Block | Paragraphs | Words |
|---|---|---|
| 1 — The proposal and its components | 1, always the first | 60–226 |
| 2 — The results recap | 1 or 2 | 100–180 each |
| 3 — The consequence beyond the method | own paragraph, or the close of block 2 | ~50–120 |
| 4 — Future work | 1, always last | 55–180 |

Blocks 2 and 3 may share a paragraph; blocks 1 and 4 never merge with anything.

## Block 1 — The proposal and its components

Past tense. Full name, acronym, and the category of the artefact. Then the N
components restated, in one of three forms:

- **`First / Second / Third`** as separate sentences, after announcing the count;
- **an inline list** inside a single sentence — the most compact form;
- **prose with connectives** — *integrating A … the incorporation of B allows … 
  furthermore C*.

**Same count, same order, same names** as the introduction's contribution list and
the methods section's subsections.

**Close on what distinguishes the method from its alternatives** — the property, not
the number. What it does not require, what it does not need modified, what it does
not depend on.

## Block 2 — The results recap

Named competitors, named axes, and the specific finding with the conditions under
which it held.

**One or two paragraphs, and the number of experimental scenarios decides.** Two
dissimilar scenarios take one paragraph each. A single scenario may still split into
result and mechanism — what the numbers were, and what the pattern was consistent
with.

**Figures are permitted, with dispersion, but they are not the norm.** Quote a value
only when the value is the point; otherwise stay in comparatives. A quoted figure
must match the results section exactly.

## Block 3 — The consequence beyond the method

What the reader takes away, past the fact that the method worked. Not a result and
not a contribution — a consequence. It answers *so what*.

Two flavours; the paper picks by whose problem it is:

- **For whoever implements it** — the cost of adoption is low: nothing needs
  modifying, the architecture drops into existing pipelines, prediction time falls.
- **For whoever lives the problem** — something becomes possible that was not: the
  factor behind a prediction can be traced back, the decision path is auditable where
  regulation demands it.

It may be its own paragraph or the closing sentences of block 2. It is the only part
of the section that speaks to someone outside the sub-field.

## Block 4 — Future work

Always last. **The only block in the section that cites** — one reference per
direction, showing the direction is live in the literature. Everything before it
cites nothing.

**Future work is the relevant subset of the limitations, with a reference per
direction.** Each direction answers a stated limitation.

**The reduction goes one way only.** A limitation may be left without a direction —
not everything is meant to be repaired. But no direction is left without a limitation
motivating it: **a direction with no corresponding limitation means the limitation
was never declared**, not that the direction is unnecessary. Fix it by declaring the
limitation, not by dropping the direction.

That is what makes the coupling between the two sections checkable.

Each direction is specific enough to be a paper — an extension named, not a hope.
The block closes on the applicability those directions would widen.

## Optional

**A scope caveat.** When the results could be read as a finding about the domain
rather than about the model, say which one they are. This carries the same
attribution discipline as a quoted figure: state what the claim belongs to.

## Inputs

Everything except the abstract must exist. The abstract is written after this
section, because it compresses it.

### External inputs

| Input | Unblocks |
|---|---|
| The **results**, and the number of experimental scenarios, which decides one paragraph or two | `concl-block-2` |

### Internal chain

| Block | Depends on |
|---|---|
| `conclusions.concl-block-1` — The contributions, as defined — same count, order, and names as the introduction and the methods section | `materials-and-methods.mm-proposal` — the enumerated contributions restated here |
| `conclusions.concl-block-4` — The limitations, which it is the relevant subset of, and one reference per direction | `limitations.lim-proposal-items` — the swept limitations this block draws its relevant subset from |

Block 3's own placement — its own paragraph or the close of block 2 — is a
placement option (see Structural decisions), not a content derivation from
block 2's own prose, so `concl-block-3` carries neither an external input nor
an internal-chain row.

### Structural decisions

- **Block 3 — the consequence beyond the method** is chosen by whose problem
  it is: the implementer's or the domain's — an authorial decision, not a
  fact fetched from data or a dependency on a sibling block.

## Disqualifiers

- A claim, number, or property that appears nowhere earlier in the paper.
- A component list disagreeing with the introduction or the methods section in count,
  order, or naming.
- Block 1 not first, or block 4 not last.
- Block 1 closing on a number instead of on the distinguishing property.
- A quoted figure that does not match the results section exactly.
- A future-work direction that answers no stated limitation.
- A citation anywhere outside the future-work block.
- A future-work direction with no reference.
- A future-work direction too vague to be a paper.
- An equation, a figure, or a table.
- Limitations developed here instead of in the results section.
- Over 500 or under 375 words.
- A section that cannot be read without having read the paper.
