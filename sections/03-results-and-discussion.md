---
{
  "section": "results-and-discussion",
  "position": 7,
  "mode": {
    "value": "argument",
    "source": {
      "file": "sections/03-results-and-discussion.md",
      "quote": "The discussion is inferential by default and assertive by exception."
    }
  },
  "blocks": [
    {
      "id": "rd-general-task",
      "requires_facts": [
        {
          "value": "results",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "The results — the main runs, against the baselines"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "resolution"
    },
    {
      "id": "rd-contribution-blocks",
      "requires_facts": [
        {
          "value": "contributions",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "The property a contribution promised, and the instrument the setup named for it"
          }
        },
        {
          "value": "results",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "Input the results of the experiments"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "resolution",
      "after": [
        {
          "target": "results-and-discussion.rd-general-task",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "A mechanism block opens by naming the previous block's result as the question it comes to answer."
          }
        },
        {
          "target": "materials-and-methods.mm-proposal",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "The property a contribution promised, and the instrument the setup named for it"
          }
        }
      ]
    },
    {
      "id": "rd-cost",
      "requires_facts": [
        {
          "value": "results",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "Input the results of the experiments"
          }
        },
        {
          "value": "implementation",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "The implementation — the most demanding configuration, and the hardware declared in the setup"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "none",
      "optional": true,
      "after": [
        {
          "target": "results-and-discussion.rd-contribution-blocks",
          "source": {
            "file": "sections/03-results-and-discussion.md",
            "quote": "A mechanism block opens by naming the previous block's result as the question it comes to answer."
          }
        }
      ]
    }
  ]
}
---
# Results and Discussion

**Extent** 1170–4150 words · two or three content blocks, plus limitations last
**Input** the results of the experiments
**Carries** 5–14 figures and 0–4 tables — the artefact-densest section of the paper
**Does not carry** a preamble, a closing artefact, or a single numbered equation

## One section, never two

The discussion is not a block. There is no separate stretch of discussion prose: the
discussion is **the third beat of every artefact reading, in the same paragraph as
the number it explains**. That is why the two are one section and why they cannot be
split.

## The blocks

**1. The general task.** The evidence that the proposal works on the task it was
built for: the main metric, on the main data, against the baselines. This block
carries the bulk of the section — 40% to 66% of it.

**2. One block per contribution.** Each validates the property that contribution
promised, using the instrument the experimental setup named for it.

**3. Cost, when cost is claimed.** One or two paragraphs, one figure. Measured on the
most demanding configuration, and stated as such so the estimate reads as
conservative.

**4. Limitations.** Last, always, under its own contract.

### Organizing by scenario instead

When the work has dissimilar experimental scenarios — different domains, different
data regimes — the blocks may be organized one per scenario, each walking
performance-then-mechanism internally. **The correspondence to the contributions is
still stated**, so the reader knows which block validates which contribution.
Organizing by scenario without saying that is what loses the correspondence.

## The chain that ends here

> **problem *i* → contribution *i* → property *i* → instrument *i* → evidence *i***

The problem was declared in the problem statement, the gap said nobody had resolved
it, the contribution answers it, the setup named the instrument that measures it, and
this section is where the evidence appears. **The property carries the same name
through all five links** — not a synonym, the same words.

The obligation runs both ways:

- **every contribution has a block here**, and
- **every block here belongs to a contribution or to the general task.**

A block belonging to neither is a measurement nobody asked for.

## How a result is presented

The form is the same for a figure and for a table. Two syntactic positions:

**The artefact as grammatical subject**, followed by a reading verb and what it
shows.

**The artefact as a pointer inside the claim** — the form used whenever there is a
value:

> **[the claim in words] + [the value in parentheses] + [the pointer to the artefact]**

**The pointer resolves to the exact sub-element, not to the artefact as a whole.**
When an artefact has parts — panels, columns, row bands, sides, shaded regions — the
pointer names the part. Sending the reader to a whole artefact to find one number is
sending them to look for it.

**The reading verbs are a closed set with a gradient.** Neutral ones say the artefact
displays something: *presents, shows, illustrates, depicts, provides*. Assertive ones
say it establishes something: *reveals, demonstrates, confirms, identifies*. Use the
assertive form only when the artefact settles the point.

## Every artefact is referenced before it appears

Any numbered object — figure, table, or panel — is referenced in the body **before**
it appears. Without exception.

The diagnostic value is the point: **an artefact that appears with no prior reference
is either misplaced or dead.** Applying this rule is how a figure that nothing in the
paper points at gets found.

## The three-beat move

Per artefact: **point at it → read it in numbers → give the mechanism.** All three, in
that order, in the same paragraph. The third beat is what separates reporting from
explaining.

**A number in prose comes with its pointer.** Prose never introduces a value that no
artefact shows.

## The discussion: three registers

The third beat comes in three registers, and they are not interchangeable.

| Register | Share | Form | When |
|---|---|---|---|
| **Inferential** | ~57% | *indicates, suggests, is consistent with, reflects* | the mechanism is inferred from the pattern |
| **Assertive** | ~30% | *because, due to, stems from, is attributed to* | the mechanism is a known property of the formulation or of the data, not an inference from the result |
| **Corroborative** | ~13% | *confirms, reinforces* | the result agrees with an earlier block or with established behaviour |

**The discussion is inferential by default and assertive by exception.** Two out of
three explanations say what the number is *consistent with*, not what *caused* it. A
discussion written entirely in the assertive register is claiming causal knowledge
the experiment did not produce.

**It is anchored.** The explanation sits in the same paragraph as the number it
explains. It never floats.

**It chains between blocks.** A mechanism block opens by naming the previous block's
result as the question it comes to answer.

**The concession belongs to the discussion.** Where a competitor wins a sub-criterion,
say so, and say what the loss buys.

**Three things the discussion does not do:** introduce a claim no artefact supports;
restate the number in words without adding a mechanism; or jump to implications for
practice — that belongs to the conclusions.

## When a contribution has no competitor

Some contributions have nothing to be compared against, because nothing else does
that thing. Three moves, in order:

1. **Project down to a shared space where comparison is possible**, and show
   **parity** there — parity, not superiority. If the contribution operates over more
   dimensions than any competitor, reduce it to the dimension they share and show it
   holds up.
2. **Show what only this contribution produces** — the part no competitor can be
   measured on. There is no comparison there because there is nothing to compare
   with, and that absence is the argument.
3. **If the parity is in fact a loss, concede it and state what is bought with it.**

**The guard:** a conceded loss is paired with a **measured** gain, not an asserted
one. Both point at an artefact. *We lose here but we are better there* holds only if
*there* has its own reported cell. Without this guard, any unfavourable result can be
recycled as a virtue.

**And the deficiency still goes to limitations as an item.** Justified here it reads
defensive; declared there it reads honest, and only there can it earn a future-work
direction.

## The artefact type follows the claim

A grid of numbers is a table. A spatial, temporal, or spectral pattern is a figure.
This is not a stylistic preference: a block whose claim is a comparison across cells
takes tables and may carry no figure at all, while a block whose claim is a pattern
takes figures and may carry no table.

## Citations

Almost none — and never for a result. A citation here credits **an instrument** used
to read the data, or a **behaviour already established** that the result agrees with.

## Inputs

### External inputs

| Input | Unblocks |
|---|---|
| The **results** — the main runs, against the baselines | `rd-general-task` |
| The **implementation** — the most demanding configuration, and the hardware declared in the setup | `rd-cost` |

### Internal chain

| Block | Depends on |
|---|---|
| `results-and-discussion.rd-contribution-blocks` — a mechanism block opens by naming the previous block's result as the question it comes to answer | `results-and-discussion.rd-general-task` — the general task's evidence, the block immediately before it |
| `results-and-discussion.rd-contribution-blocks` — The property a contribution promised, and the instrument the setup named for it | `materials-and-methods.mm-proposal` — the enumerated contributions each property traces to |
| `results-and-discussion.rd-cost` — a mechanism block opens by naming the previous block's result as the question it comes to answer | `results-and-discussion.rd-contribution-blocks` — the per-contribution validation, the block immediately before cost |

### Structural decisions

- **Each artefact** depends on the runs, and the experimental setup's closing
  diagram must be able to locate it — a rule cutting across every block here,
  not a dependency on one specific block.
- **The third beat** (the mechanistic explanation) draws on the formulation,
  or on a property of the data — again cutting across every block, not
  naming one.
- **Limitations** lives in its own section, under its own contract — it is
  not a block of this section and carries no dependency on it.

## Disqualifiers

- A numbered equation.
- A preamble, or a closing summary artefact.
- A block that opens on prose with no artefact reference.
- An artefact that appears before any reference to it, or that nothing references at
  all.
- A pointer to a whole artefact when the value is in one of its parts.
- A number in prose that appears in no artefact.
- An artefact that cannot be located in the experimental setup's closing diagram —
  a reported cell the design never declared.
- A claim of improvement without the baseline it improves on, in the same artefact.
- A contribution with no block here.
- A block belonging to neither a contribution nor the general task.
- A property named here under a different name than the problem statement, the
  contribution, or the instrument gave it.
- A block organized by scenario without stating which contribution it validates.
- An artefact reading with no third beat — the number stated and never explained.
- A discussion written entirely in the assertive register.
- An explanation placed in a different paragraph from the number it explains.
- A conceded loss paired with an asserted gain instead of a measured one.
- A deficiency justified here and absent from limitations.
- A citation credited to a result.
- A table used for a pattern, or a figure used for a comparison grid.
- Limitations placed anywhere but last.
- Interpretation of a result no artefact contains.
