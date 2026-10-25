"""In-memory history of what changed while the dashboard runs.

``diff_states`` and ``diff_health`` turn two snapshots into a list of
``Change`` records; ``HistoryStore`` keeps the newest entries in a bounded,
thread-safe ring and serves them through a cursor (``page``). Nothing here
touches the disk: history lives for one server process (``boot_id``).
"""

from __future__ import annotations

import collections
import copy
import math
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

#: Entries retained per process; older ones are evicted (reported as ``gap``).
DEFAULT_CAPACITY = 1000
DEFAULT_LIMIT = 200
MAX_LIMIT = 500

#: Diagram element kinds; an ``element_id`` is ``"<kind>:<raw id>"`` exactly as
#: the pipeline diagram builds its node ids.
ELEMENT_KINDS = ("stage", "gate", "section")
MAX_ELEMENT_REMAINDER = 200

#: Entry kinds a client may filter by.
KINDS = (
    "section_status", "section_blocks", "section_words",
    "gate", "stage", "health", "smoke",
)


class HistoryQueryError(ValueError):
    """An invalid ``element`` or ``kind`` filter (HTTP 422)."""


@dataclass(frozen=True)
class Change:
    """One observed difference, before it is given an id and a timestamp."""

    kind: str
    element_id: str | None
    summary: str
    before: Any
    after: Any


@dataclass(frozen=True)
class Entry:
    """One immutable history record."""

    id: str
    boot_id: str
    seq: int
    ts: float
    kind: str
    element_id: str | None
    summary: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "boot_id": self.boot_id, "seq": self.seq, "ts": self.ts,
            "kind": self.kind, "element_id": self.element_id, "summary": self.summary,
            "before": copy.deepcopy(self.before), "after": copy.deepcopy(self.after),
        }


# --------------------------------------------------------------------------
# diffs
# --------------------------------------------------------------------------
def _by_id(items: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            result[item["id"]] = item
    return result


def _percent(value: Any, digits: int = 0) -> str:
    """``value`` (a 0..1 fraction) as a percentage with at most ``digits`` decimals.

    Whole-number precision keeps ``"<1%"`` for a positive value below one percent
    instead of a misleading ``"0%"``; extra decimals drop trailing zeros.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "n/a"
    pct = value * 100
    if digits == 0:
        return "<1%" if 0 < pct < 1 else f"{round(pct)}%"
    return f"{pct:.{digits}f}".rstrip("0").rstrip(".") + "%"


def _percent_change(before: Any, after: Any) -> str:
    """``"<before> -> <after>"`` with just enough precision to tell them apart."""
    for digits in (0, 1, 2, 3):
        old, new = _percent(before, digits), _percent(after, digits)
        if old != new:
            break
    return f"{old} -> {new}"


def _stage_summary(stage_id: str, before: dict | None, after: dict | None) -> str:
    if before is None:
        return f"Stage {stage_id} appeared"
    if after is None:
        return f"Stage {stage_id} was removed"
    parts: list[str] = []
    if before.get("active") != after.get("active"):
        parts.append("became active" if after.get("active") else "became inactive")
    if before.get("progress") != after.get("progress"):
        parts.append(f"progress {_percent_change(before.get('progress'), after.get('progress'))}")
    if len(parts) == 1 and parts[0].startswith("progress"):
        return f"Stage {stage_id}: {parts[0]}"
    return f"Stage {stage_id} " + "; ".join(parts)


def diff_states(prev: dict[str, Any], curr: dict[str, Any]) -> list[Change]:
    """Meaningful differences between two workspace states.

    Compares section status, blocks written and word count, gate state and
    reasons, and stage active/progress. ``generated_at`` and every other field
    are ignored on purpose. A section, gate or stage that appears or vanishes
    is reported as a status/state change from or to ``None``.
    """
    changes: list[Change] = []

    old_sections, new_sections = _by_id(prev.get("sections")), _by_id(curr.get("sections"))
    for sid in list(old_sections) + [s for s in new_sections if s not in old_sections]:
        old, new = old_sections.get(sid), new_sections.get(sid)
        element = f"section:{sid}"
        if old is None or new is None:
            before = old.get("status") if old else None
            after = new.get("status") if new else None
            verb = "appeared" if old is None else "was removed"
            changes.append(Change("section_status", element, f"Section {sid} {verb}", before, after))
            continue
        for key, kind, label in (("status", "section_status", "status"),
                                 ("blocks_written", "section_blocks", "blocks written"),
                                 ("word_count", "section_words", "word count")):
            if old.get(key) != new.get(key):
                changes.append(Change(
                    kind, element,
                    f"Section {sid} {label}: {old.get(key)} -> {new.get(key)}",
                    old.get(key), new.get(key)))

    old_gates, new_gates = _by_id(prev.get("gates")), _by_id(curr.get("gates"))
    for gid in list(old_gates) + [g for g in new_gates if g not in old_gates]:
        old, new = old_gates.get(gid), new_gates.get(gid)
        before = None if old is None else {"state": old.get("state"), "reasons": list(old.get("reasons") or [])}
        after = None if new is None else {"state": new.get("state"), "reasons": list(new.get("reasons") or [])}
        if before != after:
            changes.append(Change(
                "gate", f"gate:{gid}",
                f"Gate {gid}: {(before or {}).get('state')} -> {(after or {}).get('state')}",
                before, after))

    old_stages, new_stages = _by_id(prev.get("pipeline_stages")), _by_id(curr.get("pipeline_stages"))
    for stage_id in list(old_stages) + [s for s in new_stages if s not in old_stages]:
        old, new = old_stages.get(stage_id), new_stages.get(stage_id)
        before = None if old is None else {"active": old.get("active"), "progress": old.get("progress")}
        after = None if new is None else {"active": new.get("active"), "progress": new.get("progress")}
        if before != after:
            changes.append(Change(
                "stage", f"stage:{stage_id}", _stage_summary(stage_id, before, after),
                before, after))
    return changes


def diff_health(prev: dict[str, Any], curr: dict[str, Any]) -> list[Change]:
    """Differences in overall and per-harness status only."""
    changes: list[Change] = []
    old = (prev.get("summary") or {}).get("state")
    new = (curr.get("summary") or {}).get("state")
    if old != new:
        changes.append(Change("health", None, f"Wiring health: {old} -> {new}", old, new))

    def harnesses(health: dict[str, Any]) -> dict[str, Any]:
        rows = (health.get("harness_sync") or {}).get("harnesses") or []
        return {row["tool"]: row.get("state") for row in rows
                if isinstance(row, dict) and isinstance(row.get("tool"), str)}

    old_h, new_h = harnesses(prev), harnesses(curr)
    for tool in list(old_h) + [t for t in new_h if t not in old_h]:
        if old_h.get(tool) != new_h.get(tool):
            changes.append(Change(
                "health", None, f"Harness {tool}: {old_h.get(tool)} -> {new_h.get(tool)}",
                old_h.get(tool), new_h.get(tool)))
    return changes


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------
def validate_element(element: str) -> None:
    kind, sep, rest = element.partition(":")
    if (not sep or kind not in ELEMENT_KINDS or not 1 <= len(rest) <= MAX_ELEMENT_REMAINDER
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in element)):
        raise HistoryQueryError(
            "element must be '<stage|gate|section>:<id>' with an id of 1 to "
            f"{MAX_ELEMENT_REMAINDER} characters and no control characters")


class HistoryStore:
    """Thread-safe ring of immutable entries, scoped to one process."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self.boot_id = uuid.uuid4().hex
        self._entries: collections.deque[Entry] = collections.deque(maxlen=capacity)
        self._seq = 0
        self._lock = threading.Lock()

    def add(self, kind: str, element_id: str | None, summary: str,
            before: Any, after: Any, *, ts: float | None = None) -> Entry:
        with self._lock:
            self._seq += 1
            entry = Entry(
                id=f"{self.boot_id}-{self._seq}", boot_id=self.boot_id, seq=self._seq,
                ts=time.time() if ts is None else ts, kind=kind, element_id=element_id,
                summary=summary, before=copy.deepcopy(before), after=copy.deepcopy(after))
            self._entries.append(entry)
            return entry

    def page(self, boot_id: str | None = None, after_seq: int = 0,
             element: str | None = None, kind: str | None = None,
             limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """One page of entries, oldest first.

        ``reset`` is true when ``boot_id`` names another process: the cursor is
        meaningless, so the page restarts from the first retained entry and the
        client must discard what it holds. ``gap`` is true when entries after
        ``after_seq`` were evicted. ``has_more`` is true when more matching
        entries follow this page.
        """
        if element is not None:
            validate_element(element)
        if kind is not None and kind not in KINDS:
            raise HistoryQueryError(f"kind must be one of: {', '.join(KINDS)}")
        limit = max(1, min(MAX_LIMIT, int(limit)))
        reset = boot_id is not None and boot_id != self.boot_id
        cursor = 0 if reset else max(0, int(after_seq))
        with self._lock:
            retained = list(self._entries)
        gap = bool(retained) and retained[0].seq > cursor + 1
        matches = [e for e in retained
                   if e.seq > cursor
                   and (element is None or e.element_id == element)
                   and (kind is None or e.kind == kind)]
        return {
            "boot_id": self.boot_id,
            "entries": [e.to_dict() for e in matches[:limit]],
            "has_more": len(matches) > limit,
            "reset": reset,
            "gap": gap,
        }
