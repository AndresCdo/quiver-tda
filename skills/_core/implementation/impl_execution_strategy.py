"""One pure rule for whether a job needs a remote worker, shared by two
callers that ask the identical question about the identical facts:
`probe` (which only reports) and, in a later slice, `gate` (which
refuses on it). Before this module existed there was no such rule at
all -- a caller inventing its own version of "does this need to be
sent remotely" is exactly how two commands would quietly disagree
about the same job.

This module answers `necessity: "must-remote" | "local-sufficient" |
"optional"` per job, and -- since "optional" means the recorded facts
do not decide, never "you may skip it" -- always names which fact was
missing. It never raises, and it never composes a sentence a caller
reads aloud, the same restraint `impl_availability.launch_available`
already holds: a caller that must refuse loudly wraps this verdict in
whatever exception shape it already raises.

Every fact this rule needs arrives as a keyword argument, already
computed by whichever caller is asking. This module opens no file,
reads no argument list, and never derives "locally tolerable" from a
measured wall-clock on its own -- the target declares the budget
(`generate-job --local-budget-seconds`, recorded as `run-config.json`'s
`localBudget.seconds`), and this module only compares. A target that
declared nothing is silence, not a default of zero: silence resolves
to `optional`, with a `reason` naming exactly what was missing, never
to a threshold this module invented.
"""
from __future__ import annotations

#: `results_status` values that mean no usable measurement exists at
#: all -- distinct from `"stale"` (a measurement exists, against the
#: wrong revision) and `"piloted"` (a measurement exists, below the
#: declared scale) and `"unknown"` (a measurement exists, staleness
#: merely unestablished). Only these two carry no reduction to project
#: a cost from in the first place.
_UNMEASURED_RESULTS_STATUSES = frozenset({"absent", "unreadable"})


def _numeric(value: object) -> float | int | None:
    """`value` when it is a real number, `None` otherwise -- `bool` is
    deliberately excluded even though `isinstance(True, int)` is true
    in Python, because a caller's `seconds`/`projectedSeconds` field
    being a boolean is a shape defect, not a zero- or one-second budget.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _classify_one(job: dict, *, results_status: str, cost_forecast: dict | None) -> tuple[str, str]:
    """The five-rule ladder (design D3), in the order every mutation
    proof below assumes and no caller may reorder.
    """
    # Rule 1: the target's own record already sits at declared full
    # scale. There is no run left to send, hardware or not -- checked
    # first and short-circuiting, ahead of every other fact.
    if results_status == "current":
        return "local-sufficient", "results.current"

    # Rule 2: the job DECLARES an accelerator. This asks only what the
    # target declared, never what this machine has -- a pure rule
    # cannot look, and "does this laptop have the card" is a different
    # question from "does this job need one".
    if job.get("accelerator"):
        return "must-remote", "accelerator.declared"

    # Rules 3-4 both need two numbers: the target's own declared
    # tolerance, and the pilot-projected cost of the full run. Neither
    # is inferred here -- a caller that never declared a budget, or
    # whose search never produced a projectable forecast, gets no
    # substitute value in its place.
    local_budget = job.get("localBudget")
    budget_seconds = (
        _numeric(local_budget.get("seconds"))
        if isinstance(local_budget, dict) else None
    )
    projected_seconds = _numeric((cost_forecast or {}).get("projectedSeconds"))

    if budget_seconds is not None and projected_seconds is not None:
        if projected_seconds > budget_seconds:
            return "must-remote", "budget.exceeded"
        return "local-sufficient", "budget.within"

    # Rule 5: the recorded facts do not decide. `reason` always names
    # which one is missing, in this priority: no measurement exists at
    # all (the more fundamental gap) outranks a merely-undeclared
    # budget, which in turn outranks a budget that IS declared but has
    # nothing to compare against yet.
    if results_status in _UNMEASURED_RESULTS_STATUSES:
        return "optional", "results.unmeasured"
    if budget_seconds is None:
        return "optional", "budget.undeclared"
    return "optional", "forecast.unprojectable"


def classify_remote_necessity(*, jobs: list[dict], results_status: str,
                              cost_forecast: dict | None) -> dict:
    """Whether each of `jobs` must run remotely, and why not when it is
    undecided.

    `jobs` is `[{"job": str, "accelerator": dict | None,
    "localBudget": dict | None, "smokeReady": bool}]` -- the exact row
    shape `remote_execution_jobs_state()` already assembles once
    `accelerator`/`localBudget` are read out of the same open
    `run_config` it already opens (design D3: no second discovery).
    `smokeReady` rides along in that row for shape consistency with its
    producer; no rule below inspects it.

    `results_status` and `cost_forecast` carry no default, the SAME
    discipline `launch_available` already applies to `disagreements`:
    a caller that forgets one fails the call itself, loudly, rather
    than being read as an absence and silently widening a verdict.
    `results_status` is `probe_state()`'s own `status` field
    (`"absent"|"unreadable"|"unknown"|"current"|"stale"|"piloted"`),
    read once and shared across every job in `jobs` -- it is a fact
    about the target's own record, not about any one job.
    `cost_forecast` is `search_cost_forecast()`'s own return, or
    `None` when nothing was ever declared to project from.

    Returns `{"jobs": {job: {"necessity": ..., "reason": ...}},
    "summary": {"mustRemote": int, "localSufficient": int,
    "optional": int}}`.
    """
    verdicts: dict[str, dict] = {}
    summary = {"mustRemote": 0, "localSufficient": 0, "optional": 0}
    summary_key = {
        "must-remote": "mustRemote",
        "local-sufficient": "localSufficient",
        "optional": "optional",
    }
    for job in jobs:
        necessity, reason = _classify_one(
            job, results_status=results_status, cost_forecast=cost_forecast)
        verdicts[job["job"]] = {"necessity": necessity, "reason": reason}
        summary[summary_key[necessity]] += 1
    return {"jobs": verdicts, "summary": summary}
