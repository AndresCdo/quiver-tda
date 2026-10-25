"""paper_contract: front-matter grammar and schema validation.

The header is JSON inside a `---` … `---` front-matter fence; `json.loads`
is all-or-nothing by construction, so "never parses partially" is
structural rather than a rule someone has to maintain. Everything below the
closing fence is prose — read as bytes and handed back unread, never
decoded for meaning.

**`install_header` was removed** (zero-production-caller corrective): it was
the one-shot tool that inserted front matter into the ten shipped
`sections/*.md` files, and that migration already ran and completed --
every shipped file carries its header today. Nothing in `SKILL.md`, a
published spec, or a registered agent promises an ongoing "create a new
section contract" workflow, so this module no longer touches disk bytes at
all; it only parses what is already there.

Public surface:

    parse(data)                    -> (ContractHeader, body_bytes)
    resolve_sections_dir(arg, ...) -> Path   (raises SECTIONS_OUTSIDE_REPOSITORY,
                                               SECTION_CONTRACTS_UNREADABLE)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_scaffold  # noqa: E402
import paper_vocabulary  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: The exact fence line. JSON is a YAML 1.2 subset, so this is also valid
#: YAML front matter and editors highlight it (design.md, `the header is
#: JSON inside a --- front-matter fence`).
_FENCE_LINE = b"---"

_TOP_LEVEL_REQUIRED = ("section", "position", "blocks")
#: `mode` widened in `the-writer-may-assert-only-what-it-was-given`
#: (`section-contract` spec, `Requirement: Front Matter Schema`, MODIFIED):
#: the section-level drafting-mode default, optional, overridden per block.
#: `produces_facts` added in `a-fact-is-declared-or-it-is-produced`
#: (`fact-production` spec, `Requirement: produces_facts Field Grammar`):
#: the section-level half of the same field `_BLOCK_OPTIONAL` gains below,
#: parsed the identical way `after` already is at this level.
_TOP_LEVEL_OPTIONAL = ("after", "mode", "produces_facts")
_TOP_LEVEL_ALLOWED = _TOP_LEVEL_REQUIRED + _TOP_LEVEL_OPTIONAL

_BLOCK_REQUIRED = ("id", "requires_facts", "requires_declarations", "citations")
#: `mode` widened the same way at block level — a block's own `mode`
#: overrides the section-level default when present (`resolve_mode` below).
#: `figure` widened in `a-diagram-that-compiles-or-says-why`
#: (`section-contract` spec, `Requirement: Front Matter Schema`, MODIFIED):
#: a per-block diagram obligation, read by `paper_obligation.py` and never
#: hardcoded against a section or block id.
#: `produces_facts` added in `a-fact-is-declared-or-it-is-produced`
#: (`fact-production` spec, `Requirement: produces_facts Field Grammar`): a
#: block MAY declare the facts it writes rather than observes, entry shape
#: byte-identical to `requires_facts` (design.md, Decision B) and parsed
#: through the same `_normalize_requirement_entry`.
_BLOCK_OPTIONAL = ("optional", "after", "mode", "figure", "produces_facts")
_BLOCK_ALLOWED = _BLOCK_REQUIRED + _BLOCK_OPTIONAL

#: A `figure` object's own six subkeys. Five are required, nothing else
#: admitted (`diagram-obligation` spec, `Requirement: Obligations Read From
#: Contract Front Matter`; `section-contract` spec, `Requirement: Front
#: Matter Schema`). `caption_decodes` is deliberately a boolean, not a list
#: of encodings — WHICH encodings exist is a property of the diagram itself
#: and lives in `<id>.diagram.json`, never duplicated into the contract.
#:
#: `components_from` is OPTIONAL (corrective amendment, `a-diagram-that-
#: compiles-or-says-why`'s own verify FAIL, CRITICAL finding): it names the
#: one fact whose value IS the diagram's full expected component list, and
#: that equality only holds when the diagram truly is one fact's own list
#: by contract (section 01: the methods diagram is the contribution list).
#: A block whose diagram is a composite crossing over several categories of
#: content, none of which alone is the full list (section 02's closing
#: diagram), declares no `components_from` at all — the Components Check
#: then does not run for that block, honestly, rather than being wired to
#: one fact's partial value and silently inverting (measured directly: a
#: prose-compliant diagram refused, a degenerate one passed). Same
#: `raw.get(...) is not None` round-trip convention `mode` already uses
#: below, so a re-serialized header's explicit `null` means the same as the
#: key being absent.
_FIGURE_REQUIRED = (
    "ordered", "excludes",
    "caption_enumerates", "caption_decodes", "mandatory",
)
_FIGURE_OPTIONAL = ("components_from",)
_FIGURE_ALLOWED = _FIGURE_REQUIRED + _FIGURE_OPTIONAL

_AFTER_REQUIRED = ("target", "source")
_SOURCE_REQUIRED = ("file", "quote")
#: Same shape as an `after` entry's own `source` — `{value, source}`, where
#: `source` is `{file, quote}` (`section-contract` spec, `Requirement:
#: Closed Mode Vocabulary And Transcription`). Reuses `_validate_source`
#: below rather than a second copy of the same three checks.
_MODE_REQUIRED = ("value", "source")
#: `requires_facts` / `requires_declarations` entry shape
#: (`requirement-transcription` spec, `Requirement: Transcribed Requirement
#: Entries Only`; `section-contract` spec, `Requirement: Front Matter
#: Schema`). U3 (design.md D3): bare-string acceptance is removed; every
#: entry MUST be an object carrying both keys, with a non-null `source` —
#: see `_normalize_requirement_entry`.
_REQUIREMENT_REQUIRED = ("value", "source")
#: `requires_facts`-only optional half (`source-section-binding` spec,
#: `Requirement: Bindable Facts Are Derived, Never Listed`; `section-
#: contract` spec, `Requirement: Front Matter Schema`, MODIFIED by
#: `the-requirement-names-the-section-that-feeds-it`): the source
#: document's lineage and the exact title of the section within it that
#: feeds this entry. Never admitted on `requires_declarations` or
#: `produces_facts` — only a caller that opts in via
#: `_normalize_requirement_entry`'s `allow_document` parameter ever widens
#: its allowed key set to include this.
_REQUIREMENT_OPTIONAL = ("document",)
_DOCUMENT_REQUIRED = ("lineage", "section")

#: The transcription lock's own emphasis strip — a closed, enumerated pair
#: of markdown constructs, never a bare-character removal (corrective:
#: "the emphasis strip is positionally blind"). `**bold**` is matched
#: first, on two whole delimiter pairs with no `*` inside either span, so a
#: bold run is never mistaken for two adjacent italic runs. `*italic*` is
#: matched second, requiring its opening delimiter to be followed by a
#: non-whitespace, non-`*` character and its content to carry no further
#: `*` — this is what makes `func*tions` (one bare `*`, no closing partner
#: anywhere) survive with its `*` intact rather than silently vanishing:
#: a single stray delimiter is not a pair, so nothing here ever strips it,
#: and the comparison below correctly still fails against `functions`.
_BOLD_EMPHASIS_RE = re.compile(r"\*\*([^*]+?)\*\*")
_ITALIC_EMPHASIS_RE = re.compile(r"\*([^\s*][^*]*)\*")


@dataclass(frozen=True)
class ContractHeader:
    """One parsed header. `blocks` is a list of validated dicts, each
    carrying exactly `id`, `requires_facts`, `requires_declarations`,
    `citations`, `optional`, `after`, `mode`, `figure`, `produces_facts` —
    defaults filled in, nothing extra. `mode` is the section-level default
    (`None` when the header declares none); a block's own `mode` entry, also
    `None` when absent, wins over it (`resolve_mode` below). `produces_facts`
    is this dataclass's OWN section-level list, the same shape `after`
    already has at this level (`fact-production` spec, `Requirement:
    produces_facts Field Grammar`; design.md, Decision B) — defaulted to an
    empty list so every existing construction site and fixture stays green."""

    section: str
    position: int
    after: list
    blocks: list
    mode: dict | None = None
    produces_facts: list = field(default_factory=list)


def _split_front_matter(data: bytes) -> tuple[str, bytes]:
    """Returns `(json_text, body_bytes)`. Refuses `MALFORMED_HEADER` when
    the file does not open with a `---` fence, the fence is never closed, or
    the header bytes are not valid UTF-8.
    """
    if not (data.startswith(b"---\n") or data.startswith(b"---\r\n")):
        raise Refused(
            "MALFORMED_HEADER",
            "file does not open with a '---' front-matter fence",
        )
    first_newline = data.index(b"\n")
    rest = data[first_newline + 1:]
    lines = rest.split(b"\n")
    close_idx = None
    for i, line in enumerate(lines):
        if line.rstrip(b"\r") == _FENCE_LINE:
            close_idx = i
            break
    if close_idx is None:
        raise Refused(
            "MALFORMED_HEADER",
            "front-matter fence opened but never closed with a line reading '---'",
        )
    json_bytes = b"\n".join(lines[:close_idx])
    body = b"\n".join(lines[close_idx + 1:])
    try:
        json_text = json_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refused("MALFORMED_HEADER", f"header bytes are not valid utf-8: {exc}")
    return json_text, body


def strip_markdown_emphasis(text: str) -> str:
    """Strips `**bold**` and `*italic*` markup by matching PAIRED
    delimiters only — never a bare `*` removed wherever it appears. Word
    content is untouched, so a paraphrase or an unrelated sentence still
    fails a substring check after stripping: this is character-pair
    removal, never a fuzzy or similarity match. Bold pairs are resolved
    before italic pairs so `**word**` is read as one bold span, not two
    adjacent italic delimiters."""
    text = _BOLD_EMPHASIS_RE.sub(r"\1", text)
    text = _ITALIC_EMPHASIS_RE.sub(r"\1", text)
    return text


def quote_in_body(body: bytes, quote: str) -> bool:
    """The transcription lock's own check, shared by every caller that
    verifies a transcribed `{file, quote}` pair against a contract's own
    prose: whitespace-collapsed and markdown-emphasis-stripped
    (`strip_markdown_emphasis`), `quote` against `body` — never the raw
    file, whose header JSON always re-serializes whatever `quote` a
    `source` entry holds, verbatim. `mode` (self-sourced; verified in
    `parse()` below, against the same file's own body) and `after` (may
    name a different contract; verified in `paper_graph.assemble_corpus`,
    against whichever file's body `source.file` names) both call this one
    function — two disciplines diverging here would be worse than either
    alone (`sdd-apply` launch context, defect 1)."""
    collapsed_body = strip_markdown_emphasis(" ".join(body.decode("utf-8").split()))
    collapsed_quote = strip_markdown_emphasis(" ".join(quote.split()))
    return collapsed_quote in collapsed_body


def _validate_source(source, owner: str) -> dict:
    """The `{file, quote}` shape an `after` entry's own `source` carries,
    and — since `the-writer-may-assert-only-what-it-was-given` — a `mode`
    declaration's `source` too (`section-contract` spec, `Requirement:
    Closed Mode Vocabulary And Transcription`: "the same shape
    `_validate_after_list` already enforces for `after` edges"). Factored
    out here so one validator serves both rather than two copies drifting
    (`design.md`, Decision D4)."""
    if not isinstance(source, dict):
        raise Refused("MALFORMED_HEADER", f"{owner}: 'source' must be an object")
    missing_source = [key for key in _SOURCE_REQUIRED if key not in source]
    if missing_source:
        raise Refused("MALFORMED_HEADER", f"{owner}: 'source' missing {missing_source[0]!r}")
    unknown_source = [key for key in source if key not in _SOURCE_REQUIRED]
    if unknown_source:
        raise Refused(
            "MALFORMED_HEADER", f"{owner}: 'source' carries unknown key {unknown_source[0]!r}"
        )
    return source


def _validate_after_list(value, owner: str) -> list:
    if not isinstance(value, list):
        raise Refused("MALFORMED_HEADER", f"{owner}: 'after' must be a list")
    for entry in value:
        if not isinstance(entry, dict):
            raise Refused("MALFORMED_HEADER", f"{owner}: each 'after' entry must be an object")
        missing = [key for key in _AFTER_REQUIRED if key not in entry]
        if missing:
            raise Refused("MALFORMED_HEADER", f"{owner}: 'after' entry missing {missing[0]!r}")
        unknown = [key for key in entry if key not in _AFTER_REQUIRED]
        if unknown:
            raise Refused("MALFORMED_HEADER", f"{owner}: 'after' entry carries unknown key {unknown[0]!r}")
        _validate_source(entry["source"], owner)
    return value


def _validate_mode_object(raw, owner: str) -> dict:
    """`mode` MUST be `{value, source}` — `value` one of
    `paper_vocabulary.MODES`, `source` the same `{file, quote}` shape
    `_validate_source` already enforces for `after` edges. Refuses
    `UNKNOWN_MODE` (via `paper_vocabulary.validate_mode`) for a `value`
    outside the pair (`section-contract` spec, `Requirement: Closed Mode
    Vocabulary And Transcription`)."""
    if not isinstance(raw, dict):
        raise Refused("MALFORMED_HEADER", f"{owner}: 'mode' must be an object")
    missing = [key for key in _MODE_REQUIRED if key not in raw]
    if missing:
        raise Refused("MALFORMED_HEADER", f"{owner}: 'mode' missing {missing[0]!r}")
    unknown = [key for key in raw if key not in _MODE_REQUIRED]
    if unknown:
        raise Refused("MALFORMED_HEADER", f"{owner}: 'mode' carries unknown key {unknown[0]!r}")
    value = raw["value"]
    if not isinstance(value, str):
        raise Refused("MALFORMED_HEADER", f"{owner}: 'mode.value' must be a string")
    paper_vocabulary.validate_mode(value)
    source = _validate_source(raw["source"], f"{owner}.mode")
    return {"value": value, "source": dict(source)}


def _validate_document_object(raw, owner: str) -> dict:
    """`document: {lineage, section}` — the source document's lineage and
    the title(s) of the section(s) within it that feed one `requires_facts`
    entry (`source-section-binding` spec; `section-contract` spec,
    `Requirement: Front Matter Schema`, MODIFIED). Both keys are required
    together: an absent key or an explicit `null` for either is treated as
    missing (named the same way `_validate_source` names a missing key),
    and any key outside `{lineage, section}` refuses naming the unknown key
    — the identical missing-then-unknown ordering `_validate_source` and
    `_normalize_requirement_entry` already use, so a `guidance/`-shaped
    marker's own precedent (name the ABSENT key first) is followed here too.

    `section` (U2d, `the-requirement-names-the-section-that-feeds-it`):
    ONE title (a non-empty string, the original shape) OR MORE THAN ONE (a
    non-empty list of unique non-empty-string titles) — a block may borrow
    from several sections of the same lineage (a contract's own prose may
    promise "one to three subsections" feeding one block), and the block
    count must never move just because a source document's own section
    count does. An empty list, a list carrying a repeated title, or a list
    entry that is not a non-empty string all refuse the same way a
    malformed single title would — shape errors, never silently tolerated.
    A single string stays valid; this never forces every binding to widen
    into a list.
    """
    if not isinstance(raw, dict):
        raise Refused("MALFORMED_HEADER", f"{owner}: 'document' must be an object")
    unknown = [key for key in raw if key not in _DOCUMENT_REQUIRED]
    if unknown:
        raise Refused(
            "MALFORMED_HEADER", f"{owner}: 'document' carries unknown key {unknown[0]!r}"
        )
    missing = [key for key in _DOCUMENT_REQUIRED if raw.get(key) is None]
    if missing:
        raise Refused("MALFORMED_HEADER", f"{owner}: 'document' missing {missing[0]!r}")
    lineage = raw["lineage"]
    if not isinstance(lineage, str) or not lineage:
        raise Refused(
            "MALFORMED_HEADER", f"{owner}: 'document.lineage' must be a non-empty string"
        )
    section = raw["section"]
    if isinstance(section, str):
        if not section:
            raise Refused(
                "MALFORMED_HEADER", f"{owner}: 'document.section' must be a non-empty string"
            )
    elif isinstance(section, list):
        if not section:
            raise Refused(
                "MALFORMED_HEADER", f"{owner}: 'document.section' list must not be empty"
            )
        if not all(isinstance(title, str) and title for title in section):
            raise Refused(
                "MALFORMED_HEADER",
                f"{owner}: 'document.section' list entries must all be non-empty strings",
            )
        if len(set(section)) != len(section):
            raise Refused(
                "MALFORMED_HEADER", f"{owner}: 'document.section' list carries a duplicate title"
            )
    else:
        raise Refused(
            "MALFORMED_HEADER",
            f"{owner}: 'document.section' must be a non-empty string or a "
            "non-empty list of unique non-empty-string titles",
        )
    return {"lineage": lineage, "section": section if isinstance(section, str) else list(section)}


def _normalize_requirement_entry(
    raw, validate, owner: str, *, allow_document: bool = False,
) -> dict:
    """The single normalization point for one `requires_facts` /
    `requires_declarations` / `produces_facts` entry (`requirement-
    transcription` spec, `Requirement: Transcribed Requirement Entries
    Only`; design.md D1: "the plain id list is never stored, only derived at
    read time through one accessor"). `validate` is the caller's own
    closed-vocabulary check (`paper_vocabulary.validate_fact` or
    `validate_declaration`), applied to `value`.

    U3 (design.md D3): bare-string acceptance is removed. An entry MUST be
    an object carrying `value` (a string, validated against the closed
    vocabulary) and a non-null `source` — an absent `source` key or an
    explicit `source: null` both refuse `MALFORMED_HEADER` naming `source`,
    exactly as an `after` entry's own `source` is required. A non-null
    `source` goes through `_validate_source`, the same `{file, quote}` shape
    enforced for `after` and `mode`. An unknown key or a non-string `value`
    refuses `MALFORMED_HEADER` naming it, mirroring `_validate_mode_object`.
    This makes the half-migrated bare-string state structurally
    unrepresentable rather than merely detected: a fixture or a contract
    rebuilt with a bare string now refuses at parse.

    `allow_document` (`the-requirement-names-the-section-that-feeds-it`):
    only `requires_facts` entries pass this `True`; `requires_declarations`
    and `produces_facts` entries never do, so a `document` key on either
    refuses `MALFORMED_HEADER` as an unknown key — a declaration is
    operator-supplied, never document-rooted (`section-contract` spec), and
    a produced fact has no document-rooted source of its own either. The
    returned dict carries a `"document"` key only when the raw entry
    declared one — an entry with no `document` half round-trips through
    this function with exactly the two keys it came in with, unchanged.
    """
    if not isinstance(raw, dict):
        raise Refused("MALFORMED_HEADER", f"{owner}: entry must be an object")
    allowed = _REQUIREMENT_REQUIRED + (_REQUIREMENT_OPTIONAL if allow_document else ())
    missing = [key for key in _REQUIREMENT_REQUIRED if key not in raw]
    if missing:
        raise Refused("MALFORMED_HEADER", f"{owner}: entry missing {missing[0]!r}")
    unknown = [key for key in raw if key not in allowed]
    if unknown:
        raise Refused("MALFORMED_HEADER", f"{owner}: entry carries unknown key {unknown[0]!r}")
    value = raw["value"]
    if not isinstance(value, str):
        raise Refused("MALFORMED_HEADER", f"{owner}: entry 'value' must be a string")
    validate(value)
    source = raw["source"]
    if source is None:
        raise Refused("MALFORMED_HEADER", f"{owner}: entry missing 'source'")
    source = dict(_validate_source(source, owner))
    result = {"value": value, "source": source}
    if allow_document and raw.get("document") is not None:
        result["document"] = _validate_document_object(raw["document"], owner)
    return result


def requirement_values(entries) -> tuple:
    """The ONLY way a caller turns `requires_facts` / `requires_declarations`
    entries into a plain tuple of ids, in declaration order (design.md D1:
    "the plain tuple exists only as a transient at two construction
    sites"). Nothing stores the result; every caller — `paper_graph`'s
    `BlockRecord` construction and `paper_cli.py`'s `BlockContract`
    construction — derives it fresh at the point of use, so two
    representations can never drift. An AST scan over `scripts/*.py`
    (`tests/test_paper_writing.py`) asserts no other module subscripts a
    parsed block's `["requires_facts"]` / `["requires_declarations"]`."""
    return tuple(entry["value"] for entry in entries)


def requirement_documents(entries) -> tuple:
    """Mirrors `requirement_values`: derives the `(fact_id, lineage,
    section_title)` triples from `requires_facts` entries that carry a
    `document` half, in declaration order (`source-section-binding` spec,
    worked example). Entries with no `document` half contribute nothing —
    `document` is optional, and an unbound bindable fact is a corpus-level
    concern (`SECTION_BINDING_ABSENT`, U3), never this accessor's own.
    `paper_graph.BlockRecord.source_bindings` is built from this, the sole
    source of that tuple.

    `document.section` (U2d) may be one title or a list of several — this
    accessor is where that shape is flattened: a list contributes ONE
    triple per title, in the list's own declaration order, so every
    downstream consumer (`paper_graph._verify_source_section_bindings`)
    keeps working against a single `section_title` per triple, unchanged.
    A single-string `section` still contributes exactly one triple, same
    as before U2d."""
    triples = []
    for entry in entries:
        document = entry.get("document")
        if document is None:
            continue
        section = document["section"]
        titles = section if isinstance(section, list) else (section,)
        for title in titles:
            triples.append((entry["value"], document["lineage"], title))
    return tuple(triples)


def _parse_figure(raw, owner: str) -> dict:
    """`diagram-obligation` spec, `Requirement: Obligations Read From
    Contract Front Matter`; `section-contract` spec, `Requirement: Front
    Matter Schema`. Refuses `MALFORMED_FIGURE_OBLIGATION` naming the
    missing or unknown key, or a wrong-typed value. `components_from`,
    when present, is validated through `paper_vocabulary.validate_fact` —
    an invented fact refuses `UNKNOWN_FACT`, reused verbatim rather than a
    second vocabulary (design.md, "Refusal codes and their classification").
    Absent (or explicit JSON `null`, matching `mode`'s own round-trip
    convention), it resolves to `None` and admits no Components Check for
    that block — see `_FIGURE_REQUIRED`'s own comment for why this is
    optional rather than the original six-required schema."""
    if not isinstance(raw, dict):
        raise Refused("MALFORMED_FIGURE_OBLIGATION", f"{owner}: 'figure' must be an object")
    missing = [key for key in _FIGURE_REQUIRED if key not in raw]
    if missing:
        raise Refused("MALFORMED_FIGURE_OBLIGATION", f"{owner}: 'figure' missing {missing[0]!r}")
    unknown = [key for key in raw if key not in _FIGURE_ALLOWED]
    if unknown:
        raise Refused(
            "MALFORMED_FIGURE_OBLIGATION", f"{owner}: 'figure' carries unknown key {unknown[0]!r}"
        )

    components_from = raw.get("components_from")
    if components_from is not None:
        if not isinstance(components_from, str):
            raise Refused(
                "MALFORMED_FIGURE_OBLIGATION", f"{owner}: 'figure.components_from' must be a string"
            )
        paper_vocabulary.validate_fact(components_from)

    for bool_key in ("ordered", "caption_enumerates", "caption_decodes", "mandatory"):
        if not isinstance(raw[bool_key], bool):
            raise Refused(
                "MALFORMED_FIGURE_OBLIGATION", f"{owner}: 'figure.{bool_key}' must be a boolean"
            )

    excludes = raw["excludes"]
    if not isinstance(excludes, list) or not all(isinstance(item, str) for item in excludes):
        raise Refused(
            "MALFORMED_FIGURE_OBLIGATION", f"{owner}: 'figure.excludes' must be a list of strings"
        )

    return {
        "components_from": components_from,
        "ordered": raw["ordered"],
        "excludes": list(excludes),
        "caption_enumerates": raw["caption_enumerates"],
        "caption_decodes": raw["caption_decodes"],
        "mandatory": raw["mandatory"],
    }


def _parse_block(raw, section: str) -> dict:
    if not isinstance(raw, dict):
        raise Refused("MALFORMED_HEADER", f"{section}: each block must be an object")
    missing = [key for key in _BLOCK_REQUIRED if key not in raw]
    if missing:
        raise Refused("MALFORMED_HEADER", f"{section}: block missing {missing[0]!r}")
    unknown = [key for key in raw if key not in _BLOCK_ALLOWED]
    if unknown:
        raise Refused("MALFORMED_HEADER", f"{section}: block carries unknown key {unknown[0]!r}")

    block_id = raw["id"]
    if not isinstance(block_id, str) or not block_id:
        raise Refused("MALFORMED_HEADER", f"{section}: block 'id' must be a non-empty string")

    facts_raw = raw["requires_facts"]
    if not isinstance(facts_raw, list):
        raise Refused("MALFORMED_HEADER", f"{section}.{block_id}: 'requires_facts' must be a list")
    facts = [
        _normalize_requirement_entry(
            entry, paper_vocabulary.validate_fact, f"{section}.{block_id}.requires_facts",
            allow_document=True,
        )
        for entry in facts_raw
    ]

    declarations_raw = raw["requires_declarations"]
    if not isinstance(declarations_raw, list):
        raise Refused(
            "MALFORMED_HEADER", f"{section}.{block_id}: 'requires_declarations' must be a list"
        )
    declarations = [
        _normalize_requirement_entry(
            entry, paper_vocabulary.validate_declaration, f"{section}.{block_id}.requires_declarations"
        )
        for entry in declarations_raw
    ]

    citations = raw["citations"]
    if not isinstance(citations, str):
        raise Refused("MALFORMED_HEADER", f"{section}.{block_id}: 'citations' must be a string")
    paper_vocabulary.validate_citations(citations)

    optional = raw.get("optional", False)
    if not isinstance(optional, bool):
        raise Refused("MALFORMED_HEADER", f"{section}.{block_id}: 'optional' must be a boolean")

    block_after = _validate_after_list(raw.get("after", []), f"{section}.{block_id}")

    produces_facts_raw = raw.get("produces_facts", [])
    if not isinstance(produces_facts_raw, list):
        raise Refused(
            "MALFORMED_HEADER", f"{section}.{block_id}: 'produces_facts' must be a list"
        )
    produces_facts = [
        _normalize_requirement_entry(
            entry, paper_vocabulary.validate_fact, f"{section}.{block_id}.produces_facts"
        )
        for entry in produces_facts_raw
    ]

    # `raw.get("mode") is not None` rather than `"mode" in raw`: this
    # function's own OWN output round-trips through re-serialization in
    # `paper_graph.py`'s corpus assembly and this suite's own fixtures
    # (`header.blocks` already carries a `"mode": None` key for every block
    # that declared none), so an explicit JSON `null` MUST mean the same
    # thing as the key being absent -- never a `MALFORMED_HEADER` a
    # round-trip would otherwise manufacture out of this parser's own
    # output shape.
    block_mode = None
    if raw.get("mode") is not None:
        block_mode = _validate_mode_object(raw["mode"], f"{section}.{block_id}")

    # Same `raw.get(...) is not None` convention as `mode` above: this
    # function's own output round-trips through re-serialization elsewhere
    # (`paper_graph.py`'s corpus assembly), so an explicit JSON `null` MUST
    # mean the same thing as the key being absent.
    block_figure = None
    if raw.get("figure") is not None:
        block_figure = _parse_figure(raw["figure"], f"{section}.{block_id}")

    return {
        "id": block_id,
        "requires_facts": list(facts),
        "requires_declarations": list(declarations),
        "citations": citations,
        "optional": optional,
        "after": block_after,
        "mode": block_mode,
        "figure": block_figure,
        "produces_facts": list(produces_facts),
    }


def parse_header(header) -> ContractHeader:
    """Validates an already-`json.loads`-ed header object against the
    schema and the three vocabularies. Refuses `MALFORMED_HEADER` naming the
    missing or unknown key; refuses `UNKNOWN_FACT` / `UNKNOWN_DECLARATION` /
    `UNKNOWN_CITATIONS_REGIME` from `paper_vocabulary` for a value outside
    the closed vocabularies."""
    if not isinstance(header, dict):
        raise Refused("MALFORMED_HEADER", "header is not a JSON object")

    missing = [key for key in _TOP_LEVEL_REQUIRED if key not in header]
    if missing:
        raise Refused("MALFORMED_HEADER", f"missing required key {missing[0]!r}")
    unknown = [key for key in header if key not in _TOP_LEVEL_ALLOWED]
    if unknown:
        raise Refused("MALFORMED_HEADER", f"unknown key {unknown[0]!r}")

    section = header["section"]
    if not isinstance(section, str) or not section:
        raise Refused("MALFORMED_HEADER", "'section' must be a non-empty string")

    position = header["position"]
    if not isinstance(position, int) or isinstance(position, bool):
        raise Refused("MALFORMED_HEADER", "'position' must be an integer")

    blocks_raw = header["blocks"]
    if not isinstance(blocks_raw, list) or not blocks_raw:
        raise Refused("MALFORMED_HEADER", "'blocks' must be a non-empty list")

    after = _validate_after_list(header.get("after", []), section)
    blocks = [_parse_block(raw, section) for raw in blocks_raw]

    section_mode = None
    if header.get("mode") is not None:
        section_mode = _validate_mode_object(header["mode"], section)

    produces_facts_raw = header.get("produces_facts", [])
    if not isinstance(produces_facts_raw, list):
        raise Refused("MALFORMED_HEADER", f"{section}: 'produces_facts' must be a list")
    produces_facts = [
        _normalize_requirement_entry(
            entry, paper_vocabulary.validate_fact, f"{section}.produces_facts"
        )
        for entry in produces_facts_raw
    ]

    return ContractHeader(
        section=section,
        position=position,
        after=after,
        blocks=blocks,
        mode=section_mode,
        produces_facts=produces_facts,
    )


def resolve_mode(header: ContractHeader, block: dict) -> dict | None:
    """A block's own `mode` wins; the section-level `mode` is the default;
    `None` when neither declares one (`section-contract` spec, `Requirement:
    Front Matter Schema`, scenarios "A block inherits the section-level
    mode" / "A block's own mode overrides the section-level default";
    `Requirement: Headers Written Before mode Existed` for the `None` case —
    `write`'s own readiness stage is what refuses on `None`, never this
    reader)."""
    block_mode = block.get("mode")
    if block_mode is not None:
        return block_mode
    return header.mode


def _verify_mode_transcription(header: ContractHeader, body: bytes) -> None:
    """`mode.source.quote` MUST be a literal (whitespace-collapsed,
    markdown-emphasis-stripped) substring of THIS file's own parsed prose
    body — checked here, once the header/body split has already happened,
    never inside `_validate_mode_object` (which runs during header
    validation, before any body exists to check against) and never
    against the raw file bytes, whose header JSON always re-serializes
    whatever `quote` a `mode.source` entry holds, verbatim (the exact
    vacuity a whole-file check would have for the shipped corpus, where
    every declared `mode` sources its own file). Walks both the
    section-level `mode` and every block-level `mode`, so a fabricated
    quote at either level refuses (`SPAN_NOT_IN_SOURCE`) before this
    module ever hands the header back to a caller."""
    entries = []
    if header.mode is not None:
        entries.append((header.section, header.mode))
    for raw_block in header.blocks:
        block_mode = raw_block.get("mode")
        if block_mode is not None:
            entries.append((f"{header.section}.{raw_block['id']}", block_mode))

    for owner, mode in entries:
        source = mode["source"]
        if not quote_in_body(body, source["quote"]):
            raise Refused(
                "SPAN_NOT_IN_SOURCE",
                f"{owner}: mode.source.quote {source['quote']!r} not found verbatim "
                f"(whitespace-collapsed, markdown-emphasis-stripped) in "
                f"{source['file']}'s prose body",
            )


def parse(data: bytes) -> tuple[ContractHeader, bytes]:
    """The whole-file entry point: split the fence, `json.loads` the
    middle, validate the result. `json.loads` is all-or-nothing, so a
    malformed body never produces a partial header -- the caller gets a
    `Refused` and nothing else (`MALFORMED_HEADER`, carrying the
    `JSONDecodeError`'s own line/column rather than a bare "invalid").

    Also verifies every declared `mode`'s own transcription against the
    body this same call just split off (`_verify_mode_transcription`) —
    the one half of the transcription discipline checkable with no
    further disk I/O, because `mode` is always sourced from the file
    being parsed. The `after`-edge half of the same discipline may need a
    DIFFERENT file's bytes and is verified in
    `paper_graph.assemble_corpus` instead — never here.
    """
    json_text, body = _split_front_matter(data)
    try:
        raw_header = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise Refused(
            "MALFORMED_HEADER",
            f"invalid JSON in header at line {exc.lineno} column {exc.colno}: {exc.msg}",
        )
    header = parse_header(raw_header)
    _verify_mode_transcription(header, body)
    return header, body


def resolve_sections_dir(sections_arg: str | None, *, forge_root: Path = paper_scaffold.FORGE_ROOT) -> Path:
    """Resolve `--sections <dir>` (or the default `<forge_root>/sections`).

    Refuses `SECTIONS_OUTSIDE_REPOSITORY` (invocation-defect) when the
    resolved path does not sit under `forge_root`. Reuses
    `paper_scaffold.FORGE_ROOT` rather than re-deriving a second root
    constant — the same `parents[3]` resolution `paper_scaffold.py` already
    proved, at the same directory depth from this file.

    Also refuses `SECTION_CONTRACTS_UNREADABLE` (work-state) when an
    EXPLICIT `sections_arg` sits under `forge_root` but does not exist as a
    directory (K4 corrective). Without this, a typo'd `--sections` path
    read as a real, legitimately empty corpus: `contract`/`readiness`/
    `order`/`plan` all reported a clean `ok` with zero blocks,
    indistinguishable from an actually-empty corpus. Reuses the exact code
    `paper_verify.UNMEASURED_REASONS` and `paper_coupling_evidence.
    _blocks_by_fact` already use to name "the corpus itself could not be
    read" — never a second code for the same condition — rather than
    inventing a fresh one.

    Scoped to an explicit `sections_arg` only, never the bare default
    (`<forge_root>/sections` when `sections_arg` is falsy): a caller who
    names a path is making a claim about reality worth checking; the
    default is this skill's own convention, always populated in a real
    checkout, and `test_sections_dir_defaults_to_sections_under_the_forge_
    root` fixes its own contract to the resolved path alone, independent of
    whatever the fixture's throwaway `forge_root` does or does not contain
    on disk.
    """
    root = forge_root.resolve()
    target = Path(sections_arg).resolve() if sections_arg else (root / "sections")
    try:
        target.relative_to(root)
    except ValueError:
        raise Refused(
            "SECTIONS_OUTSIDE_REPOSITORY",
            f"{target} does not resolve inside the repository root {root}",
        )
    if sections_arg and not target.is_dir():
        raise Refused(
            "SECTION_CONTRACTS_UNREADABLE",
            f"{target} does not exist as a directory; the section corpus cannot be read",
        )
    return target


def resolve_section_path(sections_dir: Path, section: str) -> Path:
    """The contract file declaring `section`, found by reading each header's
    own `section` field -- NEVER by composing a filename from `section`.

    The filename is not authoritative anywhere else in this skill and must
    not become authoritative here: `order` derives the writing order from
    the block graph and states it takes "`position`, declared block order,
    and every transcribed `after` edge; never the filename", and
    `paper_graph.assemble_corpus` keys every section off `header.section`
    after globbing `*.md`. This applies the identical rule for the one
    lookup that needs a single file rather than the whole corpus.

    Composing `sections_dir / f"{section}.md"` instead is what `assemble_
    packet` did, and it could not open a single one of the shipped
    contracts -- every one of them is named `NN-<section>.md`, so `packet`
    died with a `FileNotFoundError` traceback and exit 1 for every real
    block, rather than returning this skill's own refusal envelope.

    Refuses `SECTION_UNKNOWN` (invocation-defect), naming the sections the
    corpus does declare, so a typo is answerable from the refusal itself.
    Two files declaring the same section is a corpus defect rather than an
    invocation one and belongs to the corpus reader
    (`paper_graph.assemble_corpus`'s own `ID_COLLISION` surface); this
    returns the first in sorted order and never silently prefers one.
    """
    declared = []
    unreadable_files: list = []
    for path in sorted(sections_dir.glob("*.md")):
        try:
            header, _ = parse(path.read_bytes())
        except Refused as unreadable:
            # A sibling this lookup was not asked about cannot decide it. This
            # scan reads every file to find one, so without this an unrelated
            # corrupted contract that sorts alphabetically FIRST refused every
            # lookup behind it -- including a section whose own file is
            # perfectly well formed. Reproduced with a minimal fixture by the
            # verify phase of `the-redactor-receives-the-section-it-must-
            # transpose`, whose own corpus-contamination test had to order its
            # fixture filenames around this to stay meaningful.
            #
            # The defect is not swallowed, only deferred: if the requested
            # section IS found, the corrupt sibling genuinely did not matter
            # and `contract`/`plan` still refuse on it through the corpus
            # reader, which is the verb whose job that is. If it is NOT found,
            # the refusal below names the unreadable files beside the declared
            # sections, so "it is not there" and "one file could not be read"
            # never look the same.
            unreadable_files.append((path.name, unreadable.code))
            continue
        if header.section == section:
            return path
        declared.append(header.section)
    detail = (
        f"no contract under {sections_dir} declares section {section!r}; "
        f"declared sections are {sorted(declared)}"
    )
    if unreadable_files:
        listed = ", ".join(f"{name} ({code})" for name, code in sorted(unreadable_files))
        detail += f"; unreadable contracts, any of which could hold it: {listed}"
    raise Refused("SECTION_UNKNOWN", detail)
