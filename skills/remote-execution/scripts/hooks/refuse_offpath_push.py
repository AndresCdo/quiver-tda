#!/usr/bin/env python3
"""A tripwire, not a gate (design §5, `the-position-nobody-holds`): refuses
a `Bash` invocation that mentions a service's own push surface without
ALSO invoking `remote_cli.py`.

The load-bearing precondition is `_verify_launch_authorization()` inside
`submit` itself (`remote_cli.py`) -- it is the ONLY mechanism this change
trusts to keep a full-scale launch honest, because it reads a record no
caller's own argv could have produced. This script covers only the residue
that precondition structurally cannot see: a launch that never calls
`submit` at all, and so never reaches it. This repository has produced
exactly that shape once -- a hand-rolled probe lost `mode=smoke` and ran a
full-scale search on a metered account -- which is the incident this
script exists to catch a repeat of, nothing more.

Reads a `PreToolUse` hook payload for the `Bash` tool from stdin (Claude
Code's own hook contract: a JSON object carrying `tool_name` and
`tool_input`, the latter holding `command` for the `Bash` tool). Exits `2`
with a refusal on stderr when the command names a push surface without
naming `remote_cli.py` anywhere in it; exits `0` silently otherwise,
including when the payload cannot be read at all -- a tripwire that cannot
parse its own input refuses NOTHING, it never fails closed onto an
unrelated command.

Push surfaces are never hardcoded here. Each adapter under
`scripts/adapters/` declares its own module-level `PUSH_SURFACE: tuple[str,
...]` -- `adapters/kaggle.py` is the one place this skill lets a service be
named (its own docstring's confinement rule), and this script only ever
READS that declaration. A second service is covered by that service's own
adapter declaring its own tuple, never by editing this file.

What this predicate explicitly does NOT do: read a job's mode. `mode=smoke`
is a `submit`-time argv flag written into `run_config` on the `Job` object
(`remote_cli.py`'s own `cmd_submit`), never a job-folder property readable
before submission -- a predicate that tried to classify scale from disk
would be unimplementable, and design §5 records this so it is not
re-proposed.

Honest bound, stated rather than implied: `python -c "..."`, a heredoc, or
a script file that itself shells out defeats simple substring matching.
This hook catches the shape that actually happened once and nothing more
-- it is never the reason a launch is safe. That reason is
`_verify_launch_authorization()`, which this script does not replace and
does not need to be trusted as strongly as.

Run with any Python 3.10+ (stdlib-only):
    python3 -m unittest tests.test_remote_execution
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ADAPTERS_DIR = Path(__file__).resolve().parents[1] / "adapters"

#: The literal substring that means "this command already routes through
#: the one place `_verify_launch_authorization()` lives" -- present, the
#: predicate below never refuses, whatever else the command also mentions.
SUBMIT_MARKER = "remote_cli.py"


def _load_push_surfaces(adapters_dir: Path = ADAPTERS_DIR) -> tuple[str, ...]:
    """Every `PUSH_SURFACE` token declared by every adapter module.

    Reads `adapters/*.py` by source path, the same `spec_from_file_location`
    technique every sibling loader in this skill already uses, and reads
    only each module's own declared `PUSH_SURFACE` constant -- nothing
    about a service's own vocabulary is invented here, only relayed.

    A module this scan cannot import at all (a missing optional dependency,
    for instance) is skipped rather than raised on: this script's own job
    is a best-effort tripwire, never a gate load-bearing enough to refuse
    the CALLER'S command because one adapter module failed to import in
    the hook's own process.
    """
    surfaces: list[str] = []
    if not adapters_dir.is_dir():
        return ()
    for path in sorted(adapters_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        spec = importlib.util.spec_from_file_location(
            f"_push_surface_scan_{path.stem}", path
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        declared = getattr(module, "PUSH_SURFACE", ())
        surfaces.extend(str(token) for token in declared)
    return tuple(surfaces)


def offpath_push(command: str, push_surfaces: tuple[str, ...]) -> str | None:
    """The matching push-surface token, or `None` when `command` is clean.

    A command is refused when it names a push surface AND does not also
    name `remote_cli.py` -- both conditions, never one alone: a command
    that legitimately runs `remote_cli.py submit ...` may well mention
    `kernels_push` in a comment or a log line without that being the
    off-path shape this predicate exists to catch.
    """
    if SUBMIT_MARKER in command:
        return None
    for token in push_surfaces:
        if token and token in command:
            return token
    return None


def main(argv: list[str] | None = None) -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    is_antigravity = False
    if command is None:
        tool_call = payload.get("toolCall")
        if isinstance(tool_call, dict):
            is_antigravity = True
            args = tool_call.get("args")
            if isinstance(args, dict):
                command = args.get("CommandLine")
    if not isinstance(command, str) or not command:
        if is_antigravity:
            sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        return 0

    matched = offpath_push(command, _load_push_surfaces())
    if matched is None:
        if is_antigravity:
            sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        return 0

    refusal_msg = (
        f"refusing: this command names a push surface ({matched!r}) "
        f"without invoking {SUBMIT_MARKER} -- a launch that skips `submit` "
        "skips its own authorization precondition "
        "(`_verify_launch_authorization()`). This is a tripwire covering "
        "the residue that precondition cannot see, not a replacement for "
        "it: route the launch through `remote_cli.py submit` (or "
        "`--smoke` for a rehearsal) instead.\n"
    )
    if is_antigravity:
        sys.stdout.write(json.dumps({"decision": "deny", "reason": refusal_msg}) + "\n")
        return 0

    sys.stderr.write(refusal_msg)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
