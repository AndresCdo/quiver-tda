#!/usr/bin/env python3
"""Turn a worker id into a `CredentialHandle`, by running one command.

This module is the ONLY producer of a `CredentialHandle` anywhere above the
adapter seam. It builds one by running the credential owner's own
non-interactive materialize command as a CHILD PROCESS and reading exactly
one field off its stdout — never by opening a file itself, never by
importing that command's module directly. `subprocess`, `json`, `pathlib`
and this skill's own `adapter.py` are the whole list of what this file
imports; there is no `open`, no `Path.read_text`, no `Path.read_bytes`
anywhere in it.

That is what makes the structural claim true rather than merely stated: a
credential VALUE cannot enter this process's memory, not because a rule
says not to, but because nothing this module's own dependency graph is
even capable of reading one. The value is read by exactly two processes in
the whole system, neither of them this one: the materialize command's own
child process, and whatever service client a concrete adapter eventually
hands the returned path to.

Run with any Python 3.10+ (stdlib-only):
    python3 -m unittest tests.test_remote_execution
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


def _load_adapter_seam():
    """Path-import `adapter.py`, reusing an already-loaded copy under
    `remote_execution_adapter` when one exists.

    Same idiom every other sibling loader in this skill uses for the same
    correctness reason: a second, separately exec'd copy of `adapter.py`
    would define a second, distinct `CredentialHandle` dataclass with the
    same name, and a caller checking the shape this module returns against
    the one it already holds would silently disagree with an instance
    built from the second copy.
    """
    module_name = "remote_execution_adapter"
    if module_name in sys.modules:
        return sys.modules[module_name]
    script = Path(__file__).resolve().parent / "adapter.py"
    spec = importlib.util.spec_from_file_location(module_name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ADAPTER = _load_adapter_seam()


class CredentialsError(ADAPTER.AdapterError):
    """Materialization failed, timed out, or answered with something this
    module will not guess at.

    Subclasses the seam's own `AdapterError` so every caller above the
    adapter — `remote_cli.py`'s existing exception handling included —
    needs no extra case to catch a credential failure alongside every
    other refusal an adapter can already raise.
    """


SUBPROCESS_TIMEOUT_SECONDS = 60.0


def materialize(
    worker_id: str,
    *,
    accounts_cli: Path | str | None = None,
    timeout: float = SUBPROCESS_TIMEOUT_SECONDS,
) -> "ADAPTER.CredentialHandle":
    """Run `<accounts_cli> materialize --worker <id> --json` as a child
    process and return the `CredentialHandle` it names.

    `accounts_cli` names the location of that command's own script; this
    module holds no default for it and no opinion about which backend's
    credential CLI it points to — that knowledge belongs to whichever
    concrete adapter module a caller resolved a backend through, one level
    below this seam, and it is that caller's job to pass the path in. A
    missing `accounts_cli` is refused here, the same way every other
    unusable answer in this module is refused, rather than left to fail as
    an unrelated `TypeError` from the path construction below.

    This is the ONLY place in this module — and, by `adapter.py`'s own
    shape, the only place above the adapter seam at all — that ever
    produces a handle. `shell=False` with a list argv, matching every other
    subprocess call this skill makes: a worker id with shell metacharacters
    reaches argv verbatim and executes nothing. A non-zero exit, a timeout,
    unparsable stdout, or stdout missing the one field this reads is a
    refusal raised as `CredentialsError` — never a fabricated handle.
    """
    if accounts_cli is None:
        raise CredentialsError(
            f"materialize for worker {worker_id!r} has no accounts_cli "
            "configured; this module holds no default location for any "
            "service's credential CLI, so the constructing caller must "
            "supply one"
        )
    cli = Path(accounts_cli)
    argv = [sys.executable, str(cli), "materialize", "--worker", worker_id, "--json"]
    try:
        result = subprocess.run(
            argv, shell=False, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CredentialsError(
            f"materialize for worker {worker_id!r} timed out after {timeout}s"
        ) from exc
    except OSError as exc:
        raise CredentialsError(f"could not run {argv[0]}: {exc}") from exc

    if result.returncode != 0:
        raise CredentialsError(
            f"materialize for worker {worker_id!r} exited {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CredentialsError(
            f"materialize for worker {worker_id!r} did not print JSON: {exc}"
        ) from exc

    token_path = payload.get("tokenPath")
    if not token_path:
        raise CredentialsError(
            f"materialize for worker {worker_id!r} printed no 'tokenPath'"
        )
    return ADAPTER.CredentialHandle(worker_id=worker_id, token_path=Path(token_path))


def provider(
    *,
    accounts_cli: Path | str | None = None,
    override: Path | str | None = None,
) -> Callable[[str], "ADAPTER.CredentialHandle"]:
    """Build the callable an adapter's constructor accepts as `credentials`.

    `override`, when given, answers every worker with the SAME path —
    the shape a test or an already-materialized run needs, and the one
    case this function never shells out for at all. Otherwise the callable
    it returns materializes lazily, by worker id, the FIRST time an
    adapter actually asks for one: `remote_cli`'s own `poll` command never
    learns a worker id at the command line, only a submission id that only
    the adapter is permitted to split — so nothing above the seam can
    build a full mapping up front for that command. Every call re-runs
    `materialize` rather than caching a handle across calls: this function
    keeps no state of its own, and a path held past a credential's own
    rotation is a worse failure than one extra subprocess call per adapter
    method.
    """
    if override is not None:
        token_path = Path(override)

        def _override(worker_id: str) -> "ADAPTER.CredentialHandle":
            return ADAPTER.CredentialHandle(worker_id=worker_id, token_path=token_path)

        return _override

    def _materialize(worker_id: str) -> "ADAPTER.CredentialHandle":
        return materialize(worker_id, accounts_cli=accounts_cli)

    return _materialize
