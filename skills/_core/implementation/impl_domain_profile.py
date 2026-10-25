"""The contract a Cut-1 implementation domain fills in, and the resolver
that finds it.

The moved engine (`_core/implementation/engine/implementation_engine.py`)
serves no domain of its own: it resolves its host from
`IMPLEMENTATION_DOMAIN_PROFILE` and refuses to start without one, mirroring
`skills/_core/deliberation/engine/domain-profile.ts`'s resolver
properties exactly -- no default, fails closed at import, absolute path
required, nested required-key validation, path values validated, named
refusal codes.

`ImplementationProfileError(RuntimeError)`, never `Refused`/`NameRefused`
(design.md D3, three independent reasons):

1. The TS precedent throws a plain `Error`, not the engine's own domain
   refusal type.
2. The engine's JSON error renderer lives inside a module that has not
   finished importing when this resolves, and a second, duplicated renderer
   here is new surface for a state the launcher never produces.
3. Collateral: `reachable_refusal_codes()`, part of this suite's own
   coverage lock, walks every `*.py` under `_core/implementation/` for
   `Refused`/`NameRefused` constructions and pins its derived count at a
   fixed number. Six `Refused`s in a core module would move that unrelated
   pin -- a behavioural-delta-adjacent edit to a guard this change does not
   touch. A distinctly-named exception is invisible to that walk.

Cut-1 field set (design.md D3, amended 2026-09-11 -- operator ruling on task
7.5's non-interference finding): `kit.root` (the engine's `SKILL_ROOT`, 19
reader lines), `cli.path` (the engine's `CLI_PATH` -> `CLI_INVOCATION`), and
`objective` (the engine's `OBJECTIVE_FLOW` -- stamped into every refusal AND
discovered by the suite's cross-skill north lock (`test_agents.py`), which
walks a skill's OWN directory tree for a literal `OBJECTIVE_FLOW` assignment).
Nothing else -- a profile field nothing reads cannot be mutation-proven, and
an unprovable field is the shape of a false guard; `objective` earns its
place by that exact rule, now that it is read twice from outside the engine.
"""
from __future__ import annotations

import importlib.util
import os
import re
import string
from pathlib import Path
from typing import Any, Mapping

#: The variable a launcher sets (`setdefault`, so an explicit override wins)
#: and this resolver reads. No default: a default would have to name one
#: domain, which is exactly the coupling this file exists to remove.
_ENV_VAR = "IMPLEMENTATION_DOMAIN_PROFILE"

#: `(section, key)` pairs the profile must declare, nested. Named this way
#: so an incomplete `kit: {}`-shaped profile is refused by its actual
#: missing LEAF (`kit.root`), never by the top-level key alone -- the
#: `artifact: {}` lesson `domain-profile.ts` already learned once. Path-
#: valued only: each pair below is also walked by the UNSAFE_PATH check,
#: which treats every value here as a filesystem path. `objective`'s own
#: leaves are validated separately (`_OBJECTIVE_REQUIRED`), since none of
#: them is a path.
_REQUIRED_NESTED: tuple[tuple[str, str], ...] = (("kit", "root"), ("cli", "path"))

#: Cut-2 (`the-domain-crosses-the-seam`, design.md D1/D7): the non-path
#: leaves a domain profile must declare, checked for PRESENCE only -- never
#: walked by the `..._UNSAFE_PATH` check below, which treats every
#: `_REQUIRED_NESTED` pair as a filesystem path. `vocabulary.names` is
#: deliberately absent here: design.md D7 lands it at S13, alongside the two
#: neutrality locks it exists to serve, not at S2 with the other fourteen.
_REQUIRED_PRESENCE: tuple[tuple[str, str], ...] = (
    ("provenance", "claim_key"),
    ("provenance", "authored_init_sentence"),
    ("findings", "locus_key"),
    ("findings", "remedy_locus_key"),
    ("findings", "notation_keys"),
    ("findings", "citation_pattern"),
    ("vocabulary", "subject_singular"),
    ("vocabulary", "subject_plural"),
    ("vocabulary", "subject_singular_es"),
    ("vocabulary", "subject_plural_es"),
    ("vocabulary", "subject_collective"),
    ("vocabulary", "subject_collective_es"),
    ("vocabulary", "artifact_noun"),
    # S13 (design.md D7): declared alongside the two neutrality locks it
    # exists to serve, not at S2 with the other fourteen -- this presence
    # requirement lands here, not above, so `DomainFieldLeafRefusalTests`'s
    # `vocabulary.names` case stays red through S12 and turns green only now.
    ("vocabulary", "names"),
    # `documents` is NOT a member of this tuple (Cut 3, design.md D4): it is
    # a LIST, validated per entry by its own indexed walk below --
    # `documents[N].label`, never the bare `documents.label` pair a flat
    # tuple entry would produce.
    # `the-holder-each-skill-declares` (design.md D1, tasks.md 1.3): the 8th
    # top-level `PROFILE` section -- the checklist holder this skill owns
    # the name of. Presence only, checked by the existing loop below;
    # `_REQUIRED_NESTED` is deliberately NOT used here -- its
    # `..._UNSAFE_PATH` check demands absolute-and-existing, the exact
    # inverse of a relative, usually non-existent holder filename. A
    # separate shape tier (`..._INVALID_HOLDER`, task 1.4) validates
    # `filename`/`headings`/`scaffold` together once all three are present.
    ("holder", "filename"),
    ("holder", "headings"),
    ("holder", "scaffold"),
)

#: `documents[N].directory` gets its OWN validation tier per index (design.md
#: M3, extended by Cut 3's D4 to a per-entry walk): required and absolute,
#: like `_REQUIRED_NESTED`'s pairs, but existence is NOT required.
#: `proposals_root()`'s own readers already tolerate an absent root --
#: `revision_discovery` returns `empty`, `revision_source` returns `None` --
#: so putting this leaf in `_REQUIRED_NESTED` would refuse AT IMPORT on any
#: clone with no `proposals/` yet, turning five reported absences (the
#: seal's own `*-e0` cases) into one fatal refusal: a behavioural delta.
#: Cut 3 (`a-revision-is-two-documents`, design.md D4): `documents` is a
#: LIST, not a scalar mapping. Each entry is validated independently, by its
#: own index -- `documents[1].directory`, never the bare `documents.directory`
#: -- so `_REQUIRED_ABSOLUTE_ONLY`'s former single-pair tuple is replaced by
#: the per-entry walk inside `_resolve()` below. An empty `documents` list is
#: refused `..._INCOMPLETE` naming `documents[0]`, mirroring
#: `_STAGE_REQUIRED`'s own `stages: []` lesson: presence of the list alone
#: does not rule out zero entries.

#: Cut 3 slice C (`the-second-document-verified-on-its-own-terms`, design.md
#: D1): the five claim-vocabulary leaves a `documents[N]` entry may declare,
#: overlaying the top-level `provenance.*`/`findings.*` scalars
#: (`document_vocabulary`, the engine's own accessor, reads these exact five
#: names). All-or-nothing per entry: an entry declaring ANY of them must
#: declare ALL of them, or the partial overlay is refused naming each
#: missing leaf by its own indexed path -- never a per-leaf fallback, which
#: would make deleting one leaf a zero-mover (design.md D1's own rationale).
_DOCUMENT_VOCABULARY_LEAVES: tuple[str, ...] = (
    "claim_key", "locus_key", "remedy_locus_key", "notation_keys",
    "citation_pattern",
)

#: The three sub-keys a declared `documents[N].notation_keys` overlay must
#: carry, mirroring `findings.notation_keys`'s own three engine-read keys
#: (`NOTATION_KEYS["locus"]`/`["remedyLocus"]`/`["unknown"]`).
_NOTATION_KEYS_REQUIRED: tuple[str, ...] = ("locus", "remedyLocus", "unknown")

#: `the-agreement-nothing-computes` (Slice D, design.md D1/R2): the three
#: sub-keys a declared `documents[N].block_locator` must carry -- `pattern`
#: (how this document spells a declared numbered entry, one capturing
#: group), `block_pattern` (the enclosing substitutable block), and
#: `identity` (a `str.format` template with exactly one field, `value`).
#: Required and non-nullable on EVERY entry, ruled onto `dataset_marker`'s
#: own required tier (5d42dd7) rather than the five-leaf all-or-nothing
#: overlay: a silent `block_locator` falls back to the engine's own
#: `TAG_RE`/`DISPLAY_BLOCK_RE`, and that silent fallback is the live defect
#: this leaf exists to close, never a tolerable absence the way the
#: five-leaf tier's silence is (its own fallback is the HOST's own
#: top-level `provenance.*`/`findings.*` values).
_BLOCK_LOCATOR_REQUIRED: tuple[str, ...] = ("pattern", "block_pattern", "identity")

#: `the-agreement-nothing-computes` (Slice D, design.md D5/R1): the two
#: sub-keys a declared `documents[N].cross_citation` mapping must carry --
#: `pattern` (the form this document uses to cite another document's
#: declared entries, one capturing group) and `resolves_against` (the
#: `label` of the document those citations resolve against). Required per
#: entry, on `dataset_marker`'s own tier, but -- unlike `block_locator` --
#: the LEAF itself is nullable: `None` states out loud that this document
#: cites no other document, a real declared state
#: `implementation-cross-document-agreement` must be able to tell apart
#: from "the profile author forgot to say". Only when the leaf is declared
#: as a mapping do these two sub-keys become required.
_CROSS_CITATION_REQUIRED: tuple[str, ...] = ("pattern", "resolves_against")

#: `domain-profile.ts`'s own `OBJECTIVE_REQUIRED` mirrored exactly: the four
#: top-level keys a declared north must carry.
_OBJECTIVE_REQUIRED: tuple[str, ...] = ("purpose", "stages", "arrival", "humanStops")

#: What every element of `objective.stages` must carry. `stages: []` would
#: pass a bare presence check vacuously -- a north with no stages is not a
#: north -- so this is checked as its own shape, exactly as `domain-
#: profile.ts`'s `stagesIncomplete` does.
_STAGE_REQUIRED: tuple[str, ...] = ("stage", "establishes", "behindWhen")


class ImplementationProfileError(RuntimeError):
    """The engine has no domain profile it can start with.

    Deliberately not `Refused`/`NameRefused` -- see the module docstring's
    three reasons. Every message below leads with its own named code so a
    caller can classify the refusal from `str(error)` alone, exactly as the
    engine's own `Refused.code` lets a JSON reader classify a refusal.
    """


def _load_profile_module(path: Path, configured: str):
    """One fresh, uncached load of the host-declared profile file.

    `spec_from_file_location` returning `None` (an unrecognised location)
    and the module's own top-level code raising are both refused under the
    same `UNREADABLE` code -- the caller only ever gets a working profile
    or a named reason it does not have one, never a raw traceback from a
    file it does not own.
    """
    spec = importlib.util.spec_from_file_location(
        "impl_domain_profile_host", path)
    if spec is None or spec.loader is None:
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_UNREADABLE: {configured} could "
            "not be loaded as a module.")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImplementationProfileError:
        raise
    except Exception as exc:  # the host's own file is malformed
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_UNREADABLE: {configured} raised "
            f"{type(exc).__name__}: {exc}") from exc
    return module


def _is_one_safe_component(holder_filename: Any) -> bool:
    """Exactly one path component -- non-empty, no separator, not `.`/`..`,
    no NUL, no newline, and `Path(f).name == f` as a general safety net over
    any other separator this platform might honor. Shared by `_resolve`'s
    own holder check and `declared_holder_filenames`, so a sibling's name
    is accepted under exactly the rule this skill's own is."""
    return (
        isinstance(holder_filename, str)
        and bool(holder_filename)
        and "/" not in holder_filename
        and "\\" not in holder_filename
        and holder_filename not in (".", "..")
        and "\x00" not in holder_filename
        and "\n" not in holder_filename
        and Path(holder_filename).name == holder_filename
    )


def declared_holder_filenames(skills_root: Path) -> frozenset[str]:
    """Every checklist holder filename declared by a profile under
    `skills_root/*/impl_profile.py` -- the profiles that share one engine
    copy, because each skill's launcher points that engine at its own
    `impl_profile.py` beside it.

    Derived, never a hand-kept list: a new sibling skill is recognized by
    shipping its own profile, with no edit here or in the engine.

    Fails closed by contributing nothing: a profile that cannot be loaded,
    exports no `PROFILE` mapping, or declares a holder filename that is not
    one safe `.md` path component is skipped. The engine only ever uses
    this set to stop treating a sibling's declared holder as an undeclared
    candidate, so a skipped sibling leaves its file a candidate, and the
    refusal that guards an unknown checklist still fires for it.
    """
    names: set[str] = set()
    try:
        candidates = sorted(skills_root.glob("*/impl_profile.py"))
    except OSError:
        return frozenset()
    for path in candidates:
        try:
            module = _load_profile_module(path, str(path))
            profile = getattr(module, "PROFILE", None)
            holder = profile.get("holder") if isinstance(profile, Mapping) else None
            filename = holder.get("filename") if isinstance(holder, Mapping) else None
        except Exception:  # an unreadable sibling contributes nothing
            continue
        if _is_one_safe_component(filename) and filename.endswith(".md"):
            names.add(filename)
    return frozenset(names)


def _resolve() -> Mapping[str, Any]:
    configured = os.environ.get(_ENV_VAR)
    if not configured:
        raise ImplementationProfileError(
            "IMPLEMENTATION_DOMAIN_PROFILE_REQUIRED: this engine serves no "
            f"domain of its own. Set {_ENV_VAR} to a module exporting "
            "`PROFILE`, or launch through a skill's own "
            "scripts/implementation_cli.py, which sets it.")

    # Absolute, and refused otherwise -- mirroring domain-profile.ts's own
    # reasoning verbatim: a relative path resolves against the working
    # directory, and the engine does not control that. A child process
    # launched with its cwd inside the engine would turn
    # `skills/.../impl_profile.py` into
    # `<engine>/skills/.../impl_profile.py` and die on a path
    # nobody wrote. Every launcher that sets this variable already knows an
    # absolute path.
    path = Path(configured)
    if not path.is_absolute():
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_NOT_ABSOLUTE: {configured} is "
            "relative, and a child process's working directory is not the "
            "engine's to assume.")
    if not path.is_file():
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_UNREADABLE: {configured} does "
            "not exist.")

    module = _load_profile_module(path, configured)
    profile = getattr(module, "PROFILE", None)
    if not isinstance(profile, Mapping):
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID: {configured} exports "
            "no `PROFILE`, or it is not a mapping.")

    missing = []
    for section, key in _REQUIRED_NESTED + _REQUIRED_PRESENCE:
        section_value = profile.get(section)
        if not isinstance(section_value, Mapping) or key not in section_value:
            missing.append(f"{section}.{key}")

    # Cut 3 (`a-revision-is-two-documents`, design.md D4): `documents` is a
    # LIST, validated per entry, by its own index -- never as a flat
    # top-level pair. An empty list is refused naming `documents[0]` alone
    # (mirroring `stages_incomplete`'s own reasoning: presence of the list
    # does not rule out zero entries). A non-empty list names each missing
    # leaf by its exact indexed path, `documents[N].directory`/
    # `documents[N].label`.
    documents = profile.get("documents")
    if not isinstance(documents, (list, tuple)) or len(documents) == 0:
        missing.append("documents[0]")
    else:
        for index, entry in enumerate(documents):
            entry_is_mapping = isinstance(entry, Mapping)
            if not entry_is_mapping or "directory" not in entry:
                missing.append(f"documents[{index}].directory")
            if not entry_is_mapping or "label" not in entry:
                missing.append(f"documents[{index}].label")
            # `a-data-directory-somebody-can-owe` (B1, design.md D1): its
            # own required tier, appended right after `label` -- never a
            # member of `_DOCUMENT_VOCABULARY_LEAVES` below, which is
            # all-or-nothing over five leaves this one has nothing to do
            # with. A string or the literal `None` both satisfy presence;
            # `None` means "this document never owes a dataset", declared
            # rather than silently absent.
            if not entry_is_mapping or "dataset_marker" not in entry:
                missing.append(f"documents[{index}].dataset_marker")
            # `the-agreement-nothing-computes` (Slice D, design.md D1,
            # R2 resolved 5d42dd7): its own required, non-nullable tier,
            # appended right after `dataset_marker` -- a missing LEAF names
            # `documents[N].block_locator` alone; a leaf present but missing
            # a sub-key names that sub-key's own indexed path. No entry may
            # borrow another entry's locator and none may fall back to the
            # engine's own constants (spec `implementation-per-document-
            # vocabulary`).
            if not entry_is_mapping or "block_locator" not in entry:
                missing.append(f"documents[{index}].block_locator")
            elif entry_is_mapping:
                locator = entry["block_locator"]
                for sub_key in _BLOCK_LOCATOR_REQUIRED:
                    if not isinstance(locator, Mapping) or sub_key not in locator:
                        missing.append(
                            f"documents[{index}].block_locator.{sub_key}")
            # `the-agreement-nothing-computes` (Slice D, design.md D5,
            # R1 resolved 5d42dd7): its own required tier, appended right
            # after `block_locator` -- a missing LEAF names
            # `documents[N].cross_citation` alone; a leaf DECLARED as a
            # mapping but missing a sub-key names that sub-key's own
            # indexed path. Unlike `block_locator`, the leaf's own value
            # may be the literal `None` -- checked here only for KEY
            # presence, never for its value, so `None` passes this tier
            # untouched (spec `implementation-per-document-vocabulary`,
            # "Omitting the leaf refuses by its own indexed name" /
            # "An explicit `None` is accepted and crosses nothing").
            if not entry_is_mapping or "cross_citation" not in entry:
                missing.append(f"documents[{index}].cross_citation")
            elif entry_is_mapping and entry["cross_citation"] is not None:
                crossing = entry["cross_citation"]
                for sub_key in _CROSS_CITATION_REQUIRED:
                    if not isinstance(crossing, Mapping) or sub_key not in crossing:
                        missing.append(
                            f"documents[{index}].cross_citation.{sub_key}")
            if entry_is_mapping:
                # Cut 3 slice C (design.md D1): all-or-nothing per entry.
                # An entry declaring none of the five vocabulary leaves is
                # silent, not incomplete (the pre-existing-profile rule) --
                # this only fires once at least one is present.
                declared_vocab = [leaf for leaf in _DOCUMENT_VOCABULARY_LEAVES
                                  if leaf in entry]
                if declared_vocab and len(declared_vocab) < len(_DOCUMENT_VOCABULARY_LEAVES):
                    for leaf in _DOCUMENT_VOCABULARY_LEAVES:
                        if leaf not in entry:
                            missing.append(f"documents[{index}].{leaf}")
                # Cut 3 slice C (design.md D3, tier 2): a declared
                # `notation_keys` overlay must carry all three engine-read
                # sub-keys -- checked whenever the leaf is present, even
                # inside an otherwise-partial overlay already caught above,
                # so its own missing sub-key is named too.
                if "notation_keys" in entry:
                    notation = entry["notation_keys"]
                    for sub_key in _NOTATION_KEYS_REQUIRED:
                        if not isinstance(notation, Mapping) or sub_key not in notation:
                            missing.append(
                                f"documents[{index}].notation_keys.{sub_key}")

    objective = profile.get("objective")
    if not isinstance(objective, Mapping):
        missing.append("objective")
    else:
        for key in _OBJECTIVE_REQUIRED:
            if key not in objective:
                missing.append(f"objective.{key}")
    if missing:
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INCOMPLETE: {configured} is "
            f"missing {', '.join(missing)}.")

    # `the-holder-each-skill-declares` (design.md D1/D4, tasks.md 1.4): the
    # holder leaf's own shape, validated at resolve time --
    # `IMPLEMENTATION_DOMAIN_PROFILE_INVALID_HOLDER`, joining the
    # `..._INVALID_CITATION_PATTERN`/`..._INVALID_BLOCK_LOCATOR`/
    # `..._INVALID_CROSS_CITATION_PATTERN` family (a distinct
    # `..._INVALID_<THING>` code per the established convention, never a
    # reuse of `..._UNSAFE_PATH`, whose message would be false here). Every
    # leaf's presence is already guaranteed by the check above. Four
    # checks (D4):
    holder = profile["holder"]
    holder_filename = holder["filename"]
    # (1) exactly one path component -- non-empty, no separator, not
    # `.`/`..`, no NUL, no newline, and `Path(f).name == f` as a general
    # safety net over any other separator this platform might honor.
    if not _is_one_safe_component(holder_filename):
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_HOLDER: {configured} "
            f"declares holder.filename={holder_filename!r}, which is not "
            "exactly one safe path component.")
    # (2) ends `.md` -- `AGREEMENTS_GLOB` is `"*.md"`, and the read
    # fall-back would not see a holder the write side created under
    # another suffix.
    if not holder_filename.endswith(".md"):
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_HOLDER: {configured} "
            f"declares holder.filename={holder_filename!r}, which does "
            "not end \".md\".")
    # (3) `headings` is a non-empty sequence of `str`.
    holder_headings = holder["headings"]
    if (
        not isinstance(holder_headings, (list, tuple))
        or len(holder_headings) == 0
        or any(not isinstance(heading, str) for heading in holder_headings)
    ):
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_HOLDER: {configured} "
            f"declares holder.headings={holder_headings!r}, which is not "
            "a non-empty sequence of str.")
    holder_scaffold = holder["scaffold"]
    if not isinstance(holder_scaffold, str):
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_HOLDER: {configured} "
            f"declares holder.scaffold={holder_scaffold!r}, which is not "
            "a str.")
    # (4) every `headings` entry occurs in `scaffold` as a full line whose
    # stripped text equals it, outside a fenced region -- the exact
    # matching rule `locate_headings` implements (`impl_position.py:
    # 366-389`: `stripped != heading` skips, and a ``` ``` `` `/`~~~` line
    # toggles `fenced`). Reimplemented here, never imported: this module
    # resolves before the engine and owns no dependency on it.
    for heading in holder_headings:
        stripped_heading = heading.strip()
        fenced = False
        found = False
        for line in holder_scaffold.split("\n"):
            stripped_line = line.strip()
            if stripped_line.startswith("```") or stripped_line.startswith("~~~"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if stripped_line == stripped_heading:
                found = True
                break
        if not found:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_HOLDER: {configured} "
                f"declares holder.headings entry {heading!r}, which does "
                "not occur in holder.scaffold as a full, unfenced line.")

    # Cut 3 slice C (design.md D3, tier 3): `citation_pattern`'s group
    # count, validated wherever it resolves -- the top-level fallback AND
    # every declared overlay. `_impact_class` reads `match.group(1) or
    # match.group(2) or match.group(3)`, so a fourth or a second group is a
    # live defect, not a style choice. Applied to the TOP-LEVEL pattern too
    # (not only overlays): it is document 0's own pattern under the
    # fallback, and a check that validated only overlays would leave the
    # one pattern that ships today unvalidated.
    citation_pattern_leaves = [
        ("findings.citation_pattern", profile["findings"]["citation_pattern"]),
    ]
    for index, entry in enumerate(documents):
        if "citation_pattern" in entry:
            citation_pattern_leaves.append(
                (f"documents[{index}].citation_pattern", entry["citation_pattern"]))
    for leaf_name, pattern in citation_pattern_leaves:
        try:
            group_count = re.compile(pattern).groups
        except re.error as exc:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_CITATION_PATTERN: "
                f"{configured} declares {leaf_name} that does not compile: "
                f"{exc}.") from exc
        if group_count != 3:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_CITATION_PATTERN: "
                f"{configured} declares {leaf_name} with {group_count} "
                "capturing group(s); exactly 3 are required.")

    # `the-agreement-nothing-computes` (Slice D, design.md D1): every
    # `documents[N].block_locator`'s own shape, validated at resolve time --
    # `documents` is guaranteed a non-empty list of entries each carrying a
    # complete `block_locator` here; the missing-leaf/sub-key check above
    # already raised otherwise. Exactly ONE capturing group in `pattern`,
    # never `citation_pattern`'s three -- `_impact_class` reads
    # `group(1) or group(2) or group(3)`, but the locator's own reader
    # takes a single value, so copying the three-group rule would enforce a
    # count nothing reads. `identity` validated via `string.Formatter().
    # parse`: exactly one field, named `value` -- never `eval`, never `%`,
    # never an f-string construction (threat-matrix row).
    for index, entry in enumerate(documents):
        locator = entry["block_locator"]
        try:
            pattern_groups = re.compile(locator["pattern"]).groups
        except re.error as exc:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_BLOCK_LOCATOR: "
                f"{configured} declares documents[{index}].block_locator."
                f"pattern that does not compile: {exc}.") from exc
        if pattern_groups != 1:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_BLOCK_LOCATOR: "
                f"{configured} declares documents[{index}].block_locator."
                f"pattern with {pattern_groups} capturing group(s); exactly "
                "1 is required.")
        try:
            re.compile(locator["block_pattern"])
        except re.error as exc:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_BLOCK_LOCATOR: "
                f"{configured} declares documents[{index}].block_locator."
                f"block_pattern that does not compile: {exc}.") from exc
        identity_fields = [
            field_name for _, field_name, _, _ in
            string.Formatter().parse(locator["identity"])
            if field_name is not None]
        if identity_fields != ["value"]:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_BLOCK_LOCATOR: "
                f"{configured} declares documents[{index}].block_locator."
                f"identity with field(s) {identity_fields}; exactly one "
                "field named 'value' is required.")
        # Optional: absent means off. When declared it must be a real
        # boolean -- a truthy string would turn aliasing on by accident.
        if ("block_aliases" in locator
                and not isinstance(locator["block_aliases"], bool)):
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_BLOCK_LOCATOR: "
                f"{configured} declares documents[{index}].block_locator."
                f"block_aliases as {locator['block_aliases']!r}; it must be "
                "true or false when declared.")

    # `documents[N].section_heading` (`cross-skill-consistency`, B1):
    # optional; absent means no heading is a section. When declared it is a
    # mapping whose `label` and `closer` compile, and whose optional
    # `marker` compiles with exactly one capturing group, the label its
    # reader takes.
    for index, entry in enumerate(documents):
        grammar = entry.get("section_heading")
        if grammar is None:
            continue
        where = f"{configured} declares documents[{index}].section_heading"
        problem = None
        if (not isinstance(grammar, Mapping)
                or not isinstance(grammar.get("label"), str)
                or not isinstance(grammar.get("closer"), str)
                or not isinstance(grammar.get("marker", ""), str)):
            problem = ("it must be a mapping with string `label` and `closer` "
                       "and an optional string `marker`")
        else:
            try:
                re.compile(grammar["label"])
                re.compile(grammar["closer"])
                if grammar.get("marker") and re.compile(grammar["marker"]).groups != 1:
                    problem = "its `marker` must carry exactly 1 capturing group"
            except re.error as exc:
                problem = f"a pattern in it does not compile: {exc}"
        if problem:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_SECTION_HEADING: "
                f"{where}; {problem}.")

    # `the-agreement-nothing-computes` (Slice D, design.md D5): every
    # `documents[N].cross_citation`'s own shape, validated at resolve
    # time -- guaranteed either the literal `None` or a complete two-key
    # mapping here; the missing-leaf/sub-key check above already raised
    # otherwise. Exactly ONE capturing group in `pattern`, the same
    # reasoning as `block_locator`'s own: the reader this leaf serves
    # takes a single value, so copying `citation_pattern`'s three-group
    # rule would enforce a count nothing reads. `resolves_against` must
    # name a document label another `documents[N]` entry actually
    # declares, and never its OWN entry's label -- a crossing that
    # resolves against itself crosses nothing, the same failure a
    # positional `index + 1` scheme could not even express as an error
    # (design.md D5's own rejected options).
    declared_labels = {entry["label"] for entry in documents}
    for index, entry in enumerate(documents):
        crossing = entry["cross_citation"]
        if crossing is None:
            continue
        try:
            crossing_groups = re.compile(crossing["pattern"]).groups
        except re.error as exc:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_CROSS_CITATION_PATTERN: "
                f"{configured} declares documents[{index}].cross_citation."
                f"pattern that does not compile: {exc}.") from exc
        if crossing_groups != 1:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_CROSS_CITATION_PATTERN: "
                f"{configured} declares documents[{index}].cross_citation."
                f"pattern with {crossing_groups} capturing group(s); exactly "
                "1 is required.")
        # Optional third sub-key: the form this document uses to mark an
        # entry of the target out of its own scope. Held to the pattern's
        # own one-group rule when declared; absent, the crossing reads as it
        # always did.
        out_of_scope = crossing.get("out_of_scope")
        if out_of_scope is not None:
            try:
                out_of_scope_groups = re.compile(out_of_scope).groups
            except (re.error, TypeError) as exc:
                raise ImplementationProfileError(
                    f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_CROSS_CITATION_PATTERN: "
                    f"{configured} declares documents[{index}].cross_citation."
                    f"out_of_scope that does not compile: {exc}.") from exc
            if out_of_scope_groups != 1:
                raise ImplementationProfileError(
                    f"IMPLEMENTATION_DOMAIN_PROFILE_INVALID_CROSS_CITATION_PATTERN: "
                    f"{configured} declares documents[{index}].cross_citation."
                    f"out_of_scope with {out_of_scope_groups} capturing group(s); "
                    "exactly 1 is required.")
        target = crossing["resolves_against"]
        if target not in declared_labels or target == entry["label"]:
            raise ImplementationProfileError(
                f"IMPLEMENTATION_DOMAIN_PROFILE_UNKNOWN_CROSS_DOCUMENT: "
                f"{configured} declares documents[{index}].cross_citation."
                f"resolves_against={target!r}, which names no OTHER "
                "declared document label.")

    # `stages` presence alone (the loop above) does not rule out `stages: []`
    # -- domain-profile.ts's own `stagesIncomplete` lesson. Every element
    # must carry all three `_STAGE_REQUIRED` keys, or a stage this domain
    # declares by name would silently establish nothing and close on no
    # condition at all.
    stages = objective["stages"]
    stages_incomplete = (
        not isinstance(stages, (list, tuple)) or len(stages) == 0
        or any(not isinstance(stage, Mapping)
              or any(key not in stage for key in _STAGE_REQUIRED)
              for stage in stages))
    if stages_incomplete:
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_INCOMPLETE: {configured} is "
            "missing objective.stages.")

    # `SAFE_ARTIFACT_SEGMENT` in the TS precedent guards SEGMENTS joined
    # under a root; these are whole absolute paths the host names, so that
    # escape is not reachable here. What IS reachable is a `kit.root` that
    # does not exist -- today that scatters into 19 unrelated missing-asset
    # failures across the engine's own readers; validating it here turns
    # them into one named refusal at import (design.md D3). A "must live
    # under FORGE_ROOT" rule was considered and rejected: it would refuse a
    # tmpdir fixture profile, which is the exact override case `setdefault`
    # exists to serve.
    unsafe = []
    for section, key in _REQUIRED_NESTED:
        value = Path(profile[section][key])
        if not value.is_absolute() or not value.exists():
            unsafe.append(f"{section}.{key}")
    if unsafe:
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_UNSAFE_PATH: {configured} "
            f"declares an unsafe {', '.join(unsafe)} (must be absolute and "
            "exist on disk).")

    # `documents[N].directory` (M3, extended by Cut 3's D4): its own tier,
    # absolute required, existence NOT required -- a separate loop and a
    # separate message, never merged into the one above, which is exactly
    # what would refuse a still-empty `documents[N].directory` at import on
    # a clone with no `proposals/` (or a second document's directory) yet.
    # `documents` is guaranteed a non-empty list of complete entries here --
    # the missing-leaf check above already raised otherwise.
    unsafe_absolute_only = []
    for index, entry in enumerate(documents):
        value = Path(entry["directory"])
        if not value.is_absolute():
            unsafe_absolute_only.append(f"documents[{index}].directory")
    if unsafe_absolute_only:
        raise ImplementationProfileError(
            f"IMPLEMENTATION_DOMAIN_PROFILE_UNSAFE_PATH: {configured} "
            f"declares an unsafe {', '.join(unsafe_absolute_only)} (must be "
            "absolute; existence is not required).")

    return profile


#: The profile this process serves, resolved once at import. Chosen by the
#: host, never by the engine -- see the module docstring.
PROFILE: Mapping[str, Any] = _resolve()
