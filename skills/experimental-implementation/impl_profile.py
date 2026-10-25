"""This skill's own domain profile for the shared implementation engine
(`_core/implementation/engine/implementation_engine.py`), the SECOND host
built on the seam Cut 1/2/3 cut for it (change
`the-second-skill-the-seam-was-for`, slice A).

Every value here is computed from THIS file's own location, mirroring
`proposal-implementation/impl_profile.py` exactly (design.md D1/D2) --
`kit.root` and `cli.path` are structurally identical in shape (both derived
from `Path(__file__).resolve().parent`), never from the engine's location.
The launcher (`scripts/implementation_cli.py`) is a byte-identical copy of
the sibling's own launcher (design.md D4/M4): every path in it is
self-anchored off `Path(__file__).resolve()`, so the same launcher bytes placed
here resolve to THIS skill's own profile, never the sibling's.

**Scope, Slice A (design.md, proposal.md): change A only.** A single
declared document -- `documents[0]` is the `experiments/` directory,
label `experiments` (design.md D1). The mathematical proposal document,
cross-document agreement, and the successor composer were follow-on
changes (B, C, D), not built at Slice A. This profile's `documents` list
held exactly ONE entry, to that shape held by
`tests/test_implementation_domain_lock.py`'s single-document guard
(design.md D10).

**Scope, Slice C (`the-second-document-verified-on-its-own-terms`,
design.md D8/M2): `documents[1]` now declares the mathematical proposal**
-- its own complete per-document vocabulary overlay (`claim_key`
`"equations"`, matching `proposal-implementation`'s own established
vocabulary for this domain), landed as this change's LAST write, after
the per-document fold and per-document citation matching it depends on
were already proven against a fixture the shipped fold could not pass
(design.md D8's own ordering argument). The single-document guard this
scope note used to name is deleted; `tests/test_implementation_domain_
lock.py`'s `TwoDocumentReadProvenTests` replaces it, proving the
per-document READ rather than merely counting two entries.

**`vocabulary.names` (design.md D6, the M1 finding).**
`LockADiscoveryTests.test_every_declared_name_really_is_that_domain_speaking`
was vacuous for every profile, this skill's included, because it searched
`entry["source"]` -- the profile file's own text, which trivially contains
every literal in its own `names` list. The lock itself changes (design.md
D6): the haystack becomes the profile's declared VALUES (every leaf other
than `vocabulary.names` itself, rendered as text), so a declared name must
actually equal some OTHER leaf's real value to be found -- never merely
exist as a literal in this file's source.

Declared here: the namespace word `experimental-implementation` (found via
`kit.root`'s own path text, the same reason `experimental-deliberation`
records for its own namespace word), plus every subject-vocabulary value
measured ABSENT (`\\bword\\b == 0`, case-insensitive) from
`implementation_engine.py` -- admitting a word the engine already spells as
general machinery would immediately redden `LockBEngineNeutralityTests`.
Measured this session, word-boundary, case-insensitive, whole-word
occurrence counts (never line counts -- see the-second-skill-the-seam-
was-for's apply-progress record for the line-count figures 89/30/28, which
answer a different question):

    experiment            24   -- EXCLUDED (general engine vocabulary)
    experiments             6   -- EXCLUDED (general engine vocabulary)
    experimento             0   -- admitted
    experimentos            0   -- admitted
    experimentation         0   -- admitted
    experimentación    0   -- admitted
    protocol                 1   -- EXCLUDED (one comment, "the protocol")

So `names` is the namespace word plus the four measured-absent forms --
never `experiment`/`experiments`/`protocol`, which the engine already
spells for reasons that have nothing to do with this domain.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# The canonical tree is `skills/<skill>/impl_profile.py`, one level
# shallower than upstream's `.claude/skills/<skill>/` anchor, so the repo
# root is `parents[1]`, not `parents[2]`.
_SKILL = Path(__file__).resolve().parent
_FORGE_ROOT = _SKILL.parents[1]

#: The ONE experiment convention, shared with `experimental-deliberation`
#: (`reference-experimental.ts`, `profile.ts`): the identifier class, the
#: declaration marker `[<declares>:<id>]` an experiment carries in its own
#: heading, the citation marker, and the prose citation form. Read, never
#: respelled here -- a second spelling is how the two skills came to disagree
#: on what an experiment heading is (`cross-skill-consistency`, A7).
EXPERIMENT_CONVENTION = json.loads(
    (_SKILL.parent / "_core" / "conventions" / "experiments.json")
    .read_text(encoding="utf-8"))
#: The ONE section-label convention, shared with `proposal-implementation`:
#: what a section heading's leading label looks like (`cross-skill-consistency`,
#: B1). Read, never respelled here.
SECTION_CONVENTION = {
    key: value for key, value in json.loads(
        (_SKILL.parent / "_core" / "conventions" / "sections.json")
        .read_text(encoding="utf-8")).items()
    if not key.startswith("$")}
_IDENTIFIER = EXPERIMENT_CONVENTION["identifier"]
_DECLARES = re.escape("[" + EXPERIMENT_CONVENTION["declares"] + ":")
_PROSE_REFERENCE = EXPERIMENT_CONVENTION["proseReference"].replace(
    "{identifier}", _IDENTIFIER)
#: `[<outOfScope>:<id>]`: the convention's marker an experiments document uses
#: to say a proposal claim is deliberately not tested here. `agree` subtracts
#: what it marks from `untested` (`cross-skill-consistency`, C14).
_OUT_OF_SCOPE = (re.escape("[" + EXPERIMENT_CONVENTION["outOfScope"] + ":")
                 + f"({_IDENTIFIER})" + re.escape("]"))

#: WHY THIS SKILL WAS INVOKED, AND WHERE IT HAS TO ARRIVE.
#:
#: This domain's own north (design.md D3): five stages, a different arrival
#: from the sibling's six -- `standing` -> `binding` -> `instrumentation` ->
#: `rehearsal` -> `full-scale`. No `behindWhen` here matches
#: `UNMEASURABLE` (`nothing here measures it|the user said so`); this domain
#: declares no such stage.
#:
#: Discovered by `tests/test_agents.py::_python_objective` as a module-level
#: literal named exactly `OBJECTIVE_FLOW` -- never wrap this in a function
#: call or a derived expression, or that AST-literal walk stops finding it.
OBJECTIVE_FLOW = {
    "purpose": (
        "carry the declared experiments protocol as far as complete runs "
        "whose own record agrees with what the protocol says -- not a "
        "green verification, not a passing rehearsal"),
    "stages": [
        {"stage": "standing",
         "establishes": "a repository set up the way this skill expects, "
                        "with an interpreter of its own and the protocol's "
                        "declared steps laid out as runnable commands",
         "behindWhen": "`structure` reports no scaffold gaps and "
                       "`__implementation__` carries the revision and "
                       "premises the protocol answers to -- which is what "
                       "`materialize --stage objects` refuses without"},
        {"stage": "binding",
         "establishes": "the code that runs says what the bound "
                        "experiments revision says, every declared step "
                        "traced to a runnable command",
         "behindWhen": "`fidelity` is clean against the bound experiments "
                       "revision and the target's own suite is green under "
                       "its own interpreter"},
        {"stage": "instrumentation",
         "establishes": "every measurement the protocol declares has a "
                        "place to land -- a metric, a record, a check that "
                        "can fail",
         "behindWhen": "every declared measurement resolves to something "
                       "that can actually be run and read back"},
        {"stage": "rehearsal",
         "establishes": "the declared flow runs end to end at a small "
                        "scale, and the record it leaves agrees with the "
                        "document a person reads",
         "behindWhen": "the rehearsal is complete and its own report is "
                       "`ok`"},
        {"stage": "full-scale",
         "establishes": "every step routed to where it was decided to run, "
                        "and executed there at the scale the protocol "
                        "declares",
         "behindWhen": "this is the arrival; it is behind nobody"},
    ],
    "arrival": (
        "complete runs at the protocol's declared scale, with a record "
        "checkable against the experiments revision"),
    # Said here because a blocked agent needs it most: some stops are not
    # defects and must not be repaired.
    "humanStops": [
        "authorizing that code be written at all, which nothing below the "
        "gate may start without",
        "approving the map from the protocol's declared steps to runnable "
        "commands",
        "publishing the commit a worker would clone",
        "authorizing a launch, which is hours of somebody's quota",
    ],
}

PROFILE = {
    # Structurally identical to the sibling (design.md D2): both leaves are
    # derived from this file's own location, never the engine's.
    "kit": {"root": _SKILL},
    "cli": {"path": _SKILL / "scripts" / "implementation_cli.py"},
    "objective": OBJECTIVE_FLOW,
    "provenance": {
        "claim_key": "experiments",
        "authored_init_sentence": (
            "Each module declares the sections and experiments it "
            "implements in\n"
            "`__provenance__`, and every invariant listed there has a "
            "matching\n"
            "test under tests/.\n"),
    },
    "findings": {
        "locus_key": "experiments",
        "remedy_locus_key": "remedy_experiments",
        "notation_keys": {
            "locus": "experiments",
            "remedyLocus": "remedyExperiments",
            "unknown": "unknownExperiments",
        },
        # M2 (design.md), task 1.4: bilingual, exactly THREE capturing
        # groups -- `_impact_class` reads `match.group(1) or match.group(2)
        # or match.group(3)`, so a fourth or a second group is a live
        # defect, not a style choice. Asserted directly in
        # `tests/test_experimental_implementation.py`.
        #
        # Group 1 is the shared convention's own prose form (`(Exp. E1)`);
        # groups 2 and 3 are the digits-only forms this skill read before
        # 0.14.0 (`Exp. 3`, `Experiment (3)`, `Experimentos (3)`), kept so
        # an existing revision's citations keep counting.
        "citation_pattern": (
            _PROSE_REFERENCE
            + r"|(?:Exps?|Experiment)\.?\s*\(?(\d+)\)?|"
            r"Experimentos?\s*\((\d+)\)"),
    },
    "vocabulary": {
        "subject_singular": "experiment",
        "subject_plural": "experiments",
        "subject_singular_es": "experimento",
        "subject_plural_es": "experimentos",
        "subject_collective": "experimentation",
        "subject_collective_es": "experimentación",
        "artifact_noun": "protocol",
        # D6: the namespace word (found via `kit.root`'s own path text)
        # plus every subject-vocabulary value measured ABSENT from the
        # engine -- see this module's own docstring for the measured
        # counts. Deliberately excludes "experiment"/"experiments"/
        # "protocol", which the engine already spells as general machinery.
        "names": [
            "experimental-implementation",
            "experimento", "experimentos",
            "experimentation", "experimentación",
        ],
    },
    # Slice C (`the-second-document-verified-on-its-own-terms`, design.md
    # M2/D8): the experiments document (`documents[0]`, unchanged from
    # Slice A -- no per-document overlay, so it keeps resolving from the
    # top-level `provenance.*`/`findings.*` scalars above), and the
    # mathematical proposal (`documents[1]`), landed here as this
    # change's LAST write -- after the per-document fold (C2a) and the
    # per-document citation matching (C2b) both already read it against a
    # fixture the shipped fold could not pass. `documents[1]` declares its
    # OWN complete per-document vocabulary overlay (all five leaves,
    # design.md D1's all-or-nothing rule), matching `proposal-
    # implementation`'s own established "equations" vocabulary for this
    # exact domain -- never inheriting document 0's "experiments" values
    # by omission passing silently as agreement.
    "documents": [
        {
            "directory": _FORGE_ROOT / "experiments",
            "label": "experiments",
            # `a-data-directory-somebody-can-owe` (B2, design.md D1/D10):
            # the REAL marker, declared last -- only after B1 proved the
            # detector against a fixture. Matches the exact literal
            # `experimental-deliberation` already enforces on this same
            # domain's own documents (`preservation-experimental.ts`'s
            # `DATASET = DECLARATION("Dataset")`, spec `experimental-
            # plan-declarations`'s own `**Dataset:** ...` line): a
            # revision this domain publishes either already carries this
            # exact line-leading marker or it does not, and `verify` can
            # now say which.
            "dataset_marker": "**Dataset:**",
            # The experiment heading, from the shared convention (A7,
            # `cross-skill-consistency`): an experiment is a heading of any
            # level carrying its `[exp:<id>]` declaration -- exactly what
            # `experimental-deliberation` writes and validates -- and its
            # block runs to (not including) the next heading of the same or
            # a higher level, or the end of the text.
            #
            # Legacy read, never a rewrite: before 0.14.0 this skill knew
            # only a bare `## N` heading, so published revisions carry
            # either that alone or `## N` with a nested `[exp:<id>]`
            # heading. Both still read. A legacy `## N` block declares
            # `N` and every `[exp:<id>]` nested in it, and
            # `block_aliases` makes the engine treat ids one block
            # declares together as one locus, so a finding citing the old
            # `N` and one citing `<id>` name the same experiment.
            "block_locator": {
                "pattern": (
                    r"(?m)(?:^## (?=\d+$)|^#{1,6}[ \t][^\n]*?" + _DECLARES
                    + r"(?=" + _IDENTIFIER + r"\]))(" + _IDENTIFIER + r")"),
                "block_pattern": (
                    r"(?ms)^(#{1,6})[ \t](?:(?<=^## )\d+|[^\n]*?" + _DECLARES
                    + _IDENTIFIER + r"\][^\n]*)$.*?(?=\n(?!\1#)#{1,6}[ \t]|\Z)"),
                "identity": "## {value}",
                "block_aliases": True,
            },
            # The section unit `verify`'s per-section drift speaks in
            # (`cross-skill-consistency`, B1): the shared section-label
            # convention (`_core/conventions/sections.json`), which still
            # reads a legacy `## N` heading, plus an experiment heading's own
            # `[exp:<id>]` declaration as its marker.
            "section_heading": {
                **SECTION_CONVENTION,
                "marker": (r"^#{1,6}[ \t][^\n]*?" + _DECLARES + r"("
                           + _IDENTIFIER + r")\]"),
            },
            # `the-agreement-nothing-computes` (Slice D, design.md D5,
            # task 2.7): THIS document -- the experiments document -- is
            # the one that cites the mathematical proposal's declared
            # claims, `[claims:N]` resolving against `documents[1]`'s own
            # `block_locator.pattern` findings (`resolves_against:
            # "proposal"`, that entry's own `label`). One capturing group,
            # the identifier class copied from
            # `reference-experimental.ts::IDENTIFIER` verbatim (design.md
            # D5) so a crossing id is spelled exactly as that domain
            # already spells identifiers.
            "cross_citation": {
                "pattern": r"\[claims:([A-Za-z0-9][A-Za-z0-9._-]*)\]",
                "resolves_against": "proposal",
                "out_of_scope": _OUT_OF_SCOPE,
            },
        },
        {
            "directory": _FORGE_ROOT / "proposals",
            "label": "proposal",
            # This document never owes a dataset -- stays `None`
            # permanently (design.md D10).
            "dataset_marker": None,
            # `the-agreement-nothing-computes` (Slice D, design.md D1):
            # the mathematical proposal's own LaTeX form -- today's exact
            # engine bytes, the same declaration `proposal-implementation`
            # makes for its own single document.
            "block_locator": {
                "pattern": r"\\tag\{([^}]+)\}",
                "block_pattern": r"(?s)\$\$.*?\$\$",
                "identity": "\\tag{{{value}}}",
            },
            # `the-agreement-nothing-computes` (Slice D, design.md D5,
            # task 2.7): the mathematical proposal cites no experiments
            # document -- `None`, this leaf's own legal declared absence,
            # correctly indexed here (this entry already IS `documents[1]`).
            "cross_citation": None,
            "claim_key": "equations",
            "locus_key": "equations",
            "remedy_locus_key": "remedy_equations",
            "notation_keys": {
                "locus": "equations",
                "remedyLocus": "remedyEquations",
                "unknown": "unknownEquations",
            },
            "citation_pattern": (
                r"Ecs?\.?\s*\(?(\d+)\)?|Eq\.?\s*\(?(\d+)\)?|"
                r"Ecuaciones?\s*\((\d+)\)"),
        },
    ],
    # `the-holder-each-skill-declares` (design.md D1/D4, tasks.md 1.6):
    # this skill's own declared checklist holder -- a distinct filename
    # from the sibling's `AGREED.md`, closing the collision the two
    # skills' shared engine and product-folder shape would otherwise let
    # them write into each other's holder.
    "holder": {
        "filename": "Experimental_AGREED.md",
        "headings": ("# Agreed", "## Ladder"),
        "scaffold": "# Agreed\n\n## Ladder\n",
    },
}
