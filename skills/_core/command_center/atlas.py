"""Read-only SOTA atlas reader for the command center.

The atlas is written by ``skills/plausibility`` (``sota-pool/atlas.json`` and the
self-contained ``sota-pool/atlas.html``). The dashboard only reads: it never
writes, regenerates or repairs either file.

* :func:`build_atlas` returns the state of both files, their staleness, the
  checker's verdict and a small summary of the JSON.
* :func:`read_html` returns the HTML bytes for the sandboxed view route.

Every read resolves the path, requires it to stay inside the workspace and to be
a regular file, and checks the size BEFORE reading any byte.

SECURITY: validation executes workspace Python inside the server process. The
checker is loaded by file path from exactly one fixed location,
``<workspace>/skills/plausibility/scripts/check_atlas.py``, after the same
containment and regular-file checks as every other read. The path is never
derived from request input. A workspace is trusted code (it also ships the
wiring-smoke script the dashboard can run), but this is still a code-execution
surface: do not point the dashboard at a workspace you do not trust.
"""

from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path
from typing import Any

from . import state_extractor as _ex

JSON_MAX_BYTES = 2 * 1024 * 1024
HTML_MAX_BYTES = 2 * 1024 * 1024
MAX_ERRORS = 50
MAX_EVIDENCE = 100
MAX_SYSTEMS = 100
MAX_FAMILIES = 20
MAX_RELS = 50
TEXT_MAX = 300

CHECKER_REL = ("skills", "plausibility", "scripts", "check_atlas.py")


def _mtime_token(mtime: float) -> int:
    """Integer milliseconds since the epoch: a cache-busting token for the UI."""
    return int(mtime * 1000)


def _clip(value: Any) -> str:
    return value[:TEXT_MAX] if isinstance(value, str) else ""


# --------------------------------------------------------------------------
# bounded, containment-checked reads
# --------------------------------------------------------------------------
def _locate(root: Path, path: Path, cap: int) -> tuple[str, Path | None, int | None, float | None]:
    """Resolve ``path`` under ``root`` and vet it without reading it.

    Returns ``(status, resolved, size, mtime)``; status is ``ok``, ``absent``,
    ``too_large``, ``unsafe`` (outside ``root``) or ``unreadable`` (not a
    regular file, or an OS error). ``resolved`` is set for ``ok``/``too_large``.
    """
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return "absent", None, None, None
    except (OSError, RuntimeError):
        return "unreadable", None, None, None
    try:
        resolved.relative_to(root)
    except ValueError:
        return "unsafe", None, None, None
    try:
        info = resolved.stat()
    except OSError:
        return "unreadable", None, None, None
    if not stat.S_ISREG(info.st_mode):
        return "unreadable", None, None, None
    if info.st_size > cap:
        return "too_large", resolved, info.st_size, info.st_mtime
    return "ok", resolved, info.st_size, info.st_mtime


def _read_bytes(resolved: Path, cap: int) -> bytes | None:
    """Read at most ``cap`` bytes; ``None`` when the file grew past it."""
    try:
        with open(resolved, "rb") as handle:
            data = handle.read(cap + 1)
    except OSError:
        return None
    return None if len(data) > cap else data


def read_html(root: Path | str) -> tuple[str, bytes | None]:
    """The atlas HTML for the view route: ``(status, bytes)``.

    ``status`` is ``ok``, ``absent`` (also unsafe or not a regular file, so the
    route answers 404) or ``too_large``.
    """
    root = Path(root).expanduser().resolve()
    status, resolved, _size, _mtime = _locate(root, root / "sota-pool" / "atlas.html", HTML_MAX_BYTES)
    if status == "too_large":
        return "too_large", None
    if status != "ok" or resolved is None:
        return "absent", None
    data = _read_bytes(resolved, HTML_MAX_BYTES)
    if data is None:
        return "too_large", None
    return "ok", data


# --------------------------------------------------------------------------
# validation through the workspace's own checker
# --------------------------------------------------------------------------
def _unavailable(detail: str) -> dict[str, Any]:
    return {"status": "unavailable", "errors": [], "error_count": 0, "detail": detail}


def _load_checker(root: Path) -> Any:
    """Load the workspace checker module from its one fixed path, or raise."""
    status, resolved, _size, _mtime = _locate(root, root.joinpath(*CHECKER_REL), 1024 * 1024)
    if status != "ok" or resolved is None:
        raise FileNotFoundError(f"checker {status}")
    spec = importlib.util.spec_from_file_location("_papersmith_command_center_check_atlas", resolved)
    if spec is None or spec.loader is None:
        raise ImportError("no loader for the checker")
    module = importlib.util.module_from_spec(spec)
    with _ex._no_bytecode():  # the workspace must not gain a __pycache__
        spec.loader.exec_module(module)
    return module


def validate(root: Path, data: Any) -> dict[str, Any]:
    """Run the workspace's ``_failures`` on already-parsed atlas data."""
    try:
        module = _load_checker(root)
        failures = getattr(module, "_failures", None)
        if not callable(failures):
            return _unavailable("check_atlas.py has no _failures validator")
        found = failures(data)
        if not isinstance(found, list) or not all(isinstance(item, str) for item in found):
            return _unavailable("check_atlas.py returned an unexpected result")
    except FileNotFoundError:
        return _unavailable("skills/plausibility/scripts/check_atlas.py is not available "
                            "in this workspace")
    except BaseException as exc:  # noqa: BLE001 - workspace code (even SystemExit) never breaks the route
        if isinstance(exc, KeyboardInterrupt):
            raise
        return _unavailable(f"check_atlas.py could not run: {type(exc).__name__}")
    errors = [_clip(item) for item in found[:MAX_ERRORS]]
    return {"status": "failed" if found else "ok", "errors": errors,
            "error_count": len(found)}


# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------
def summarize(data: Any) -> dict[str, Any] | None:
    """A defensive summary; ``None`` when the data has no systems list."""
    if not isinstance(data, dict) or not isinstance(data.get("systems"), list):
        return None
    systems: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    evidence_total = 0
    for system in data["systems"]:
        if not isinstance(system, dict):
            continue
        raw_planets = system.get("planets")
        planets = [p for p in raw_planets if isinstance(p, dict)] if isinstance(raw_planets, list) else []
        families: list[str] = []
        sid = _clip(system.get("id"))
        for planet in planets:
            if planet.get("slot") == "family" and isinstance(planet.get("label"), str):
                label = _clip(planet["label"]).strip()
                if label and label not in families and len(families) < MAX_FAMILIES:
                    families.append(label)
            ev = planet.get("evidence")
            if isinstance(ev, dict):
                evidence_total += 1
                if len(evidence) < MAX_EVIDENCE:
                    evidence.append({"system": sid, "planet": _clip(planet.get("id")),
                                     "origin": _clip(ev.get("origin")),
                                     "retrieved": _clip(ev.get("retrieved"))})
        if len(systems) < MAX_SYSTEMS:
            systems.append({"id": sid, "title": _clip(system.get("title")),
                            "planets": len(planets), "families": families})
    links = data.get("links") if isinstance(data.get("links"), list) else []
    rels: dict[str, int] = {}
    for link in links:
        rel = link.get("rel") if isinstance(link, dict) else None
        if isinstance(rel, str):
            key = _clip(rel)
            if key in rels or len(rels) < MAX_RELS:
                rels[key] = rels.get(key, 0) + 1
    return {"systems": systems, "links": len(links), "rels": rels,
            "evidence": evidence, "evidence_total": evidence_total}


# --------------------------------------------------------------------------
# payload
# --------------------------------------------------------------------------
def build_atlas(root: Path | str) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    pool = root / "sota-pool"
    j_status, j_path, j_size, j_mtime = _locate(root, pool / "atlas.json", JSON_MAX_BYTES)
    h_status, _h_path, h_size, h_mtime = _locate(root, pool / "atlas.html", HTML_MAX_BYTES)
    if h_status == "unreadable":  # the HTML status set has no "unreadable"
        h_status = "unsafe"

    json_info: dict[str, Any] = {"status": j_status}
    summary = None
    validation = _unavailable("atlas.json is not available to validate")
    if j_status == "ok" and j_path is not None:
        raw = _read_bytes(j_path, JSON_MAX_BYTES)
        if raw is None:
            j_status, j_size = "too_large", None
        else:
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (ValueError, RecursionError) as exc:  # includes UnicodeDecodeError
                j_status = "invalid"
                validation = {"status": "failed", "errors": [_clip(f"ATLAS_NOT_JSON: {exc}")],
                              "error_count": 1}
            else:
                try:
                    summary = summarize(parsed)
                except Exception:  # noqa: BLE001 - odd content never breaks the payload
                    summary = None
                validation = validate(root, parsed)
        json_info["status"] = j_status
    if j_size is not None and j_status in ("ok", "invalid", "too_large"):
        json_info["size"] = j_size
    if j_mtime is not None and j_status in ("ok", "invalid"):
        json_info["mtime"] = _mtime_token(j_mtime)
    html_info: dict[str, Any] = {"status": h_status}
    if h_size is not None and h_status in ("ok", "too_large"):
        html_info["size"] = h_size
    if h_mtime is not None and h_status == "ok":
        html_info["mtime"] = _mtime_token(h_mtime)

    stale = None
    if j_mtime is not None and h_mtime is not None:
        stale = j_mtime > h_mtime
    return {"json": json_info, "html": html_info, "stale": stale,
            "validation": validation, "summary": summary}
