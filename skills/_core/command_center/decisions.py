"""Read-only decisions timeline for the command center.

The timeline is merged on request from records the workspace already persists;
nothing is written and nothing is cached. Sources:

* ``declarations``: the ``%% paper-writing declarations`` region of
  ``paper/main.tex``. That region is replaced in place, so only the CURRENT
  state is stored: earlier values are not recoverable.
* ``proposal`` / ``experiment``: the ``.proposal-deliberation/`` and
  ``.experimental-deliberation/`` sidecars (``receipts/*.json`` and
  ``lifecycle/v1/transitions/*.json``). Edit receipts carry NO timestamp, so
  their events have ``ts: null`` and sort after dated events; the initial-revision
  receipt carries ``createdAt``, used as ``ts`` (file mtime is never used). Everything read here is plain JSON: the lifecycle store's hash and
  consistency checks are not replicated, so these events are ``verified: false``.
* ``remote-execution``: ``implementations/<repo>/<Name>/.remote-execution/
  ledger.jsonl`` (``implementation_engine`` builds
  ``target / name / '.remote-execution' / 'ledger.jsonl'``). Discovery is two
  fixed levels below ``implementations/``, never recursive. The credentials
  inbox directory is never read.

Each reader returns ``{events, status, detail?}`` with ``status`` one of ``ok``,
``absent``, ``unreadable`` or ``too_large``, so one broken source never fails
the response. Every read resolves the path, requires it to stay inside the
workspace and to be a regular file, and checks the size BEFORE reading.
"""

from __future__ import annotations

import json
import os
import re
from bisect import insort
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .atlas import _locate

MAIN_TEX_MAX_BYTES = 2 * 1024 * 1024
ITEM_MAX_BYTES = 256 * 1024
LEDGER_MAX_BYTES = 2 * 1024 * 1024
MAX_ITEM_FILES = 500
MAX_LEDGER_FILES = 20
MAX_LEDGER_LINES = 2000
MAX_DIR_NAMES = 5000
MAX_LAYOUT_NAMES = 200
MAX_SOURCE_EVENTS = 500
MAX_TOTAL_EVENTS = 1000
TEXT_MAX = 300

SOURCES = ("declarations", "proposal", "experiment", "remote-execution")

SIDECARS = {"proposal": ".proposal-deliberation", "experiment": ".experimental-deliberation"}
RECEIPTS_REL = ("receipts",)
TRANSITIONS_REL = ("lifecycle", "v1", "transitions")
LEDGER_NAME = (".remote-execution", "ledger.jsonl")

STATE_NOTE = ("Only the current state is stored: earlier values of this record "
              "are not recoverable.")

#: Transition outcomes (``MaterializationResult.outcome`` plus the three of
#: ``LifecycleTransitionEvidence``); anything else falls back to ``unknown``.
OUTCOME_SUMMARIES = {
    "COMMITTED": "Committed {op}",
    "ALREADY_COMMITTED": "Already committed {op}",
    "REJECTED": "Rejected {op}",
    "INCONSISTENT": "Inconsistent state after {op}",
    "RECOVERY_REQUIRED": "Recovery required after {op}",
}

_LEDGER_KINDS = ("submitted", "returned", "errored")
_BEGIN = re.compile(r"^%% paper-writing declarations begin sha256=[0-9a-f]{64}$")
_END = "%% paper-writing declarations end"


class DecisionsQueryError(ValueError):
    """An invalid ``source`` filter."""


def _clip(value: Any) -> str:
    return value[:TEXT_MAX] if isinstance(value, str) else ""


def _result(status: str, events: list[dict[str, Any]] | None = None,
            detail: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"events": events or [], "status": status}
    if detail:
        out["detail"] = detail
    return out


def _event(ts: Any, source: str, kind: str, summary: str, ref: str, **extra: Any) -> dict[str, Any]:
    return {"ts": ts if isinstance(ts, str) else None, "source": source, "kind": kind,
            "summary": summary, "ref": ref, **extra}


def _read_bytes(resolved: Path, cap: int) -> bytes | None:
    """Read at most ``cap`` bytes; ``None`` on an OS error or when the file grew past it."""
    try:
        with open(resolved, "rb") as handle:
            data = handle.read(cap + 1)
    except OSError:
        return None
    return None if len(data) > cap else data


def _list_names(directory: Path, want: Callable[[os.DirEntry], bool]) -> tuple[list[str], bool]:
    """Sorted entry names passing ``want``, at most ``MAX_DIR_NAMES`` of them.

    Entries are filtered BEFORE the bound, so non-matching files can never hide
    matching ones. The kept names are the smallest in sort order (deterministic
    whatever order the OS lists them in); the flag is set whenever matching
    entries were dropped.
    """
    kept: list[str] = []  # always sorted, never longer than the cap
    cut = False
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if not want(entry):
                        continue
                except OSError:
                    continue
                insort(kept, entry.name)
                if len(kept) > MAX_DIR_NAMES:
                    kept.pop()
                    cut = True
    except OSError:
        return [], False
    return kept, cut


# --------------------------------------------------------------------------
# declarations
# --------------------------------------------------------------------------
def _declaration_events(body: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for record in body.get("records") or []:
        if not isinstance(record, dict):
            continue
        id_ = _clip(record.get("id")) or "?"
        kind = _clip(record.get("kind")) or "record"
        ref = f"paper/main.tex#{id_}"
        if kind == "declaration":
            name, summary = "declaration", f"Declared {id_}"
        elif kind == "fact" and record.get("declined"):
            reason = _clip(record.get("reason"))
            name = "fact_declined"
            summary = f"Declined fact {id_}" + (f": {reason}" if reason else "")
        elif kind == "fact":
            name, summary = "fact_resolved", f"Resolved fact {id_}"
        else:
            name, summary = "record", f"Recorded {kind} {id_}"
        events.append(_event(record.get("recorded"), "declarations", name, summary, ref,
                             note=STATE_NOTE))
    return events


def read_declarations(root: Path | str) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    status, resolved, _size, _mtime = _locate(root, root / "paper" / "main.tex", MAIN_TEX_MAX_BYTES)
    if status == "absent":
        return _result("absent")
    if status == "too_large":
        return _result("too_large", detail="paper/main.tex exceeds the 2 MiB limit")
    if status != "ok" or resolved is None:
        return _result("unreadable", detail=f"paper/main.tex is {status}")
    data = _read_bytes(resolved, MAIN_TEX_MAX_BYTES)
    if data is None:
        return _result("unreadable", detail="paper/main.tex could not be read")
    lines = data.decode("utf-8", errors="replace").splitlines()
    begins = [i for i, line in enumerate(lines) if _BEGIN.match(line)]
    if not begins:
        return _result("absent")
    if len(begins) > 1:
        return _result("unreadable", detail="more than one declarations region")
    start = begins[0] + 1
    ends = [i for i in range(start, len(lines)) if lines[i] == _END]
    if not ends:
        return _result("unreadable", detail="declarations region has no end marker")
    payload = []
    for line in lines[start:ends[0]]:
        if line.startswith("%% "):
            payload.append(line[3:])
        elif line == "%%":
            payload.append("")
        else:
            return _result("unreadable", detail="declarations region has an unprefixed line")
    try:
        body = json.loads("\n".join(payload))
    except ValueError:
        return _result("unreadable", detail="declarations region is not valid JSON")
    if not isinstance(body, dict) or not isinstance(body.get("records", []), list):
        return _result("unreadable", detail="declarations region has an unexpected shape")
    return _result("ok", _declaration_events(body))


# --------------------------------------------------------------------------
# deliberation sidecars
# --------------------------------------------------------------------------
def _receipt_event(source: str, data: dict[str, Any], ref: str) -> dict[str, Any]:
    # Two shapes are written by the real engine: the initial-revision receipt
    # (initial-revision-creation.ts, carries ``createdAt``) and the edit receipt
    # (revision-receipt.ts, carries no timestamp). The file mtime is never used.
    created_at = data.get("createdAt")
    if data.get("operation") == "CREATE_INITIAL_REVISION":
        summary = f"Created initial revision {_clip(data.get('targetRevision')) or '?'}"
        return _event(created_at, source, "revision_receipt", summary, ref, verified=False)
    patches = data.get("patchCount")
    count = patches if isinstance(patches, int) and not isinstance(patches, bool) else 0
    summary = (f"Revision {_clip(data.get('sourceRevision')) or '?'} -> "
               f"{_clip(data.get('targetRevision')) or '?'} "
               f"({_clip(data.get('intent')) or 'unknown intent'}), {count} {'patch' if count == 1 else 'patches'}")
    return _event(created_at, source, "revision_receipt", summary, ref, verified=False)


def _transition_event(source: str, data: dict[str, Any], ref: str) -> dict[str, Any]:
    outcome = _clip(data.get("outcome"))
    operation = _clip(data.get("operation")).replace("_", " ").lower()
    sequence = data.get("sequence")
    label = f"Transition {sequence}" if isinstance(sequence, int) else "Transition"
    template = OUTCOME_SUMMARIES.get(outcome)
    if template is None or not operation:
        suffix = f" ({outcome})" if outcome else ""
        if template is not None:
            summary = template.format(op="an unknown operation")
        else:
            summary = f"{label}: unknown outcome{suffix}"
    else:
        summary = template.format(op=operation)
    return _event(data.get("committedAt"), source, "lifecycle_transition", summary, ref,
                  verified=False)


def read_deliberation(root: Path | str, sidecar: str, source: str | None = None) -> dict[str, Any]:
    """Events from one deliberation sidecar (``.proposal-deliberation`` or the experimental one)."""
    root = Path(root).expanduser().resolve()
    if source is None:
        source = next((k for k, v in SIDECARS.items() if v == sidecar), "proposal")
    base = root / sidecar
    if not base.is_symlink() and not base.exists():
        return _result("absent")
    try:
        resolved_base = base.resolve(strict=True)
        resolved_base.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return _result("unreadable", detail=f"{sidecar} is not a directory inside the workspace")
    if not resolved_base.is_dir():
        return _result("unreadable", detail=f"{sidecar} is not a directory inside the workspace")

    events: list[dict[str, Any]] = []
    candidates = unreadable = too_large = 0
    notes: list[str] = []
    cut = False
    for parts, build in ((RECEIPTS_REL, _receipt_event), (TRANSITIONS_REL, _transition_event)):
        directory = base.joinpath(*parts)
        label = "/".join((sidecar, *parts))
        if not directory.is_dir():
            continue
        names, listing_cut = _list_names(
            directory, lambda e: e.name.endswith(".json") and e.is_file())
        if listing_cut or len(names) > MAX_ITEM_FILES:
            cut = True
            notes.append(f"{label}: more than {MAX_ITEM_FILES} files, read the first {MAX_ITEM_FILES}")
        for name in names[:MAX_ITEM_FILES]:
            candidates += 1
            status, path, _size, _mtime = _locate(root, directory / name, ITEM_MAX_BYTES)
            if status == "too_large":
                too_large += 1
                continue
            data = _read_bytes(path, ITEM_MAX_BYTES) if status == "ok" and path else None
            try:
                value = json.loads(data.decode("utf-8")) if data is not None else None
            except ValueError:
                value = None
            if not isinstance(value, dict):
                unreadable += 1
                continue
            events.append(build(source, value, f"{label}/{name}"))
    if too_large:
        notes.append(f"{too_large} too large")
    if unreadable:
        notes.append(f"{unreadable} unreadable")
    detail = "; ".join(notes) or None
    if cut:
        return _result("too_large", events, detail)
    if candidates and not events:
        return _result("too_large" if too_large and not unreadable else "unreadable", events, detail)
    return _result("ok", events, detail)


# --------------------------------------------------------------------------
# remote-execution ledgers
# --------------------------------------------------------------------------
def _discover_ledgers(root: Path) -> tuple[list[Path], bool, bool]:
    """Fixed two-level discovery: ``implementations/*/*/.remote-execution/ledger.jsonl``.

    Returns ``(paths, cut, escaped)``. Never recursive; ``experiments/`` is not
    a ledger location (the engine builds ``target / name`` with ``target``
    under ``implementations/``).
    """
    top = root / "implementations"
    if not top.exists() and not top.is_symlink():
        return [], False, False
    try:
        top.resolve(strict=True).relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return [], False, True
    found: list[Path] = []
    repos, _ = _list_names(top, lambda e: e.is_dir())
    for repo in repos[:MAX_LAYOUT_NAMES]:
        names, _ = _list_names(top / repo, lambda e: e.is_dir())
        for name in names[:MAX_LAYOUT_NAMES]:
            candidate = top / repo / name / LEDGER_NAME[0] / LEDGER_NAME[1]
            if candidate.exists() or candidate.is_symlink():
                if len(found) >= MAX_LEDGER_FILES:
                    return found, True, False
                found.append(candidate)
    return found, False, False


def _ledger_event(data: dict[str, Any], ref: str) -> dict[str, Any] | None:
    kind = data.get("kind")
    if kind not in _LEDGER_KINDS:
        return None
    if kind == "submitted":
        summary = (f"Submitted {_clip(data.get('entrypoint')) or 'an entrypoint'} to "
                   f"{_clip(data.get('worker')) or 'a worker'}")
    elif kind == "returned":
        summary = f"Returned {_clip(data.get('submissionId')) or 'a submission'}"
    else:
        summary = f"Errored: {_clip(data.get('reason')) or 'no reason recorded'}"
    return _event(data.get("ts"), "remote-execution", kind, summary, ref)


def read_ledgers(root: Path | str) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    paths, cut, escaped = _discover_ledgers(root)
    if escaped:
        return _result("unreadable", detail="implementations/ is outside the workspace")
    if not paths:
        return _result("absent")
    events: list[dict[str, Any]] = []
    failed = too_large = malformed = skipped_lines = 0
    for path in paths:
        status, resolved, _size, _mtime = _locate(root, path, LEDGER_MAX_BYTES)
        if status == "too_large":
            too_large += 1
            continue
        data = _read_bytes(resolved, LEDGER_MAX_BYTES) if status == "ok" and resolved else None
        if data is None:
            failed += 1
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            failed += 1
            continue
        lines = data.decode("utf-8", errors="replace").splitlines()
        # the ledger is append-only: keep the NEWEST lines, drop the oldest
        dropped = max(0, len(lines) - MAX_LEDGER_LINES)
        skipped_lines += dropped
        file_events = bad = 0
        for number, line in enumerate(lines[dropped:], dropped + 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except ValueError:
                value = None
            event = _ledger_event(value, f"{rel}#{number}") if isinstance(value, dict) else None
            if event is None:
                bad += 1
                continue
            events.append(event)
            file_events += 1
        malformed += bad
        if bad and not file_events:
            failed += 1
    notes = []
    if cut:
        notes.append(f"more than {MAX_LEDGER_FILES} ledgers, scanned the first {MAX_LEDGER_FILES}")
    if skipped_lines:
        notes.append(f"{skipped_lines} oldest lines beyond the {MAX_LEDGER_LINES}-line cap ignored")
    if malformed:
        notes.append(f"{malformed} malformed lines skipped")
    if too_large:
        notes.append(f"{too_large} ledgers too large")
    if failed:
        notes.append(f"{failed} ledgers unreadable")
    detail = "; ".join(notes) or None
    if not events and (failed or too_large):
        return _result("too_large" if too_large and not failed else "unreadable", events, detail)
    return _result("ok", events, detail)


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------
def _parse_ts(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.timestamp()
    except (OverflowError, OSError, ValueError):
        return None


def merge(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dated events newest first, then ``ts: null`` events in input order.

    Ties break on source order (:data:`SOURCES`) and then input order, so the
    result is deterministic. An unparseable ``ts`` becomes ``null``.
    """
    rank = {name: index for index, name in enumerate(SOURCES)}
    keyed = []
    for index, event in enumerate(events):
        stamp = _parse_ts(event.get("ts"))
        item = dict(event)
        if stamp is None:
            item["ts"] = None
        keyed.append(((1, 0.0, rank.get(item.get("source"), len(rank)), index) if stamp is None
                      else (0, -stamp, rank.get(item.get("source"), len(rank)), index), item))
    keyed.sort(key=lambda pair: pair[0])
    return [item for _key, item in keyed]


def _read_source(root: Path, name: str) -> dict[str, Any]:
    try:
        if name == "declarations":
            return read_declarations(root)
        if name == "remote-execution":
            return read_ledgers(root)
        return read_deliberation(root, SIDECARS[name], name)
    except Exception as exc:  # noqa: BLE001 - one broken source never fails the response
        return _result("unreadable", detail=f"reader failed: {type(exc).__name__}")


def build_decisions(root: Path | str, sources: list[str] | None = None,
                    limit: int = MAX_TOTAL_EVENTS) -> dict[str, Any]:
    """The merged timeline. ``sources`` restricts which sources are even read."""
    root = Path(root).expanduser().resolve()
    chosen = list(SOURCES) if not sources else list(dict.fromkeys(sources))
    unknown = [name for name in chosen if name not in SOURCES]
    if unknown:
        raise DecisionsQueryError(
            f"unknown source {unknown[0]!r}; expected one of {', '.join(SOURCES)}")
    limit = max(1, min(MAX_TOTAL_EVENTS, int(limit)))
    summary: dict[str, dict[str, Any]] = {}
    pooled: list[dict[str, Any]] = []
    truncated = False
    for name in SOURCES:
        if name not in chosen:
            continue
        result = _read_source(root, name)
        ordered = merge(result["events"])
        capped = ordered[:MAX_SOURCE_EVENTS]
        cut = len(capped) < len(ordered)
        truncated = truncated or cut
        info: dict[str, Any] = {"status": result["status"], "count": len(capped), "truncated": cut}
        if result.get("detail"):
            info["detail"] = result["detail"]
        summary[name] = info
        pooled.extend(capped)
    merged = merge(pooled)
    if len(merged) > limit:
        truncated = True
    return {"events": merged[:limit], "truncated": truncated, "total": len(merged),
            "sources": summary,
            "note": ("Read-only view of persisted records. Deliberation events are unverified "
                     "and edit receipts carry no timestamp.")}
