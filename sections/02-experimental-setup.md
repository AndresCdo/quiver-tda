---
{
  "section": "experimental-setup",
  "position": 6,
  "mode": {
    "value": "transposition",
    "source": {
      "file": "sections/02-experimental-setup.md",
      "quote": "Nothing here is discovered: every condition this section states was already fixed when the experiments ran."
    }
  },
  "blocks": [
    {
      "id": "es-preamble",
      "requires_facts": [],
      "requires_declarations": [],
      "citations": "none"
    },
    {
      "id": "es-dataset",
      "requires_facts": [
        {
          "value": "dataset",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "The dataset — when this section owns it"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "resolution",
      "optional": true
    },
    {
      "id": "es-assessment",
      "requires_facts": [
        {
          "value": "contributions",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "Which property each contribution claims — if it was promised, this is where its instrument is named"
          }
        },
        {
          "value": "experimental-design",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "The experimental design — the competing methods, the axes, and the purpose-built corpus criteria settled as one comparison protocol"
          }
        },
        {
          "value": "gap",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "The gap — that no standard reference measures what is claimed, which is why the purpose-built corpus exists"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "resolution",
      "after": [
        {
          "target": "experimental-setup.es-dataset",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "Its one dependency that is NOT internal is the data it must show entering, which live in `es-dataset` when the dataset belongs to this section"
          }
        },
        {
          "target": "materials-and-methods.mm-proposal",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "Which property each contribution claims — if it was promised, this is where its instrument is named"
          }
        },
        {
          "target": "introduction.block-3",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "The gap — that no standard reference measures what is claimed, which is why the purpose-built corpus exists"
          }
        },
        {
          "target": "related-work.rw-closing",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "The gap — that no standard reference measures what is claimed, which is why the purpose-built corpus exists"
          }
        }
      ],
      "figure": {
        "ordered": false,
        "excludes": ["internal component of the proposal"],
        "caption_enumerates": true,
        "caption_decodes": false,
        "mandatory": true
      }
    },
    {
      "id": "es-training-details",
      "requires_facts": [
        {
          "value": "implementation",
          "source": {
            "file": "sections/02-experimental-setup.md",
            "quote": "The implementation of the experiments and its configuration — what actually ran"
          }
        }
      ],
      "requires_declarations": [],
      "citations": "none"
    }
  ]
}
---
# Experimental Set-Up

**Extent** 1020–4140 words · a preamble and two subsections
**Carries** the metric definitions, the compared methods, and one closing diagram
**Does not carry** any result

This section answers *would I get your numbers if I ran this myself*. It turns the
method into a protocol: what is measured, what it is measured against, and under
exactly what conditions. Every number in the results section must trace to something
declared here.

The methods section says what the model **is**. This one says what was **done** to it. Nothing here is discovered: every condition this section states was already fixed when the experiments ran.

## The two subsections split design from execution

**Assessment and Method Comparison is the design of the comparison. Training Details
is its execution.** Everything answering *what is measured and against what* is
design. Everything answering *with which values and on which machine it ran* is
execution. They are the same thing before and after running.

The section has two subsections. When the datasets do not belong to the methods
section, they are the first block of Assessment rather than a third subsection.

## Preamble

One paragraph of 33–41 words, no citations. It names the blocks the section
specifies, in order.

## Subsection 1 — Assessment and Method Comparison

Seven blocks. The first and the last two are conditional.

**1. The datasets** — only when the methods section does not own them. First.

**2. The announcement of the split** — when the framework has two dissimilar halves.
Each half then makes its own pass through the blocks that follow.

**3. The comparison axes.** The architectures, backbones, or variants over which the
comparison is swept, each with its structure table — layers, shapes, parameter counts
— and its citation. The axis is as much part of the protocol as the metric.

**4. The competing methods.** One list item each, one citation each, and where
possible **its own defining equation**. Do not merely name a baseline: formalize it.
A competitor written as an objective leaves no doubt about which version was run.

**5. The quantitative metrics.** Each defined by a numbered equation, with its symbol
glossary immediately **after** the equation, not before. This is the
equation-densest place in the paper outside the methods section, and every equation
here is a metric definition.

**Each instrument is named under the property it measures**, using the same words
the problem statement and the contribution used for that property. A synonym breaks
the chain that runs from the problem to the evidence.

**6. The qualitative or complementary instruments.** The visualization or attribution
techniques that support the claims no metric measures, each with its citation. These
are what answer the properties a contribution promised and a metric cannot reach.

**7. The purpose-built evaluation corpus** — only when no standard reference measures
what is claimed. Describe it here: its size, its composition, and a table of
examples. Without it the metric for that half means nothing.

### What is cited here

**One citation per compared object.** One per competing method, one per axis or
architecture swept, one per qualitative instrument, and one per **non-standard**
metric.

**Standard metrics carry an equation, not a citation.** The same asymmetry as the
methods section: what is borrowed is cited, what is conventional is defined.

## Subsection 2 — Training Details

The reproducibility block. Past tense, passive for procedure. Six slots.

**1. Preprocessing and exclusions.** What was filtered, discarded, or resampled, and
why. State what was thrown away before stating what was kept.

**2. The partition protocol.** The splits, the cross-validation strategy, the
stratification.

**3. The optimizer and the schedule.**

**4. The hyperparameter search.** The tool, the sampler, **the seed**, the objective
being minimized, and the search range per model. Naming the seed and the pruner's
settings is the level at which a run becomes reproducible.

**5. Leakage control.** One explicit sentence stating that everything requiring a
reference used information from the training partition only.

**6. Software and hardware.** Language version, framework version, library versions,
the environment, and the accelerator by model — mandatory whenever timing is reported
anywhere.

**A value comes with the reason it is that value.** Bounds established empirically
are stated with what the bound guarantees. The form of an objective is justified in
the methods section; a value inside a fixed form is justified here.

**Every knob traces back.** A hyperparameter named here must be a symbol declared in
the methods section.

**The full parameter table may go to an appendix**, keeping in the body only the
values that were reasoned about. That is the correct use of an appendix: the body
carries what has a reason, the appendix carries what must be consultable.

## Every artefact is referenced before it appears

Any numbered object — figure, table, or panel — is referenced in the body **before**
it appears, and the pointer resolves to the exact sub-element when the artefact has
parts. An artefact appearing with no prior reference is either misplaced or dead.

## Figures and tables here are protocol, never results

Nothing in this section reports a performance. Its figures illustrate the protocol —
the schedule that was used, the spectrum of the input, the structure of the design —
and its tables carry the architectures of each axis and the parameter values.

## The closing diagram

The section closes on one diagram, and **it is the handoff to the results section**.
What the reader must carry forward is the crossing, not the values: the values are
looked up when needed, the crossing has to be held in mind to read a results table.

It shows:

- which data enter;
- against which methods the comparison runs;
- over which axes it is swept;
- which metric comes out of each crossing;
- where the qualitative instruments attach;
- **the repetition unit** — what a single reported number is an average over, and
  what its dispersion is computed across.

The proposal is one row of the crossing, not the centre of the figure.

That repetition unit is the only element of execution admitted into the diagram.
Without it a cell of the diagram cannot be read as a cell of a table. Everything else
about execution stays in Training Details, which is where it gets consulted.

**Its obligation to the results section:** every table and every figure there must be
locatable in this diagram. A reported cell the diagram does not contain is a cell the
design never declared.

**Separation from the methods diagram.** The methods diagram shows the method; this
one shows the experiment. The test: **no dataset and no baseline appears in the
methods diagram, and no internal component of the proposal appears in this one.** A
box appearing in both means one of them is wrong.

## Inputs

### External inputs

| Input | Unblocks |
|---|---|
| The **dataset** — when this section owns it | `es-dataset` |
| The **competing methods** — the baseline list settled in the state of the art | `es-assessment` |
| The **axes** — what the comparison is swept over | `es-assessment` |
| The **purpose-built corpus** — that no standard reference measures what is claimed | `es-assessment` |
| The **experimental design** — the competing methods, the axes, and the purpose-built corpus criteria settled as one comparison protocol | `es-assessment` |
| The **implementation** of the experiments and its configuration — what actually ran | `es-training-details` |

### Internal chain

| Block | Depends on |
|---|---|
| `experimental-setup.es-assessment` — the closing diagram's "which data enter" panel | `experimental-setup.es-dataset` — the dataset block, when this section owns it |
| `experimental-setup.es-assessment` — Which property each contribution claims — if it was promised, this is where its instrument is named | `materials-and-methods.mm-proposal` — the enumerated contributions the instrument is named for |
| `experimental-setup.es-assessment` — The gap — that no standard reference measures what is claimed, which is why the purpose-built corpus exists | `introduction.block-3` — the joint gap, condensed there |
| `experimental-setup.es-assessment` — The gap — that no standard reference measures what is claimed, which is why the purpose-built corpus exists | `related-work.rw-closing` — the joint gap, developed there |

### Structural decisions

- **How many blocks Assessment has** is decided by the dataset placement
  already decided in the methods section — a structural decision, not a
  dependency on a specific block.
- **The closing diagram** is the crossing declared by everything Assessment
  already carries, plus the repetition unit — an internal composition rule
  within `es-assessment` itself. Its one dependency that is NOT internal is
  the data it must show entering, which live in `es-dataset` when the
  dataset belongs to this section; that one is a chain row above, not a
  structural decision.

## Disqualifiers

- A metric named but not defined.
- A metric glossary placed before its equation instead of after.
- A citation on a standard metric, or a missing citation on a non-standard one.
- A competing method named without a citation, or named without being formalized
  where a formalization exists.
- An axis swept without its structure declared.
- A property claimed by a contribution with no instrument named here.
- An instrument named under a different name than the property it measures carries in
  the problem statement and the contribution.
- An artefact that appears before any reference to it, or that nothing references at
  all.
- A pointer to a whole artefact when the value is in one of its parts.
- A purpose-built corpus used without being described.
- A hyperparameter with no value, or a value disagreeing with the configuration that
  ran.
- A knob that does not exist in the methods section.
- A seed, split, or repetition count omitted.
- Hardware omitted while timing is reported.
- No leakage-control statement.
- A result, a measured comparison, or a performance figure.
- The closing diagram missing.
- A results table or figure that cannot be located in the closing diagram.
- A box shared between the closing diagram and the methods diagram.
- Any element of execution in the closing diagram other than the repetition unit.
- The full parameter table in the body when only some values were reasoned about, or
  an appendix table contradicting the body.
