---
name: paper-ingestion
description: "Trigger: ingest reference PDFs into high-fidelity Markdown (LaTeX equations, Markdown tables, figures as files) using Marker, locally and keyless. One folder per paper: pdf + lean .md + figure images."
---

# Paper Ingestion

Convert each source PDF into a lean, high-fidelity Markdown file an agent can
read directly — body text in reading order, equations as LaTeX, tables as
Markdown. Each paper becomes a **self-contained folder**: `pdf + md + figure
images`. Figures are separate image files the `.md` references (loaded on demand,
not embedded), and the references/bibliography section is dropped. Runs locally
with no API keys.

**PDFs only.** Neither this skill nor `papersmith ingest` (its workspace
bridge) reads Markdown, text or HTML; `papersmith ingest` refuses any other
source and names the two routes that do. Material that is already text goes
through `proposal-deliberation` instead: Markdown a new proposal should be
seeded from goes under `guidance/paper-guide/` (`CREATE_INITIAL_REVISION`
reads it), and an existing draft that should become v1 as written goes into
`proposals/` and is adopted with `ADOPT_INITIAL_REVISION`.

## The objective flow

**Why this skill was invoked, and where it has to arrive.** Declared here and in
`OBJECTIVE_FLOW`, held equal by a test, and independent of what is on disk. A
listing of what has been ingested answers *where am I*; this answers *what is
this for*, which no listing implies. The one path a refusal takes carries it.

**Purpose:** turn a paper into the form it can actually be used in — equations
as LaTeX, tables as tables, figures as files — not a PDF that was processed.

| Stage | Establishes | Behind you when |
| --- | --- | --- |
| `filed` | The PDF sits inside a topic folder of its own, which is what makes it a paper rather than a download | it is no longer reported among the unfiled |
| `extracted` | The Markdown exists beside it, with its figures written as files rather than left inside the page | the paper folder holds the document and its images |
| `readable` | The equations are LaTeX and the tables are Markdown, so a later reader can quote a formula rather than describe a picture of one | this is the arrival; it is behind nobody |

**Arrival:** a document a person can read and a later session can cite, which a PDF is not.

**Arrival is an artefact somebody can read and cite, never a PDF that was
processed.** That distinction is this skill's whole reason to exist: a PDF is
already on disk and already unusable as evidence — its equations are pictures,
its tables are ink, and nothing downstream can quote it.

**No stop here is a person's**, and the list says so by being empty rather than
absent: ingestion asks nobody, and a reader meeting a missing key would have to
guess whether that meant none or meant nobody wrote it down.



## What this skill delegates, and to whom

Extraction is one stretch and it runs in an agent of its own. What stays in the
conversation is the part that needs a person: which loose PDFs are unfiled, and
what the report says afterwards.

| Stretch | Delegated to | Begins after | Ends at | Measure this before delegating |
| --- | --- | --- | --- | --- |
| Extract | this skill delegates to the `paper-ingestion` agent | the PDFs to ingest are named | the artefacts a person can read and cite | each named PDF sits inside a topic folder of its own; a loose one is the operator's to file and not this stretch's to guess at |

What moves is execution, never doctrine: every rule stays here, and the agent's
first instruction is to load this file.

## When a delegated agent cannot be spawned

The stretch this skill delegates is defined in full by its agent file:
`.claude/agents/paper-ingestion.md`. When that agent cannot be spawned — the
harness has no sub-agent mechanism, the agent is not registered in this
session, or the spawn itself fails — perform the stretch inline: read the
definition file and follow it as written, from the beginning it states to the
end it states, holding any gate this skill sets before the stretch, and returning the
report shape it specifies. Its `tools:` line still bounds the stretch: an act
that would need a tool outside that list is a stop, not a workaround. Say in
the reply that the stretch ran inline and why the agent could not be spawned.

## Activation Contract

Accept an optional loose PDF path, or discover the source roots from
`papersmith.yaml` and scan them. Validate configuration before doing any work.
Extraction is performed by the bundled script running inside the skill's
dedicated virtualenv.

## Environment (one-time)

The engine (Marker + torch + surya) lives in an isolated micromamba environment
(`papersmith`) so it never pollutes system Python. A new machine is provisioned
with one idempotent command that works on macOS, Linux, and Windows:

```
python scripts/setup_env.py install
# or, on macOS/Linux: ./skills/paper-ingestion/setup.sh
```

The provisioner installs both dependency kinds a `requirements.txt` alone cannot:

- **Python deps** (`requirements.txt`): `marker-pdf`, `PyYAML`, and the ML stack
  they pull in — plus `pytorch`/`torchvision`, `numpy`, `pymupdf`, `jsonschema`,
  and `kagglesdk` from conda-forge.
- **System binary**: `llama-server` (the surya-ocr OCR backend) from conda-forge's
  `llama.cpp` package — no Homebrew needed. This is **not** a pip package, so it
  can never live in `requirements.txt` — the setup script is what makes it
  reproducible.

The script detects the hardware and installs the matching PyTorch build:
`pytorch-gpu` when an NVIDIA GPU is present, `pytorch-cpu` otherwise. Override the
choice with `--cpu` or `--cuda`. Skip the ingestion engine with `--no-ingestion`,
and tear everything down with `python scripts/setup_env.py clean` (`--full`
also removes the bootstrapped micromamba).

Requirements: Python 3.10+ to run the provisioner itself; micromamba is
downloaded automatically if missing.

**No `.env` / no keys.** Ingestion is fully keyless — the only runtime env var,
`PYTORCH_ENABLE_MPS_FALLBACK=1` (Apple Silicon), is set by the script itself. To
point at a llama.cpp outside the environment, export `LLAMA_CPP_BINARY`.

## How to execute

Always invoke through the environment:

```
micromamba run -n papersmith python \
  skills/paper-ingestion/scripts/extract_pdf.py [--list] [--mode {fast,balanced}] [--force-ocr] [<loose-pdf>…]
```

- `--list`: report the pending loose PDFs and exit. Loads no model, moves no file.
- No argument: discover the source roots, then ingest every **loose** PDF in them.
- `<loose-pdf>…`: ingest exactly those loose PDFs.
- `--file <pdf> --into <topic>`: file one unfiled PDF into a topic folder under the
  base, creating it when new. Moves one file, converts nothing, loads no model.
- `--mode {fast,balanced}`: override the configured `mode` for this run.
- `--force-ocr`: OCR every page instead of reading the PDF's text layer, for this
  run. See [Tables from a poor text layer](#tables-from-a-poor-text-layer).

## Confirmation (required)

**Never ingest without asking first.** Ingestion *moves* the user's PDFs, so
discovery and execution are two separate steps:

1. Run with `--list`. This is free — it loads no model, so asking costs nothing.
2. Report what was found: each paper's path and page count.
3. Ask the user **which papers to ingest**, as a multi-select over the listed
   PDFs. Never assume the whole batch is wanted; a PDF may be sitting in a
   source root by accident, and ingesting it displaces it.
4. Run again passing only the approved paths as arguments. If the user approves
   nothing, stop and ingest nothing.

Running with no argument ingests everything unattended and therefore skips the
user's decision — use it only when the user has explicitly asked for exactly
that. The one loose PDF case is not an exception: one paper still gets moved,
so one paper still gets confirmed.

## A PDF in the base belongs to no topic yet, and nothing files it for you

The base's children are topics. A PDF dropped in the base itself, beside those
folders rather than inside one, is pending and invisible at the same time:
discovery only promotes children, so nothing finds it and the run reports that
every paper is already in its folder.

The script reports these separately and **ingests none of them**. Converting one
where it lies would make it a topic of its own, and the next run would read that
folder as already ingested and leave it there permanently — a stray paper turned
into a permanent category, silently.

So it is a question, not a default:

1. Report each unfiled PDF with its page count, and the topics that exist now.
2. **Ask which topic it belongs in** — one of the existing ones, or a new one
   whose name the user gives. Never pick for them: the topics are the user's
   filing system and the paper's subject is not something to infer from a
   filename.
3. Run `--file <pdf> --into <topic>` with the answer. The PDF lands loose inside
   that topic, which makes it ordinary pending work.
4. Then the normal confirmation applies — filing is not ingestion, and moving a
   paper into a folder never authorizes converting it.

If the user does not want to file it, leave it. It stays reported on every run,
which is the correct end state for a decision nobody has made yet.

**Loose PDF = not yet ingested.** A PDF sitting directly in a source root is
pending; once ingested it lives inside its own `<stem>/` folder, so it is no
longer loose and is skipped. To re-ingest, delete the paper's folder (leaving the
PDF loose) and run again — that deletion is the only forced re-ingestion path,
because an existing non-empty `<stem>/` folder is refused rather than merged
into.

First run downloads the Surya layout/OCR models (~1–2 GB), cached thereafter.

## Failure Semantics

Ingestion is **transactional per paper**. Conversion runs in a staging directory
beside the paper and the PDF is moved in only once its `.md` and figures exist.
A paper that fails to convert stays **loose**, so the next run retries it — a
failure never leaves a PDF stranded in a folder with no `.md`, which the next
run would read as "already ingested".

Exit codes: `0` success or nothing to do, `1` at least one paper failed (the
rest were still ingested), `2` configuration, argument, or environment error —
nothing was touched.

## Output Contract

For a loose `<root>/foo.pdf`, produce `<root>/foo/` containing:

- `foo.pdf` — the source PDF, moved in.
- `foo.md` — lean Markdown: text, LaTeX equations, Markdown tables. The
  references/bibliography section is stripped. Figures are **referenced**
  (`![](_page_4_Figure_2.jpeg)`), not embedded.
- the figure image files the `.md` references, flat in the same folder.

No `normalized/`, no base64, no manifest.

## Configuration (`papersmith.yaml`)

```yaml
paper_ingestion:
  engine: marker
  mode: fast              # fast (CPU/MPS) | balanced (highest fidelity, GPU-oriented)
  strip_references: true  # drop the references/bibliography section at the end
  force_ocr: false        # optional: OCR every page, never read the PDF's text layer
  source_base: guidance   # source roots are discovered under here, every run
  source_roots: []        # optional: extra roots outside source_base
```

## Source Root Discovery

Source roots are **rediscovered on every run**. A folder directly under
`source_base` becomes a source root when it holds at least one loose PDF. So
adding a new category of papers (e.g. a `guidance/datasets/` folder for papers
describing the research dataset) is just: create the folder, drop the PDFs in,
run. No configuration edit.

Two boundaries make that safe:

- **A loose PDF is required.** Ingestion *moves* files. Requiring a PDF you put
  there yourself is what keeps an unrelated folder under the base from ever
  being touched.
- **Exactly one level down.** A folder nested inside a source root is never
  scanned, because a subfolder means "paper already ingested". `guidance/` itself
  is a container of roots, not a root: loose PDFs sitting directly in it are
  ignored.

A folder holding only already-ingested papers is not a new root — its PDFs are
not loose — and is correctly left alone.

`source_roots` still works for roots that live outside `source_base`; explicit
entries are added to whatever was discovered. A `source_base` that is not a
folder is a configuration error, not an empty discovery.

## Fidelity & Verification

This skill **interprets** content for maximum fidelity — it reconstructs
equations as LaTeX and tables as Markdown cells. That interpretation can be
wrong (a misread digit, a garbled symbol). The source PDF sits in the same
folder as the `.md`: verify anything load-bearing against it. Prefer `balanced`
mode when fidelity matters more than speed.

### Tables from a poor text layer

In **both** modes Marker rebuilds a digital table from the PDF's own text layer
(`tables_pdftext`) and falls back to OCR only when its reconstruction scores low.
A text layer that is present but poor — split ligatures, interleaved columns, a
broken font map — therefore yields a table that is confidently wrong, and
switching `mode` does not avoid it. `--force-ocr` (or `force_ocr: true` in the
configuration, for every run) hands Marker its `force_ocr` option: no text layer
is extracted, and every page, tables included, is rebuilt by OCR. It is slower and
off by default, because a good text layer is exact and OCR is not. To redo one
paper this way, delete its folder (leaving the PDF loose) and ingest it again with
the flag.

## Decision Gates

| Situation | Action |
| --- | --- |
| Malformed/missing configuration | Report the error; do nothing |
| `source_base` set to something that is not a folder | Report the error; do nothing |
| Neither `source_base` nor `source_roots` configured | Report the error; do nothing |
| A folder under `source_base` with no loose PDF | Not a source root; leave it untouched |
| Unknown `engine`/`mode`, or a value of the wrong type (`strip_references`/`force_ocr` not a boolean) | Report the error before loading the engine; do nothing |
| Loose PDFs present | List them, ask which to ingest, ingest only those |
| User approves a subset | Ingest exactly the approved paths; leave the rest loose |
| User approves nothing | Stop; move no file |
| No loose PDFs (all in folders) | Report nothing to do; do not re-ingest |
| Argument that is missing, not a PDF, a directory, or already ingested | Refuse before loading the engine; move nothing |
| A paper's `<stem>/` folder already exists and is not empty | Refuse that paper; say to delete the folder to re-ingest |
| Marker not installed in the interpreter | Report it and point at `setup.sh`; move nothing |
| A single file fails | Report that file; leave it loose; continue with the rest |

## Output Reporting

On success, emit only a brief confirmation of which papers were ingested. On
error, report only the error. No config dumps, path listings, or per-page tables.

**Speak the user's language.** Everything addressed to the user — the pending
list, the confirmation question and its options, the success or error report —
goes in the language the user is writing in, not in the language of this
document. The script's own stdout stays English: it is data to read, not a
message to relay verbatim. Paths, filenames, flags, and exit codes are never
translated.
