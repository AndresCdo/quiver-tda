"""One pure rule for whether a launch may proceed, shared by two callers.

Two commands ask the identical question about the identical facts: may a
launch proceed for this job, given the position ladder's current state and
its readiness measurement? Before this module existed, the answer lived
inside one command's own refusal ladder, and a second command computing its
own version of the same five checks is exactly how the two would quietly
drift apart from each other -- one accepting a launch the other refuses on
identical facts, discovered only when somebody compared them by hand.

This module answers `available: bool` and, when the answer is `False`,
which of five reasons it is -- nothing more. It never raises, and it never
composes a sentence a caller reads aloud: a launch verb's own prose names
its sibling commands and their own vocabulary, and this module is shared by
more than one such verb, so it may not commit to either one's words. A
caller that must refuse loudly wraps this verdict in whatever exception
shape it already raises; a caller that must merely omit an option from a
menu reads `available` alone and never raises anything at all.

Every fact this rule needs arrives as a keyword argument, already computed
by whichever caller is asking. This module opens no file, reads no
argument list, and knows nothing about where a position ledger lives or
what a caller's own flags are spelled -- that is layout, and layout belongs
one level up, in the command that has a directory to walk.
"""
from __future__ import annotations


def position_honest(*, status: str, unbacked: list, disagreements: list,
                    shards_declared: bool) -> dict:
    """Whether the position section, as recorded, says only what was
    measured -- the honesty prefix both `launch_available` (below) and a
    caller that never asks about readiness at all share, so neither one
    computes its own version of the identical four questions.

    `status`, `unbacked` and `disagreements` are a position read's own
    fields, passed through unchanged by whichever caller already computed
    them once. `unbacked` and `disagreements` carry no default: a caller
    that forgets one fails the call itself, loudly, rather than being read
    as an empty list and letting a contradicted or an unmeasured item
    through as if it agreed.

    `shards_declared` also carries no default. It answers one question
    only: did THIS invocation resolve any directory at all to measure a
    `@shard` witness against -- an explicit override, or the repository's
    own declared location? A ticked `@shard` item that stays unmeasured
    because nothing ever named where its evidence lives is a different
    fact from one whose declared location was consulted and still came back
    silent, and the two must not read as the identical claim: the first is
    "nobody was told where to look", the second is "somebody looked, and
    found nothing that speaks for this mark". Folding them into one code
    would keep asserting the general one is true even for a target that has
    since named its shard directory correctly and simply never re-measured.

    Returns `{"honest": bool, "code": str | None, "facts": dict}`. `code`
    is one of `POSITION_ABSENT`, `POSITION_STALE`, `POSITION_UNBACKED`,
    `POSITION_SHARDS_UNDECLARED`, `POSITION_DISAGREES`, checked in that
    order. `POSITION_SHARDS_UNDECLARED` only ever fires for a ticked
    `@shard` item whose unbacked-ness is fully explained by
    `shards_declared` being false; any other unbacked item -- of any
    witness kind, `@shard` included, once a location was actually consulted
    -- still reads `POSITION_UNBACKED`, checked first, exactly as before
    this code existed. `facts` carries whichever ordinals a caller's own
    message needs to quote; it is empty wherever no caller needs one.
    """
    if status == "absent":
        return {"honest": False, "code": "POSITION_ABSENT", "facts": {}}
    if status == "stale":
        return {"honest": False, "code": "POSITION_STALE", "facts": {}}
    undeclared = ([item for item in unbacked if item["witness"]["kind"] == "shard"]
                 if not shards_declared else [])
    real_unbacked = [item for item in unbacked if item not in undeclared]
    if real_unbacked:
        return {
            "honest": False, "code": "POSITION_UNBACKED",
            "facts": {"unbackedOrdinals": [item["ordinal"] for item in real_unbacked]},
        }
    if undeclared:
        return {
            "honest": False, "code": "POSITION_SHARDS_UNDECLARED",
            "facts": {"undeclaredOrdinals": [item["ordinal"] for item in undeclared]},
        }
    if disagreements:
        return {
            "honest": False, "code": "POSITION_DISAGREES",
            "facts": {"disagreeingOrdinals": [item["ordinal"] for item in disagreements]},
        }
    return {"honest": True, "code": None, "facts": {}}


def _shortfall_is_undeclared_shards(*, sequence: list, shards_declared: bool,
                                    attained_index: int | None) -> list:
    """The ordinals of the leveled `@shard` items that account for the whole
    rung shortfall because nothing was ever told where a shard lands -- or
    `[]` when the shortfall is anything else.

    `position_honest`'s own `shards_declared` doctrine, moved one check
    further down the ladder. That one separates "nobody was told where to
    look" from "somebody looked and found nothing" for a TICKED item, whose
    unbacked-ness it explains. This separates the identical two facts for a
    leveled item that is honestly BLANK: a `@shard:level` witness with no
    declared location derives `None`, `attained_level` then reaches no rung
    at all, and the launch was refused `RUNG_NOT_ATTAINED` -- naming a rung
    the evidence fell short of, which is true, and asking what has to run
    before it is reached, which has no answer, because nothing has to run.
    One string was never declared.

    **Fully explained, or not at all** -- the identical rule
    `position_honest` keeps. Three conditions, each of which narrows a
    misdiagnosis the other two would let through:

    - `attained_index is None`. A shortfall from a rung that WAS reached is
      not the work of an unmeasured item; something graded, and lower than
      the launch needs.
    - `not shards_declared`. A directory that was consulted and came back
      silent puts a `@shard` item on the FLOOR rung, definitely, and falling
      short from the floor is a rung fact with a rung answer.
    - every leveled item this call can see as unmeasured is one of these
      shard items. A second leveled item unmeasured for its own reason means
      declaring `shardsRoot` clears only half the shortfall, and a refusal
      naming a fix that does not fix it is worse than the vague one.

    `derived` is read through `.get`, never a bare subscript: a caller
    handing raw `parse_items` output carries no such key, and every leveled
    item then reads unmeasured -- which can only ENLARGE the set the shard
    items must exhaust, so the redirect narrows rather than widens for such a
    caller. Two-state items are skipped for the reason `attained_level`'s own
    second boundary gives: graded without the ladder, they hold no rung down
    and cannot be part of a rung shortfall.
    """
    if attained_index is not None or shards_declared:
        return []
    leveled = [item for item in sequence
               if not item["witness"].get("twostate", True)]
    unmeasured = [item for item in leveled if item.get("derived") is None]
    shards = [item for item in unmeasured if item["witness"]["kind"] == "shard"]
    if not shards or len(shards) != len(unmeasured):
        return []
    return [item["ordinal"] for item in shards]


def launch_available(*, status: str, unbacked: list, disagreements: list,
                     sequence: list, ready: bool | None, job: str,
                     shards_declared: bool, levels: list[str],
                     attained_level: str | None) -> dict:
    """Whether a launch may proceed for `job`, and why not when it may not.

    `status`, `unbacked`, `disagreements`, `shards_declared` and `sequence`
    are a position read's own fields, passed through unchanged by whichever
    caller already computed them once. `ready` is that same caller's own
    readiness measurement for `job` -- `True`, `False`, or `None` when
    nothing has measured it yet; only `True` counts as ready, so a caller
    that forgets to distinguish "measured and failing" from "never measured
    at all" cannot accidentally widen this rule by passing a `False` where
    a `None` belongs.

    `disagreements` names every item whose recorded mark contradicts its
    own fresh re-measurement -- ticked but not actually reached, or the
    reverse. It carries no default: a caller that forgets to pass it fails
    the call itself, loudly, rather than being read as an empty list and
    letting a contradicted item through as if it agreed. Two callers ask
    this one rule the identical question over the identical facts, and a
    forgotten keyword is exactly the kind of drift this module exists to
    make impossible between them.

    `levels` (the target's own declared rung ladder) and `attained_level`
    (`position_state(...)["attainedLevel"]`, already computed by both
    callers and, before this, discarded) carry no default either, for the
    identical reason: a caller that forgot to thread them through must fail
    loudly rather than have this rule silently skip the rung threshold
    below. Neither is recomputed here -- this module opens no file and
    knows no ladder vocabulary of its own, the same restraint
    `resolve_levels_declaration` keeps one layer up.

    The first four questions -- is there a position at all, is it current,
    does every tick say only what was measured, does every measurement
    agree with its mark -- are answered by `position_honest` above, called
    first and unchanged in what it checks; this function only continues
    past it. `position_honest`'s own `shards_declared` doctrine applies
    here identically: see that function's docstring for why a ticked
    `@shard` item with nowhere declared to look is a different fact from
    one whose declared location simply had nothing to report.

    Returns `{"available": bool, "code": str | None, "facts": dict}`.
    `code` is one of `POSITION_ABSENT`, `POSITION_STALE`,
    `POSITION_UNBACKED`, `POSITION_SHARDS_UNDECLARED`, `POSITION_DISAGREES`,
    `NOT_READY`, `SEQUENCE_NOT_REACHED`, `RUNG_NOT_ATTAINED`, checked in
    that order. `POSITION_SHARDS_UNDECLARED` has a second reaching point at
    the rung threshold itself (`_shortfall_is_undeclared_shards`, above):
    the same absence that explains a ticked item's unbacked-ness explains a
    blank leveled one's unmeasured rung, and answering `RUNG_NOT_ATTAINED`
    there names a rung when the cause is one undeclared string. It renames a
    refusal that already existed and never converts one into a launch -- both
    verdicts are `available: False` -- the first seven in the same order one caller's own
    refusal ladder already checked them in before this rule existed,
    preserved here so neither caller's answer moves; `RUNG_NOT_ATTAINED` is
    new and checked strictly last, so it can never move an existing
    verdict, only add one where every earlier check already passed.
    `facts` carries whichever ordinals or rung names a caller's own message
    needs to quote; it is empty wherever no caller needs one.

    **The rung threshold.** When `len(levels) >= 2`, a launch additionally
    requires `attained_level`'s own index on the declared ladder to sit at
    or above `levels[-2]` -- the floor is `levels[-2]` even on a two-rung
    ladder, where it coincides with `levels[0]`; a two-rung ladder is not
    exempt from the check, only trivially at its own floor. When
    `len(levels) < 2` the check does not apply at all: there is no
    predecessor rung for a launch to have missed, the identical "structurally
    unreachable" doctrine `_skipped_rung_detail` (`implementation_cli.py`)
    already keeps for a ladder too short to name one.
    """
    honesty = position_honest(status=status, unbacked=unbacked,
                              disagreements=disagreements,
                              shards_declared=shards_declared)
    if not honesty["honest"]:
        return {"available": False, "code": honesty["code"], "facts": honesty["facts"]}
    if ready is not True:
        return {"available": False, "code": "NOT_READY", "facts": {}}

    job_item = next(
        (item for item in sequence
         if item["witness"]["kind"] == "rehearsal"
         and item["witness"]["operand"] == job),
        None)
    if job_item is None:
        return {
            "available": False, "code": "SEQUENCE_NOT_REACHED",
            "facts": {"reason": "no_witness"},
        }
    earlier_open = [item["ordinal"] for item in sequence
                    if item["ordinal"] < job_item["ordinal"] and item["mark"] != "x"]
    if earlier_open:
        return {
            "available": False, "code": "SEQUENCE_NOT_REACHED",
            "facts": {"reason": "earlier_open",
                      "earliestOpenOrdinal": min(earlier_open),
                      "jobOrdinal": job_item["ordinal"]},
        }

    if len(levels) >= 2:
        floor_index = len(levels) - 2
        attained_index = (levels.index(attained_level)
                          if attained_level in levels else None)
        if attained_index is None or attained_index < floor_index:
            undeclared_shards = _shortfall_is_undeclared_shards(
                sequence=sequence, shards_declared=shards_declared,
                attained_index=attained_index)
            if undeclared_shards:
                return {
                    "available": False, "code": "POSITION_SHARDS_UNDECLARED",
                    "facts": {"undeclaredOrdinals": undeclared_shards},
                }
            return {
                "available": False, "code": "RUNG_NOT_ATTAINED",
                "facts": {"levels": list(levels), "attainedLevel": attained_level,
                          "requiredLevel": levels[floor_index],
                          "jobOrdinal": job_item["ordinal"]},
            }

    return {"available": True, "code": None,
            "facts": {"jobOrdinal": job_item["ordinal"]}}
