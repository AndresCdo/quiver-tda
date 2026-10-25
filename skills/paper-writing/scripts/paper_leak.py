"""paper_leak: the three-draft proof (register distance + n-gram overlap)
and the eight-token tripwire — deliberately separated by signature so
tuning the tripwire can never move the proof (`style-leak-detection` spec;
`design.md`, Decision D6).

`relative_overlap_holds` takes no threshold parameter: `overlap(S,R) <=
max(overlap(A,R), overlap(B,R))` is self-calibrating against whatever chance
floor two unstyled drafts already produce. `register_distance_holds`
requires both unstyled controls positionally — there is no way to compute
`d(S,{A,B})` without also computing `d(A,B)`, so a caller cannot drop the
control and still get a "pass" (mutation 6). Both read `paper_style.
normalize_tokens` for tokenization; math is excluded once, at the source.

Public surface:

    register_distance_holds(styled, unstyled_a, unstyled_b) -> dict
    relative_overlap_holds(styled, unstyled_a, unstyled_b, samples) -> dict
    overlap_against_set(text, samples)          -> int
    tripwire_spans(styled, samples, min_tokens=8) -> list[dict]
    check_tripwire(styled, samples)              -> None  (raises STYLE_OVERLAP)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_style  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: A closed, small set of function words whose relative frequency, together
#: with sentence-length distribution, makes up the register profile
#: (`style-leak-detection` spec, `Requirement: Register Distance Rises With
#: Style, Measured Against The A/B Control`). Not an attempt at a complete
#: function-word list — a fixed, shared vocabulary both `S` and `{A,B}` are
#: measured against identically.
_FUNCTION_WORDS: tuple[str, ...] = (
    "the", "a", "an", "of", "in", "on", "to", "for", "with", "and", "or",
    "but", "is", "are", "was", "were", "this", "that", "these", "those",
    "which", "as", "by", "at", "from", "it", "its", "be", "been", "we",
    "our", "not", "than", "such", "into", "over", "under", "between",
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _sentence_lengths(text: str) -> list[int]:
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]
    return [len(paper_style.normalize_tokens(sentence)) for sentence in sentences]


def _profile(text: str) -> dict:
    tokens = paper_style.normalize_tokens(text)
    lengths = _sentence_lengths(text)
    mean_length = sum(lengths) / len(lengths) if lengths else 0.0
    total = len(tokens) or 1
    frequencies = {word: tokens.count(word) / total for word in _FUNCTION_WORDS}
    return {"mean_sentence_length": mean_length, "function_word_freq": frequencies}


def _average_profile(profile_a: dict, profile_b: dict) -> dict:
    mean_length = (profile_a["mean_sentence_length"] + profile_b["mean_sentence_length"]) / 2
    frequencies = {
        word: (profile_a["function_word_freq"][word] + profile_b["function_word_freq"][word]) / 2
        for word in _FUNCTION_WORDS
    }
    return {"mean_sentence_length": mean_length, "function_word_freq": frequencies}


def _distance(profile_a: dict, profile_b: dict) -> float:
    total = abs(profile_a["mean_sentence_length"] - profile_b["mean_sentence_length"])
    for word in _FUNCTION_WORDS:
        total += abs(profile_a["function_word_freq"][word] - profile_b["function_word_freq"][word])
    return total


def register_distance_holds(styled: str, unstyled_a: str, unstyled_b: str) -> dict:
    """`d(S,{A,B})` MUST exceed `d(A,B)`; both are reported
    (`style-leak-detection` spec, `Requirement: Register Distance Rises With
    Style, Measured Against The A/B Control`). `unstyled_a`/`unstyled_b` are
    both required positionally — omitting either is a `TypeError`, not a
    silent default (mutation 6: dropping the control must fail
    construction)."""
    profile_s = _profile(styled)
    profile_a = _profile(unstyled_a)
    profile_b = _profile(unstyled_b)
    d_ab = _distance(profile_a, profile_b)
    d_s_ab = _distance(profile_s, _average_profile(profile_a, profile_b))
    return {"d_S_AB": d_s_ab, "d_AB": d_ab, "pass": d_s_ab > d_ab}


def _longest_run(tokens_a: list[str], tokens_b: list[str]) -> int:
    best = 0
    for i in range(len(tokens_a)):
        for j in range(len(tokens_b)):
            run = 0
            while (
                i + run < len(tokens_a) and j + run < len(tokens_b)
                and tokens_a[i + run] == tokens_b[j + run]
            ):
                run += 1
            if run > best:
                best = run
    return best


def overlap_against_set(text: str, samples: list[dict]) -> int:
    """The longest contiguous normalized n-gram `text` shares with ANY
    sample in `samples` (`R`, never a reference file read directly —
    `style-leak-detection` spec, `Requirement: Overlap Reads Only The
    Recorded Sample Set`)."""
    tokens = paper_style.normalize_tokens(text)
    if not samples:
        return 0
    return max(_longest_run(tokens, paper_style.normalize_tokens(sample["span"])) for sample in samples)


def relative_overlap_holds(styled, unstyled_a, unstyled_b, samples) -> dict:
    """`overlap(S,R) <= max(overlap(A,R), overlap(B,R))` — self-calibrating,
    no threshold parameter (`design.md`, Decision D6; `style-leak-detection`
    spec, `Requirement: Overlap Does Not Rise Above The Chance Floor`)."""
    overlap_s = overlap_against_set(styled, samples)
    overlap_a = overlap_against_set(unstyled_a, samples)
    overlap_b = overlap_against_set(unstyled_b, samples)
    return {
        "overlap_S": overlap_s, "overlap_A": overlap_a, "overlap_B": overlap_b,
        "pass": overlap_s <= max(overlap_a, overlap_b),
    }


def tripwire_spans(styled: str, samples: list[dict], *, min_tokens: int = 8) -> list[dict]:
    """Every maximal contiguous run of at least `min_tokens` normalized
    tokens `styled` shares with a sample in `samples`, naming the span and
    the reference it came from. A pure measurement — never refuses on its
    own; `check_tripwire` below is the refusing wrapper (`style-leak-
    detection` spec, `Requirement: The Eight-Token Tripwire`)."""
    styled_tokens = paper_style.normalize_tokens(styled)
    hits: list[dict] = []
    for sample in samples:
        sample_tokens = paper_style.normalize_tokens(sample["span"])
        index = 0
        while index < len(styled_tokens):
            best_length = 0
            for start in range(len(sample_tokens)):
                run = 0
                while (
                    index + run < len(styled_tokens) and start + run < len(sample_tokens)
                    and styled_tokens[index + run] == sample_tokens[start + run]
                ):
                    run += 1
                if run > best_length:
                    best_length = run
            if best_length >= min_tokens:
                hits.append({
                    "reference": sample.get("reference"),
                    "span": " ".join(styled_tokens[index:index + best_length]),
                    "length": best_length,
                })
                index += best_length
            else:
                index += 1
    return hits


def check_tripwire(styled: str, samples: list[dict]) -> None:
    """Refuses `STYLE_OVERLAP`, naming the shared span and the reference it
    came from, when `tripwire_spans` finds at least one hit."""
    hits = tripwire_spans(styled, samples)
    if hits:
        first = hits[0]
        raise Refused(
            "STYLE_OVERLAP",
            f"styled draft shares {first['length']} normalized tokens with reference "
            f"{first['reference']!r}: {first['span']!r}",
        )


#: The same-author threshold's backstop (`transposition-fidelity` spec,
#: `Requirement: The Threshold Self-Calibrates Against The Contract's Own
#: Prose`; `design.md`, Decision C). A RULING, not a measurement: the
#: shipped eight-token tripwire above is deliberately sub-clause because
#: for an INDEPENDENT paper's prose a shared clause is already suspicious;
#: a bound source section is the SAME author's own earlier text about the
#: same work, where reusing terms, quantities and formal statements at a
#: far higher baseline is ordinary, and the unit that means "copied" is a
#: sentence. Sixteen normalized tokens sits at the low end of an academic
#: sentence, set at the permissive end on purpose -- a false refusal here
#: blocks `write`, while a false pass still faces contract-audit and a
#: human. What would falsify it (executable only once a real `document`
#: binding exists, recorded as an obligation in `tasks.md`, not a hope): a
#: transposed draft in the paper's own register whose longest shared run
#: with its bound section reaches sixteen (16 is too low), or a verbatim
#: sentence pasted from the bound section whose normalized run stays under
#: sixteen and passes (16 is too high). Either observation moves this ONE
#: named constant, nothing else.
SOURCE_RUN_BACKSTOP: int = 16


def source_section_floor(contract_prose: str, section_text: str) -> int:
    """The longest normalized run the block's own contract prose already
    legitimately shares with its bound section `section_text` -- the one
    text already known to be legitimate, since it is same-author,
    same-subject, and quote-anchored to that source. Reuses
    `overlap_against_set` verbatim; computes no new overlap logic
    (`design.md`, Decision C). No upper clamp: a contract that itself
    carries a long run from its own bound section has licensed that run,
    deliberately, and the cost of that licensing is reported, never
    silently absorbed here."""
    return overlap_against_set(contract_prose, [{"span": section_text}])


def check_source_section_verbatim(
    draft_latex: str, contract_prose: str, sections, *, block_id: str | None = None,
) -> dict:
    """A SIBLING of `check_tripwire`, never an extension of it
    (`transposition-fidelity` spec, `Requirement: The Verbatim Check Is A
    Sibling, Never An Extension Of The Style Tripwire`) -- `style-leak-
    detection`'s own `Requirement: Overlap Reads Only The Recorded Sample
    Set` forbids `STYLE_OVERLAP` comparing against a reference file read
    directly, and a bound section's bytes are exactly that kind of direct
    read, so folding them into `check_tripwire`'s own sample set would
    break a shipped requirement rather than merely overload a function.

    Per section: `threshold = max(source_section_floor(...),
    SOURCE_RUN_BACKSTOP)`; refuses `SOURCE_SECTION_VERBATIM` on the first
    run STRICTLY exceeding `threshold` (`tripwire_spans`'s own `min_tokens`
    makes the inequality strict for free: a run of exactly `threshold`
    tokens never reaches `min_tokens=threshold + 1`). Names the bound fact,
    the lineage and the section title the offending span came from, plus
    `block_id` when the caller (`paper_write.write_block`) supplies it --
    kept a plain string parameter here, rather than the caller catching and
    re-raising with a computed code, so the refusal's own CODE argument
    stays the literal `"SOURCE_SECTION_VERBATIM"` this repository's roster
    derivation (`tests/test_paper_writing.py::reachable_paper_refusal_
    codes`) reads statically; a caller-side `raise Refused(exc.code, ...)`
    would make that argument a runtime value instead, an unreadable site
    the derivation refuses to silently guess past. Returns `{"sections":
    [...]}` -- one `{"lineage", "title", "floor", "threshold",
    "longest_run"}` entry per section -- when nothing exceeds, so the floor
    and threshold that decided are always reported, never merely inferred
    from the absence of a refusal (`Requirement: The Floor And Threshold
    Are Reported, Never Inferred Silently`)."""
    reports = []
    for section in sections:
        section_text = section["text"]
        floor = source_section_floor(contract_prose, section_text)
        threshold = max(floor, SOURCE_RUN_BACKSTOP)
        hits = tripwire_spans(
            draft_latex,
            [{"reference": section["title"], "span": section_text}],
            min_tokens=threshold + 1,
        )
        if hits:
            first = hits[0]
            prefix = f"{block_id}: " if block_id else ""
            raise Refused(
                "SOURCE_SECTION_VERBATIM",
                f"{prefix}draft shares {first['length']} normalized tokens with bound fact "
                f"{section['fact']!r} (lineage {section['lineage']!r}, section "
                f"{section['title']!r}): {first['span']!r}",
            )
        longest_run = overlap_against_set(draft_latex, [{"span": section_text}])
        reports.append({
            "lineage": section["lineage"],
            "title": section["title"],
            "floor": floor,
            "threshold": threshold,
            "longest_run": longest_run,
        })
    return {"sections": reports}
