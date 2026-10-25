from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from impl_refusals import Refused

#: Run inside the TARGET's own interpreter, one dotted `module`/`function` per
#: invocation, exactly the shape `runner_invoke.resolve_callable`
#: (`remote-execution/assets/runner_invoke.py`) already resolves for a remote
#: run-config's own `{module, function}` block. Mirrored rather than imported:
#: that file lives under a sibling skill this module may not path-import from
#: (see `implementation_cli.py`'s own header comment for the three files it is
#: allowed to reach into, and `resolve_callable` is not one of them), and the
#: two shapes have already drifted once — a local step carries no `kwargs`,
#: because nothing here has the remote side's pressure to fully specify a job
#: nobody can ask about later.
#:
#: The verdict file is written TWICE, and that is the whole design:
#:
#:   1. the instant resolution succeeds, before the call — `{"outcome":
#:      "resolved"}`. This is what makes "every resolved run is recorded"
#:      true even when the call itself dies hard (`os._exit`, a segfault, a
#:      `SIGKILL`) — a killed process still leaves this line behind.
#:   2. the final outcome once the call returns or raises.
#:
#: A caller finds exactly one of five states on disk once the process exits:
#: no file at all (died before resolution — `STEP_RUNNER_SILENT`), an
#: `"unresolvable"` verdict naming which of module/function/callable failed,
#: a `"resolved"`-only file (entered the callable, then vanished — recorded
#: as `outcome: "unknown"`, never guessed at as a pass), or `"returned"` /
#: `"raised"`. The exit code is recorded beside whichever of these is found,
#: never trusted as the channel on its own: any callable can produce any
#: exit code, so only the verdict file decides which of the five happened.
#:
#: `error` on the `"raised"` branch is written by THIS process, not read back
#: from a captured `stderr` — the step's own `stdout`/`stderr` are inherited
#: by the caller live (a step can run for an hour; unlike `introspect`, its
#: output is progress, not a result channel to capture), so nothing on the
#: forge side ever sees it again once the subprocess exits. Formatting the
#: exception here, once, is the only way the ledger event's `error` field can
#: carry anything at all.
RUNNER = r'''
import importlib, json, sys, traceback

module_name, function_name, verdict_path = sys.argv[1], sys.argv[2], sys.argv[3]

def write(verdict):
    with open(verdict_path, "w", encoding="utf-8") as handle:
        json.dump(verdict, handle)

try:
    module = importlib.import_module(module_name)
except ImportError as exc:
    write({"outcome": "unresolvable", "reason": "module", "detail": str(exc)})
    sys.exit(1)

try:
    func = getattr(module, function_name)
except AttributeError as exc:
    write({"outcome": "unresolvable", "reason": "function", "detail": str(exc)})
    sys.exit(1)

if not callable(func):
    write({"outcome": "unresolvable", "reason": "notcallable",
           "detail": f"{function_name!r} on {module_name!r} is not callable"})
    sys.exit(1)

write({"outcome": "resolved"})

try:
    func()
except Exception as exc:
    traceback.print_exc()
    write({"outcome": "raised", "error": f"{type(exc).__name__}: {exc}"})
    sys.exit(1)

write({"outcome": "returned"})
'''

#: The three target-side refusals `RUNNER`'s `"unresolvable"` verdict can name,
#: mirroring `resolve_callable`'s own three (missing module, missing
#: attribute, non-callable attribute) one for one.
_UNRESOLVABLE_CODES = {
    "module": "STEP_MODULE_MISSING",
    "function": "STEP_FUNCTION_MISSING",
    "notcallable": "STEP_NOT_CALLABLE",
}


def step_environment(interpreter_dir: Path, pythonpath: Path) -> dict:
    """The child process's environment: `PATH` PREFIXED, never replaced, by
    `interpreter_dir`; `PYTHONPATH` set to `pythonpath`.

    This is the entire measured motivation for this module existing at all —
    a kernelspec's own `argv` starts with a bare `python`, resolved off
    whatever `PATH` the process that launched the kernel happened to carry,
    and a subprocess spawned with the wrong one silently launches a foreign
    interpreter: 297 notebooks execute standalone against their own venv,
    fifteen fail the moment `PATH` resolves a different one instead.

    `PATH` is prefixed, never replaced: the child still needs `git` and every
    other system tool the inherited `PATH` already carries; only the first
    hit for a bare `python` is meant to change. Every other environment
    variable this process holds passes through unchanged — a step is not run
    in a scrubbed environment, only in one whose interpreter resolution is
    corrected.

    Neither argument is defaulted or discovered here: `interpreter_dir` and
    `pythonpath` are the caller's own layout facts, handed in rather than
    reconstructed from a venv/source-root convention this module is not
    allowed to know exists.
    """
    return {
        **os.environ,
        "PATH": f"{interpreter_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(pythonpath),
    }


def run_step(interpreter: Path, module: str, function: str, *,
             cwd: Path, pythonpath: Path) -> dict:
    """Run one step, isolated, as a subprocess under `interpreter`.

    `argv` is a list (`[str(interpreter), "-c", RUNNER, module, function,
    str(verdict_path)]`) and this call never sets `shell=True` — the two
    facts together are why nothing a target's own `__steps__` entry names,
    however hostile, can reach a shell: `module` and `function` arrive as
    inert `argv` elements handed to `importlib.import_module`/`getattr`
    inside the child, never interpolated into a command line this process
    composes.

    The verdict file lives in a scratch directory this call creates and
    removes itself, never inside `cwd` — writing a temp file into the target
    was rejected precisely because the caller's own dirty-worktree guard just
    passed, and this function must not be what dirties it back.

    Returns a plain dict — `{"outcome": "returned"|"raised"|"unknown",
    "exitStatus": int, "error": str | None}` — for every state a caller is
    meant to RECORD. Raises `Refused` for every state a caller is meant to
    record NOTHING for: `STEP_RUNNER_SILENT` when the process exited leaving
    no verdict file at all (it died before resolution ever began), and
    `STEP_MODULE_MISSING` / `STEP_FUNCTION_MISSING` / `STEP_NOT_CALLABLE` when
    it resolved to "no" instead of "yes" — see `RUNNER`'s own docstring for
    the full five-row state machine `_verdict_result` reads back.
    """
    scratch = Path(tempfile.mkdtemp(prefix="papersmith-step-"))
    verdict_path = scratch / "verdict.json"
    try:
        proc = subprocess.run(
            [str(interpreter), "-c", RUNNER, module, function, str(verdict_path)],
            cwd=str(cwd), env=step_environment(interpreter.parent, pythonpath),
            shell=False,
        )
        verdict = (json.loads(verdict_path.read_text(encoding="utf-8"))
                   if verdict_path.exists() else None)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    return _verdict_result(verdict, proc.returncode, module, function)


def _verdict_result(verdict: dict | None, returncode: int,
                    module: str, function: str) -> dict:
    """Interpret one verdict-file reading against the five-row state machine
    `RUNNER`'s own docstring names, and only that — no subprocess, no I/O.

    Pulled apart from `run_step` so the whole state machine is provable by
    handing this hand-written verdict dicts directly, one call per row,
    rather than only ever reaching it by making a real subprocess die at the
    right instant.

    `verdict is None` is the first row: `run_step` passes that in when the
    process left no verdict file at all — died before resolution ever began.
    Every other row is read from `verdict["outcome"]`, exactly as `RUNNER`
    wrote it.
    """
    if verdict is None:
        raise Refused(
            "STEP_RUNNER_SILENT",
            f"the step process exited (code {returncode}) without ever "
            "writing a verdict file; it died before resolution began, so "
            "nothing here can say whether the step ran.")

    outcome = verdict.get("outcome")
    if outcome == "unresolvable":
        code = _UNRESOLVABLE_CODES.get(verdict.get("reason"))
        if code is None:
            raise Refused(
                "STEP_RUNNER_SILENT",
                f"the verdict file named an unrecognized refusal reason "
                f"{verdict.get('reason')!r}.")
        raise Refused(
            code,
            verdict.get("detail")
            or f"{module}.{function} could not be resolved ({code}).")
    if outcome == "resolved":
        # Entered the callable, then the process vanished before the second
        # write -- `os._exit`, a `SIGKILL`, an interpreter crash. A missing
        # second write is reported as an inability to tell, never as a pass.
        return {"outcome": "unknown", "exitStatus": returncode, "error": None}
    if outcome == "returned":
        return {"outcome": "returned", "exitStatus": returncode, "error": None}
    if outcome == "raised":
        return {"outcome": "raised", "exitStatus": returncode,
                "error": verdict.get("error")}
    raise Refused(
        "STEP_RUNNER_SILENT",
        f"the verdict file named an unrecognized outcome {outcome!r}.")
