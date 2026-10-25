"""paper_bindings: the redactor's input contract, its binding map, and the
checks that make "assert nothing outside the evidence set" a property this
CLI *detects* rather than merely instructs (`evidence-bound-drafting` spec).

The CLI never drafts anything — an agent (the redactor, `.claude/agents/
redactor.md`) does, and hands back a JSON envelope: LaTeX plus a binding map.
This module is the judge: sentences are segmented from the emitted LaTeX
itself, never trusted from the redactor's own account, and every binding is
resolved, typed and mode-checked against the block's real evidence set,
facts and mode — never against what the redactor merely claims.

Public surface:

    RedactorInput                              -> the five-input contract shape
    parse_binding(raw)                         -> (kind, ref)
    segment_sentences(latex)                   -> list[str]
    reconcile(latex, binding_entries)          -> list[dict]  (raises UNBOUND_SENTENCE, BINDING_ORPHANED)
    resolve_bindings(bindings, evidence_ids, licensed_facts) -> None  (raises EVIDENCE_ID_UNKNOWN, FACT_NOT_LICENSED)
    type_structural(bindings, contract_prose)  -> None  (raises STRUCTURAL_CARRIES_CLAIM)
    check_mode_admissibility(bindings, mode, evidence_by_id) -> None  (raises MODE_VIOLATION)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_vocabulary  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: `evidence-bound-drafting` spec, `Requirement: Redactor Input Contract`:
#: exactly five inputs, `style_set`/`source_sections` empty are both valid
#: values. This is a shape contract, not a validator with its own refusal
#: — a caller building a fixture for the redactor simply cannot omit a
#: field. `RedactorInput` has no production constructor anywhere in this
#: skill (`the-redactor-receives-the-section-it-must-transpose`, design.md
#: D3, measured by `rg 'RedactorInput' --type py`) — the field-count
#: assertion `RedactorInputContractTests` carries is this shape's ONLY
#: enforcement.
@dataclass(frozen=True)
class RedactorInput:
    contract_prose: str
    evidence_set: tuple = ()
    mode: str = ""
    style_set: tuple = ()
    #: `the-redactor-receives-the-section-it-must-transpose`, design.md D3/D4:
    #: appended fifth, exact `BlockContract.source_sections`/packet
    #: `source_sections` shape (`{fact, lineage, title, path, byte_start,
    #: byte_end, text}`), empty for a non-`transposition` block, an unbound
    #: block, or a block whose paper root could not be measured.
    source_sections: tuple = ()


#: The three binding kinds a sentence may be classified under
#: (`evidence-bound-drafting` spec, `Requirement: Binding Map Production`).
BINDING_KINDS: tuple[str, ...] = ("evidence", "fact", "structural")

_BINDING_RE = re.compile(r"^(evidence|fact):(?P<ref>.+)$")


@dataclass(frozen=True)
class Binding:
    sentence: str
    kind: str
    ref: str | None
    raw: str = field(default="", compare=False)


def parse_binding(raw: str) -> tuple[str, str | None]:
    """`"evidence:E1"` -> `("evidence", "E1")`; `"fact:results"` ->
    `("fact", "results")`; `"structural"` -> `("structural", None)`. Any
    other string is not one of the three kinds this map may name
    (`evidence-bound-drafting` spec, `Requirement: Binding Map Production`,
    "every entry names exactly one of `evidence:`, `fact:`, or
    `structural`") — raised as a plain `ValueError`, never a `Refused`: a
    binding map entry this malformed is not one this reconciliation was
    ever asked to judge, the redactor's contract having already promised
    only these three shapes.
    """
    if raw == "structural":
        return "structural", None
    match = _BINDING_RE.match(raw)
    if match is None:
        raise ValueError(f"{raw!r} is not evidence:<id>, fact:<id>, or structural")
    return match.group(1), match.group("ref")


#: Splits after a sentence-ending `.`/`!`/`?` followed by whitespace and
#: either a capital letter or a LaTeX command — enough for the contract
#: prose and fixtures this change judges; not a general-purpose sentence
#: tokenizer.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\\])")


def segment_sentences(latex: str) -> list[str]:
    """Segments `latex` into sentences from the emitted bytes themselves —
    the CLI's own reading, never the redactor's account of where its
    sentence boundaries fall (`evidence-bound-drafting` spec, `Requirement:
    Draft-Versus-Map Reconciliation`)."""
    text = latex.strip()
    if not text:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def reconcile(latex: str, binding_entries: list[dict]) -> list[Binding]:
    """Segments `latex` independently and checks it against
    `binding_entries` (each `{"sentence": ..., "binding": "evidence:E1"}`)
    in both directions. Refuses `UNBOUND_SENTENCE` naming a segmented
    sentence absent from the map; refuses `BINDING_ORPHANED` naming a map
    entry matching no segmented sentence."""
    sentences = segment_sentences(latex)
    by_sentence = {entry["sentence"]: entry for entry in binding_entries}

    for sentence in sentences:
        if sentence not in by_sentence:
            raise Refused("UNBOUND_SENTENCE", f"drafted sentence has no binding: {sentence!r}")

    sentence_set = set(sentences)
    for entry in binding_entries:
        if entry["sentence"] not in sentence_set:
            raise Refused(
                "BINDING_ORPHANED",
                f"binding entry matches no segmented draft sentence: {entry['sentence']!r}",
            )

    bindings = []
    for sentence in sentences:
        entry = by_sentence[sentence]
        kind, ref = parse_binding(entry["binding"])
        bindings.append(Binding(sentence=sentence, kind=kind, ref=ref, raw=entry["binding"]))
    return bindings


def resolve_bindings(bindings: list[Binding], evidence_ids: set, licensed_facts: set) -> None:
    """Refuses `EVIDENCE_ID_UNKNOWN` naming an `evidence:` binding's id when
    it is absent from the block's evidence set; refuses `FACT_NOT_LICENSED`
    naming a `fact:` binding's id when it sits outside `requires_facts`
    (`evidence-bound-drafting` spec, `Requirement: Binding Resolution`)."""
    for binding in bindings:
        if binding.kind == "evidence" and binding.ref not in evidence_ids:
            raise Refused("EVIDENCE_ID_UNKNOWN", f"{binding.ref!r} is not in the block's evidence set")
        if binding.kind == "fact" and binding.ref not in licensed_facts:
            raise Refused("FACT_NOT_LICENSED", f"{binding.ref!r} is not in requires_facts")


_MATH_INLINE_RE = re.compile(r"\$[^$]*\$")
_MATH_DISPLAY_RE = re.compile(
    r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(equation|align|gather|math)\*?\}.*?\\end\{\1\*?\}",
    re.DOTALL,
)
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?")
_CITE_RE = re.compile(r"\\cite\w*")
_DIGIT_RE = re.compile(r"\d")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _strip_math(text: str) -> str:
    text = _MATH_DISPLAY_RE.sub(" ", text)
    text = _MATH_INLINE_RE.sub(" ", text)
    return text


def _has_numeral(sentence: str) -> bool:
    stripped = _strip_math(sentence)
    if _DIGIT_RE.search(stripped):
        return True
    words = (w.lower() for w in _WORD_RE.findall(stripped))
    return any(word in paper_vocabulary.NUMBER_WORDS for word in words)


def _has_cite(sentence: str) -> bool:
    return bool(_CITE_RE.search(sentence))


def _has_comparative(sentence: str) -> bool:
    stripped = _strip_math(sentence)
    words = (w.lower() for w in _WORD_RE.findall(stripped))
    return any(word in paper_vocabulary.COMPARATIVES for word in words)


def _named_external_object(sentence: str, contract_prose: str) -> str | None:
    """A non-sentence-initial capitalised token, outside math and outside
    LaTeX commands, absent verbatim from `contract_prose` (`design.md`,
    Decision D3). Mechanical: no proper-noun heuristic, no auditor
    delegation."""
    stripped = _strip_math(sentence)
    stripped = _LATEX_CMD_RE.sub(" ", stripped)
    tokens = _WORD_RE.findall(stripped)
    for index, token in enumerate(tokens):
        if index == 0:
            continue
        if token[0].isupper() and token not in contract_prose:
            return token
    return None


def type_structural(bindings: list[Binding], contract_prose: str) -> None:
    """Refuses `STRUCTURAL_CARRIES_CLAIM` naming the offending sentence for
    a `structural` sentence carrying a numeral, a `\\cite` command, a
    comparative, or a named external object (`evidence-bound-drafting`
    spec, `Requirement: Structural Sentences Are Typed`)."""
    for binding in bindings:
        if binding.kind != "structural":
            continue
        if _has_numeral(binding.sentence):
            raise Refused(
                "STRUCTURAL_CARRIES_CLAIM", f"numeral in structural sentence: {binding.sentence!r}"
            )
        if _has_cite(binding.sentence):
            raise Refused(
                "STRUCTURAL_CARRIES_CLAIM", f"\\cite in structural sentence: {binding.sentence!r}"
            )
        if _has_comparative(binding.sentence):
            raise Refused(
                "STRUCTURAL_CARRIES_CLAIM", f"comparative in structural sentence: {binding.sentence!r}"
            )
        external = _named_external_object(binding.sentence, contract_prose)
        if external is not None:
            raise Refused(
                "STRUCTURAL_CARRIES_CLAIM",
                f"named external object {external!r} in structural sentence: {binding.sentence!r}",
            )


#: `evidence-bound-drafting` spec, `Requirement: Mode-Admissible Bindings`.
#: `transposition` admits only `fact`/`structural`/`resolution`-class
#: evidence; `argument` additionally admits `discovery`-class evidence.
#: `none` (no external source at all) is strictly more restrictive than
#: `resolution` and belongs in every mode's admitted set for that reason:
#: an evidence record's `regime` is inherited from its own block's
#: `citations` field (`paper_cli._resolve_regime` ->
#: `paper_validate.read_citations_regime`, fallback `"none"`), so a mode
#: that refuses `none` would refuse the very blocks that declare no
#: citation source at all -- measured against the real corpus in
#: `tests/test_paper_writing.py::CorpusModeCitationsAdmissibilityTests`.
_MODE_ADMITTED_EVIDENCE_REGIMES: dict = {
    "transposition": frozenset({"none", "resolution"}),
    "argument": frozenset({"none", "resolution", "discovery"}),
}


def check_mode_admissibility(bindings: list[Binding], mode: str, evidence_by_id: dict) -> None:
    """Refuses `MODE_VIOLATION` naming an `evidence:` binding's id when its
    record's `regime` is outside the set `mode` admits. `fact:` and
    `structural` bindings are always admitted — mode admissibility is an
    evidence-class question only."""
    paper_vocabulary.validate_mode(mode)
    admitted = _MODE_ADMITTED_EVIDENCE_REGIMES[mode]
    for binding in bindings:
        if binding.kind != "evidence":
            continue
        record = evidence_by_id.get(binding.ref)
        regime = record.get("regime") if record else None
        if regime not in admitted:
            raise Refused(
                "MODE_VIOLATION",
                f"{binding.ref!r} (regime={regime!r}) is not admitted under mode {mode!r}",
            )
