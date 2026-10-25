---
{
  "section": "back-matter",
  "position": 10,
  "mode": {
    "value": "transposition",
    "source": {
      "file": "sections/10-back-matter.md",
      "quote": "Every block here is an external fact, not a decision."
    }
  },
  "blocks": [
    {
      "id": "bm-author-contributions",
      "requires_facts": [],
      "requires_declarations": [
        {
          "value": "author-roles",
          "source": {
            "file": "sections/10-back-matter.md",
            "quote": "The author-roles — the author list, and each author's confirmed roles"
          }
        }
      ],
      "citations": "none"
    },
    {
      "id": "bm-funding",
      "requires_facts": [],
      "requires_declarations": [
        {
          "value": "grant-title",
          "source": {
            "file": "sections/10-back-matter.md",
            "quote": "The grant-title and grant-code — the funding project's registered title, funder, and code"
          }
        },
        {
          "value": "grant-code",
          "source": {
            "file": "sections/10-back-matter.md",
            "quote": "The grant-title and grant-code — the funding project's registered title, funder, and code"
          }
        }
      ],
      "citations": "none"
    },
    {
      "id": "bm-data-availability",
      "requires_facts": [],
      "requires_declarations": [
        {
          "value": "repository-url",
          "source": {
            "file": "sections/10-back-matter.md",
            "quote": "The repository-url — the project repository URL, and the date it was checked"
          }
        }
      ],
      "citations": "none"
    },
    {
      "id": "bm-conflicts-of-interest",
      "requires_facts": [],
      "requires_declarations": [],
      "citations": "none"
    },
    {
      "id": "bm-acknowledgments",
      "requires_facts": [],
      "requires_declarations": [],
      "citations": "none",
      "optional": true,
      "after": [
        {
          "target": "back-matter.bm-funding",
          "source": {
            "file": "sections/10-back-matter.md",
            "quote": "Present only when there is a project or institution to thank that is not already named under funding."
          }
        }
      ]
    },
    {
      "id": "bm-appendices",
      "requires_facts": [],
      "requires_declarations": [],
      "citations": "none",
      "optional": true
    }
  ]
}
---
# Back Matter

The administrative block that sits after the conclusions and before the references.
It is not scientific prose — it is the paper's accountability surface: who did what,
who paid, where the data and code are, and what could bias the work.

Each block is a bold inline label followed by prose. No section headings, no
subsections. This is the most mechanical part of the paper and the most likely to be
wrong at submission, because nobody treats it as writing.

## The blocks, in this order

| Block | Required | Words |
|---|---|---|
| Author Contributions | yes | 37–44 |
| Funding | yes | 55 per project |
| Data Availability Statement | yes | 7–22 |
| Conflicts of Interest | yes | one sentence |
| Acknowledgments | only if there is a project to thank | ~25 |
| Appendices | only if the paper needs them | — |

## Author Contributions

A formula, which is why its length barely varies. The CRediT roles, semicolon
separated, each followed by the initials of the authors who held it, comma separated
with *and* before the last. Then the standing closing sentence stating that all
authors have read and agreed to the published version.

**Every author appears in at least one role.** The roles are the ones each author
confirmed, not the ones inferred from the work.

## Funding

One entry per grant. Each carries the project's **exact registered title**, in its
original language, the funder, and the grant code. When a grant supports a specific
author rather than the work as a whole, name that author with it.

Grant codes are copied from the funding records, never retyped from memory.

## Data Availability Statement

The repository URL plus the date it was checked. The URL must resolve, and it must
hold the code that produced the reported numbers.

When the data cannot be published, say so in one line and give the route to request
it. Do not point at a repository holding only code while implying it holds the data.

State what is public and what is not — they are different claims.

## Conflicts of Interest

One sentence declaring none.

The one case that needs more: when an author is affiliated with an organization with
an interest in the results — typically the one that supplied the data — name the
affiliation explicitly and repeat the declaration for that author. Silence about a
known affiliation is the failure this block exists to prevent.

## Acknowledgments

Present only when there is a project or institution to thank that is not already
named under funding. One or two sentences.

## Appendices

Used when material is necessary to reproduce the work but would break the flow of
the section that needs it — verbatim artefacts, or a full parameter table when the
experimental setup carries only the values that were reasoned about.

Lettered, with subsections numbered under their letter. **Each appendix is referenced
from the body section that needs it**; one that nothing references is dead weight.

Whether the paper has appendices at all is decided per paper.

## Inputs

Every block here is an external fact, not a decision. None of it is derived from the
paper.

### External inputs

| Input | Unblocks |
|---|---|
| The **author-roles** — the author list, and each author's confirmed roles | `bm-author-contributions` |
| The **grant-title** and **grant-code** — the funding project's registered title, funder, and code | `bm-funding` |
| The **repository-url** — the project repository URL, and the date it was checked | `bm-data-availability` |
| Any author affiliation with an interested organization | `bm-conflicts-of-interest` |
| The project or institution to thank | `bm-acknowledgments` |
| Whichever body sections need one | `bm-appendices` |

### Internal chain

| Block | Depends on |
|---|---|
| `back-matter.bm-acknowledgments` — present only when there is a project or institution to thank that is not already named under funding | `back-matter.bm-funding` — the funding entries already naming any project or institution credited there |

## Disqualifiers

- An author with no role.
- A role attributed without the author confirming it.
- A grant title or code reproduced from memory rather than copied.
- A repository URL that does not resolve, or that holds code unable to produce the
  reported numbers.
- A missing access date on the URL.
- A data availability statement claiming public data that is not public.
- A known interested affiliation left undeclared.
- An appendix that no body section references.
- Appendix content that contradicts the experimental setup.
