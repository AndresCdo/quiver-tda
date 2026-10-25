#!/usr/bin/env python3
"""The Colab poll/fetch reader — a RENDERED template, never an uploaded
payload, for the same reason `launch.py` is one: it must know its session
directory (`__SESSION_DIR__`, substituted per submission) and `exec -f`
has no argument channel to hand it one.

It prints exactly one compact JSON line and nothing else:

    {"sessionDir": str,
     "launch": {...} | null,
     "status": {...} | null,
     "files": [...] | null,
     "stdoutTail": str | null}

Read-only by construction: it creates, deletes, downloads and executes
nothing. `launch.json`'s presence distinguishes a run that has started
from one that never did; `status.json`'s presence IS the completion
signal (`exitCode` 0 or non-zero), and its absence means the run may
still be live — the reader reports what is there, never an inference
about what is not.

A malformed JSON sentinel is NOT swallowed into `null`: it raises, the
CLI reports the failure, and the adapter refuses rather than guessing at
a state the VM never confirmed. Only a missing file is `null`.
"""
from __future__ import annotations

import json
from pathlib import Path

SESSION_DIR = Path("__SESSION_DIR__")

LAUNCH_FILENAME = "launch.json"
STATUS_FILENAME = "status.json"
FILES_FILENAME = "files.json"
STDOUT_LOG_FILENAME = "stdout.log"

# How much of the executor's log travels in every read. Bounded on
# purpose: the log grows for the whole life of the run, and a poll is
# supposed to be the cheap call. The tail is enough to carry a
# traceback's last lines into a refusal message.
STDOUT_TAIL_CHARS = 2000


def _read_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _stdout_tail(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()[-4096:]
    except OSError:
        return None
    return data.decode("utf-8", errors="replace")[-STDOUT_TAIL_CHARS:]


def snapshot(session_dir: Path) -> dict:
    return {
        "sessionDir": str(session_dir),
        "launch": _read_json(session_dir / LAUNCH_FILENAME),
        "status": _read_json(session_dir / STATUS_FILENAME),
        "files": _read_json(session_dir / FILES_FILENAME),
        "stdoutTail": _stdout_tail(session_dir / STDOUT_LOG_FILENAME),
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(SESSION_DIR)))
