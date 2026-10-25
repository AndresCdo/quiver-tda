"""This skill's own Cut-1 domain profile for the shared implementation
engine (`_core/implementation/engine/implementation_engine.py`).

Mirrors `domain-profile.ts`'s `artifact.directory`-style resolution: every
value here is computed from THIS file's own location, which moves as one
unit with the skill -- never from the engine's location, which the launcher
(`scripts/implementation_cli.py`) sets `IMPLEMENTATION_DOMAIN_PROFILE` to
point at.

Cut-1 field set (design.md D3, amended 2026-09-11 -- operator ruling on task
7.5's non-interference finding), each earning its place by being read:

- `kit.root` -> the engine's `SKILL_ROOT` (19 reader lines). Non-optional:
  `SKILL_ROOT` breaks the instant the engine moves, and breaks silently.
- `cli.path` -> the engine's `CLI_PATH` -> `CLI_INVOCATION` -> 4 message
  builders. Cut 1's single silent failure mode, and the mutation surface for
  R2/D4: one line in this file, instead of an edit inside 17,100.
- `objective` -> the engine's `OBJECTIVE_FLOW`, moved here VERBATIM (the
  text does not change; this is a relocation, not a rewrite). Read TWICE
  from outside the engine: stamped into every refusal this skill's engine
  invocation raises (`impl_domain_profile.py`'s own module docstring), and
  discovered by `tests/test_agents.py`'s cross-skill north lock, which walks
  THIS SKILL'S OWN directory tree (never the engine's) for a literal
  module-level `OBJECTIVE_FLOW` assignment -- which is exactly why it must
  physically live here and not in the shared engine: a second skill built on
  this same engine needs its OWN north, different stages, different
  arrival, and cannot get one by editing the engine, which is precisely what
  this seam exists to prevent (see the archived
  `2026-09-09-a-north-a-second-domain-can-hold` precedent on the
  deliberation side, where `proposal-deliberation/profile.ts` and
  `experimental-deliberation/profile.ts` each declare their own `objective`
  and `_core/deliberation/engine/domain-profile.ts` hardcodes neither).

Cut-2 field set (`the-domain-crosses-the-seam`, design.md D1/D7), fifteen
leaves landed one at a time (S3-S9), plus `vocabulary.names` landed at S13
alongside the two neutrality locks it exists to serve. Each carries TODAY'S
EXACT LITERAL BYTES the engine used to hardcode -- a profile supplying the
same literal composes the same output, which is what keeps all 28 sealed
digests byte-identical (design.md's whole bar). See design.md D1's table for
each leaf's reader and its predicted digest mover; D2 for why the provenance
side shares one read/write leaf per key while the findings side splits read
keys from wire keys; D6 for why `documents.label`'s value ("proposal") is
NOT a member of `vocabulary.names` below -- that word collides with 78 of
152 campaign-proposal hits elsewhere in this engine and is governed by its
own three-layer exclusion test instead.

`document_reader`, `cli_invocation`, `provenance.drift_unit_key`,
`provenance.revision_key`, `documents.marker` remain out of scope --
`provenance.drift_unit_key` does not exist at all (it IS the shared coarse
key `"sections"`, kept hardcoded in the engine by the B2 ruling); the other
four carry their own recorded reasons in design.md D1.
"""
from __future__ import annotations

import json
from pathlib import Path

# The canonical tree is `skills/<skill>/impl_profile.py`, one level
# shallower than upstream's `.claude/skills/<skill>/` anchor, so the repo
# root is `parents[1]`, not `parents[2]`.
_SKILL = Path(__file__).resolve().parent
_FORGE_ROOT = _SKILL.parents[1]

#: The ONE section-label convention, shared with `experimental-implementation`:
#: what a section heading's leading label looks like, so `verify`'s
#: per-section drift speaks in the labels a managed revision actually carries
#: (`cross-skill-consistency`, B1). Read, never respelled here.
SECTION_CONVENTION = {
    key: value for key, value in json.loads(
        (_SKILL.parent / "_core" / "conventions" / "sections.json")
        .read_text(encoding="utf-8")).items()
    if not key.startswith("$")}

#: WHY THIS SKILL WAS INVOKED, AND WHERE IT HAS TO ARRIVE.
#:
#: Declared, invariant, and deliberately independent of anything on disk.
#: Every other reading the engine does answers *where am I* by measuring
#: products -- `walk` the ledger, `flowActs` what is owed, `flowDestination`
#: the rung. This answers a question none of them can: *what is this for*.
#: A session that hits an error, an interruption, or a gap consults it,
#: locates itself, resolves what blocks, and rejoins -- rather than
#: improvising forward, which is what an agent does when a blocker detaches
#: it from the purpose.
#:
#: **It is not the agreements and does not replace them.** What the
#: mathematics says lives in the managed revision; what was settled about
#: this repository lives in its `AGREED.md`. This says only what the skill
#: is FOR, which is the one thing neither of those states and no artefact
#: implies.
#:
#: Each stage names what it establishes and how a reader knows it is behind
#: them. The conditions are written to be READ, not computed: a stage
#: derived from products would make the purpose depend on the products,
#: which is exactly the dependency this exists without.
#:
#: Discovered by `tests/test_agents.py::_python_objective` as a module-level
#: literal named exactly `OBJECTIVE_FLOW` -- never wrap this in a function
#: call or a derived expression, or that AST-literal walk stops finding it.
OBJECTIVE_FLOW = {
    "purpose": (
        "carry the agreed formulation as far as complete runs that can be "
        "reported -- not a green verification, not a passing rehearsal"),
    "stages": [
        {"stage": "standing",
         "establishes": "a repository to write the mathematics into: isolated "
                        "under `implementations/` with an interpreter of its "
                        "own, laid out the way this skill expects, the kit's "
                        "destinations materialized, and the map from "
                        "mathematical object to module approved",
         "behindWhen": "`structure` reports no scaffold gaps and "
                       "`__implementation__` carries the revision and "
                       "premises the map was approved with -- which is what "
                       "`materialize --stage objects` refuses without"},
        {"stage": "fidelity",
         "establishes": "the code says what the bound revision says, and every "
                        "claim it makes carries an invariant with a test",
         "behindWhen": "`fidelity` is clean and the target's own suite is green "
                       "under its own interpreter"},
        {"stage": "audit",
         "establishes": "what the formulation gets wrong, established over the "
                        "declared sweep, with each remedy ruled admissible "
                        "before it is measured and validated after",
         "behindWhen": "`audit` is no longer `incomplete`"},
        {"stage": "declaration",
         "establishes": "what the experiment compares, over which statistical "
                        "unit, by which metric, and what it produces",
         "behindWhen": "`__implementation__`'s premises are answered and the "
                       "benchmark declaration is answered rather than "
                       "sitting at its scaffolded empty value"},
        {"stage": "rehearsal",
         "establishes": "the declared flow runs end to end with its own "
                        "notebooks, and the document a person reads agrees "
                        "with the run",
         "behindWhen": "the pilot is complete and `report` is `ok`"},
        {"stage": "full-scale",
         "establishes": "every step routed to where it was decided to run, and "
                        "executed there at the scale the protocol declares",
         "behindWhen": "this is the arrival; it is behind nobody"},
    ],
    "arrival": (
        "complete runs at the declared scale, local or remote as each step "
        "declares, with the record they leave"),
    # Said here because a blocked agent needs it most: some stops are not
    # defects and must not be repaired. Publishing a commit and authorizing a
    # launch are decisions a person owes, and an agent that treats them as
    # blockers to resolve will either stall on them or take them.
    "humanStops": [
        "authorizing that code be written at all, which nothing below the gate "
        "may start without",
        "approving the map from mathematical object to module, and the "
        "revision and premises recorded beside it",
        "publishing the commit a worker would clone",
        "authorizing a launch, which is hours of somebody's quota",
    ],
}

PROFILE = {
    "kit": {"root": _SKILL},
    "cli": {"path": _SKILL / "scripts" / "implementation_cli.py"},
    "objective": OBJECTIVE_FLOW,
    "provenance": {
        # `unreached_mathematics`, `benchmark_unfaithfulness`, `wiring_proposal`,
        # `cmd_verify`'s module row, `authored_package_init` -- the read key and
        # the emitted key are the SAME leaf (design.md D2, "the exact silent
        # mismatch this cut exists to remove").
        "claim_key": "equations",
        # `authored_package_init`'s writer (design.md D3): moves VERBATIM, one
        # leaf, not composed from `claim_key` + a template -- composing would
        # leave the engine holding this sentence's English grammar.
        "authored_init_sentence": (
            "Each module declares the sections and equations it implements in\n"
            "`__provenance__`, and every invariant listed there has a matching\n"
            "test under tests/.\n"),
    },
    "findings": {
        # `remedy_compatibility`, `cmd_admit`'s verdict loop, `cmd_handoff`'s
        # item builder, `cmd_verify`'s audit block.
        "locus_key": "equations",
        # `finding_impact`, `remedy_compatibility`, `cmd_admit`, `cmd_handoff`
        # (including its `selectedEntryId` branch), `cmd_verify`'s audit block.
        "remedy_locus_key": "remedy_equations",
        # `finding_impact`'s returned dict, `cmd_handoff`'s item, `remedy_
        # compatibility`'s return, `cmd_verify`'s audit block. Wire spelling is
        # camelCase; read spelling is snake_case -- one leaf could not serve
        # both without the engine transliterating (design.md D2).
        "notation_keys": {
            "locus": "equations",
            "remedyLocus": "remedyEquations",
            "unknown": "unknownEquations",
        },
        # M1 (design.md): the `names` lock reads the engine's whole text, so
        # `CITATION_RE`'s pattern string moves here too -- read by
        # `finding_impact`.
        "citation_pattern": (
            r"Ecs?\.?\s*\(?(\d+)\)?|Eq\.?\s*\(?(\d+)\)?|Ecuaciones?\s*\((\d+)\)"),
    },
    "vocabulary": {
        # M2 (design.md): the subject vocabulary is bilingual, three
        # grammatical forms -- English singular/plural, Spanish
        # singular/plural, and a mass noun in both languages. Seven leaves.
        "subject_singular": "equation",
        "subject_plural": "equations",
        "subject_singular_es": "ecuación",
        "subject_plural_es": "ecuaciones",
        "subject_collective": "mathematics",
        "subject_collective_es": "matemática",
        # `authored_package_init`'s `"{name} formulation"`.
        "artifact_noun": "formulation",
        # S13 (design.md D7): both neutrality locks, and nothing else --
        # that "nothing else" is the field's own justification. Declared
        # from the measurement's own token list (Phase 0.5's fresh scan),
        # never from what happens to pass. Deliberately excludes "proposal"
        # -- that word collides with 78 of 152 campaign-proposal hits
        # elsewhere in this engine and is governed by its own three-layer
        # exclusion test instead (design.md D6).
        "names": [
            "equation", "equations", "ecuación", "ecuaciones",
            "mathematics", "matemática", "formulation",
        ],
    },
    # `the-holder-each-skill-declares` (design.md D1/D4, tasks.md 1.5): the
    # 8th top-level `PROFILE` section -- this skill's own declared
    # checklist holder. `AGREED.md` is not a new choice: it is the name
    # already in use by the live target and by `tests/seal/corpus.py:272`,
    # so this leaf is a zero-behavioural-delta declaration of today's
    # fact, the same discipline `block_locator` (task 1.7) already keeps.
    # Placed BEFORE `documents` deliberately: `documents` must stay the
    # LAST top-level key, or its own closing `],\n}` bytes stop being the
    # unique anchor `tests/test_implementation_domain_mutation.py::
    # OrFoldIndexHardcodeMutationTests` splices its own second document
    # into (measured, not assumed -- moving `holder` after `documents`
    # broke exactly that anchor on the first apply attempt).
    "holder": {
        "filename": "AGREED.md",
        "headings": ("# Agreed", "## Ladder"),
        "scaffold": "# Agreed\n\n## Ladder\n",
    },
    # Cut 3 (`a-revision-is-two-documents`, design.md D4): `documents` is a
    # LIST. This skill declares exactly ONE entry, so every byte the engine
    # emits from it -- `DOCUMENTS_DIRECTORY`, `DOCUMENTS_LABEL`, both derived
    # from `DOCUMENTS[0]` -- is unchanged from Cut 1/2's scalar shape.
    "documents": [
        {
            # `proposals_root()` -> `revision_source`, `revision_discovery`,
            # and the 5 hardcoded-path refusals. Required, absolute,
            # existence NOT required (M3) -- validated by its own resolver
            # tier, per entry, never `_REQUIRED_NESTED`'s exists()-walk.
            "directory": _FORGE_ROOT / "proposals",
            # Those same 5 refusals' prose, and
            # `ARMS_UNDECLARED_CONSEQUENCE`. Deliberately NOT a member of
            # `vocabulary.names` (design.md D6): this exact word collides
            # with 78 of 152 campaign-proposal hits elsewhere in the engine
            # and is governed by its own three-layer exclusion test.
            "label": "proposal",
            # `a-data-directory-somebody-can-owe` (B1, design.md D1,
            # ruling 2): required, own tier -- `None` states out loud that
            # this domain demands no dataset. The leaf's own detector never
            # opens a file for a `None` entry (D1 property 1), so this
            # sibling's 28 sealed digests stay byte-identical.
            "dataset_marker": None,
            # `cross-skill-consistency` (B1): the shared section-label
            # convention `verify`'s per-section drift speaks in.
            "section_heading": SECTION_CONVENTION,
            # `the-agreement-nothing-computes` (Slice D, task 1.7):
            # TODAY'S EXACT HARDCODED BYTES, written down rather than
            # inherited from the engine -- the whole reason this leaf is a
            # zero-delta edit against `tests/seal/`'s 28 digests, asserted
            # in `tests.seal`, never inferred. `(?s)` carries `DISPLAY_BLOCK_
            # RE`'s own `re.DOTALL` flag inline, so the resolver compiles
            # every pattern flag-free.
            "block_locator": {
                "pattern": r"\\tag\{([^}]+)\}",
                "block_pattern": r"(?s)\$\$.*?\$\$",
                "identity": "\\tag{{{value}}}",
            },
            # `the-agreement-nothing-computes` (Slice D, design.md D5,
            # task 2.7): required, own tier, NULLABLE -- `None` here.
            # This skill declares exactly one document, so there is no
            # second declared label in ITS OWN `documents` list to cite:
            # the mathematical proposal cites no experiments document.
            # This is the sibling's SECOND sanctioned edit to this file
            # in ten changes, after `block_locator` (task 1.7) -- the
            # required shape asks it to write down a value that is
            # already true, never an engine default it never chose.
            "cross_citation": None,
        },
    ],
}
