#!/usr/bin/env python3
"""The Colab launch cell — a RENDERED template, never an uploaded payload.

The adapter renders one copy per submission into a temp directory with
`SESSION_DIR` substituted (the `__SESSION_DIR__` token below), because
this file must know which session directory it is launching into and the
CLI's `exec -f` has no argument channel to tell it (measured: `exec
`takes `--session`, `--file`, `--timeout` and nothing else). The rendered
copy is executed in the kernel and never enters the job folder or the
repository.

What it does, in order:

1. spawn `executor.py` — DETACHED (`start_new_session=True`), with its
   stdout and stderr appended to `stdout.log` in the session directory,
   and with the session directory as its working directory. The child
   outlives this cell (measured live, S0 check (b)): the kernel is free
   the moment this file returns, which is what makes polling a cheap
   `exec` that never queues behind the run;
2. write `launch.json` (`pid`, `started`, `python`, `platform`) — the
   first sentinel `read_state.py` reports;
3. print exactly one compact JSON line, `{"launched_pid": N}`, which is
   the adapter's receipt that the spawn happened at all.

The log file is opened here and closed here; the child keeps its own
duplicate of the descriptor, so its output keeps flowing after this
process exits.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSION_DIR = Path("__SESSION_DIR__")

EXECUTOR_FILENAME = "executor.py"
STDOUT_LOG_FILENAME = "stdout.log"
LAUNCH_FILENAME = "launch.json"


def launch(session_dir: Path) -> dict:
    """Spawn the executor detached, record the launch, and return the
    payload that becomes `launch.json` (the caller prints its pid).

    The session directory is created here if it somehow is not (the
    adapter's remote-mkdir step runs first in production; a direct
    caller, the tests included, may not have done so) — idempotent, and
    cheaper than a spawn that dies of a missing cwd.
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    log_path = session_dir / STDOUT_LOG_FILENAME
    log = open(log_path, "ab")
    try:
        child = subprocess.Popen(
            [sys.executable, str(session_dir / EXECUTOR_FILENAME)],
            cwd=session_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()
    payload = {
        "pid": child.pid,
        "started": datetime.now(timezone.utc).isoformat(),
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "platform": sys.platform,
    }
    (session_dir / LAUNCH_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    launched = launch(SESSION_DIR)
    print(json.dumps({"launched_pid": launched["pid"]}))
