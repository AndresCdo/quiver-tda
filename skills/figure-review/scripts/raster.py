"""raster: the fallback chain that turns an already-compiled figure PDF into
a PNG, and nothing else.

This is the ONLY module in `figure-review` permitted to import `subprocess`
(pinned by this skill's own subprocess-scan suite, mirroring
`paper-writing`'s `NoSubprocessScanTests`). It never reads or writes a
repair-budget ledger, and it never invokes `latexmk` or any other LaTeX
toolchain — the PDF it consumes already exists, produced by `render`.

Four tools are attempted, in this fixed order, using the first one that
resolves on `PATH`: `pdftoppm`, `pdftocairo`, `gs`, `sips`. A tool that
resolves but fails to produce a raster (a non-zero exit, a timeout, or an
exit 0 that wrote nothing) is a LINK failure and falls through to the next
link — it is not, by itself, a toolchain-absence refusal. Only when every
link has either not resolved on `PATH` or failed to produce a raster does
this module raise `Refused("RASTER_TOOLCHAIN_ABSENT", ...)`, naming every
probed tool's own status (absent, timed out, or its exit) and the exact
`PATH` searched.

`sips` has no resolution operand for a PDF page: `-s dpiWidth/dpiHeight`
write image metadata, they do not resample. So `sips`'s DPI is DERIVED,
never requested — first `sips -g pixelWidth -g pixelHeight <pdf>` reports
the page box in points, then the produced raster's own pixel width (read
from its PNG header, not decoded) yields
`effective_dpi = raster_px_width * 72 / page_pt_width`. Every other link's
DPI is the flag it was given. Both the value and its `dpiSource`
(`"flag"` or `"derived"`) are recorded, so a derived number is never
silently read as a requested one.

Per-link timeout, never one shared chain-wide budget: a slow link 1 must
never consume the time three later links needed, and a timeout on a
present-but-slow tool must never be reported as though that tool were
absent.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: The fixed fallback order, measured on this machine (proposal.md,
#: "The fallback chain, ordered by what was measured").
CHAIN: tuple[str, ...] = ("pdftoppm", "pdftocairo", "gs", "sips")

#: Per-link, never shared across the whole chain.
RASTER_TIMEOUT_S = 60

DEFAULT_DPI = 150

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOR_TYPE_NAMES = {0: "gray", 2: "rgb", 3: "palette", 4: "gray-alpha", 6: "rgba"}


class _LinkFailure(Exception):
    """One rasterizer link did not produce a raster. Caught internally —
    never escapes `rasterize`, which turns every link's outcome into a
    status string and either returns a success dict or raises the single
    `RASTER_TOOLCHAIN_ABSENT` refusal once every link has been tried."""


def resolve_link(path: str | None = None) -> str | None:
    """The name of the first `CHAIN` tool this machine's `PATH` resolves,
    or `None` if none does. Answers presence only — it spends no process,
    which is exactly what an emptied-`PATH` refusal needs to check cheaply
    (`figure-raster` spec, `Requirement: Toolchain Absence Refuses By
    Name`)."""
    for tool in CHAIN:
        if shutil.which(tool, path=path) is not None:
            return tool
    return None


def probe(path: str | None = None) -> dict:
    """`figure-raster` spec, `Requirement: Presence Is a Command the Front
    Door Answers`: report the resolved link, or refuse naming all four and
    the exact searched `PATH`."""
    search_path = path if path is not None else os.environ.get("PATH", "")
    resolved = resolve_link(path=path)
    if resolved is None:
        raise Refused(
            "RASTER_TOOLCHAIN_ABSENT",
            f"none of {', '.join(CHAIN)} resolves on PATH={search_path!r}",
        )
    return {"resolved": resolved, "path": search_path}


def _read_png_header(png_path: Path) -> dict:
    """The width, height and colour-type name from a PNG's own `IHDR`
    chunk, read directly from bytes — never inflated, never decoded. A
    peek at the header a produced raster already carries, not the
    grayscale decode `png_read.py` performs; that module classifies every
    pixel and belongs to a later commit that also computes geometry from
    it."""
    try:
        data = png_path.read_bytes()
    except OSError:
        return {"width": None, "height": None, "colorModel": None}
    if data[:8] != _PNG_SIGNATURE or len(data) < 26:
        return {"width": None, "height": None, "colorModel": None}
    chunk_type = data[12:16]
    if chunk_type != b"IHDR":
        return {"width": None, "height": None, "colorModel": None}
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    color_type = data[25]
    return {
        "width": width,
        "height": height,
        "colorModel": _COLOR_TYPE_NAMES.get(color_type),
    }


_SIPS_DIM_RE = re.compile(r"pixel(Width|Height):\s*([0-9]+(?:\.[0-9]+)?)")


def _sips_page_points(abs_sips: str, pdf: Path, timeout: float) -> tuple[float, float]:
    """`sips -g pixelWidth -g pixelHeight <pdf>` reports the PDF's own page
    box in points — the number this skill needs to derive an effective DPI
    once the raster's own pixel width is known (design.md, Decision 2:
    "What `sips` actually is")."""
    try:
        completed = subprocess.run(
            [abs_sips, "-g", "pixelWidth", "-g", "pixelHeight", str(pdf)],
            capture_output=True, text=True, timeout=timeout, shell=False,
        )
    except subprocess.TimeoutExpired:
        raise _LinkFailure(f"timed out after {timeout}s") from None
    if completed.returncode != 0:
        raise _LinkFailure(f"exit {completed.returncode}")
    found: dict[str, float] = {}
    for match in _SIPS_DIM_RE.finditer(completed.stdout):
        found[match.group(1)] = float(match.group(2))
    if "Width" not in found or "Height" not in found:
        raise _LinkFailure("did not report a page box in points")
    return found["Width"], found["Height"]


def _effective_dpi(raster_px_width: int | None, page_pt_width: float | None) -> float | None:
    if not raster_px_width or not page_pt_width:
        return None
    return round(raster_px_width * 72 / page_pt_width, 2)


def _argv_for(tool: str, abs_tool: str, pdf: Path, tmp_dir: Path, dpi: int) -> tuple[list[str], Path]:
    """The per-link invocation (design.md, Decision 2's argv table). Always
    a list, never a composed string; `pdf` arrives already resolved to an
    absolute path by `rasterize`, so no operand can be read as a flag."""
    if tool in ("pdftoppm", "pdftocairo"):
        prefix = tmp_dir / pdf.stem
        return (
            [abs_tool, "-png", "-gray", "-r", str(dpi), "-f", "1", "-l", "1",
             str(pdf), str(prefix)],
            prefix,
        )
    if tool == "gs":
        out_png = tmp_dir / f"{pdf.stem}.png"
        return (
            [abs_tool, "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
             "-dFirstPage=1", "-dLastPage=1", "-sDEVICE=pnggray",
             f"-r{dpi}", f"-sOutputFile={out_png}", str(pdf)],
            out_png,
        )
    if tool == "sips":
        out_png = tmp_dir / f"{pdf.stem}.png"
        return [abs_tool, "-s", "format", "png", "--out", str(out_png), str(pdf)], out_png
    raise ValueError(f"unknown rasterizer link: {tool!r}")


def _locate_output(tool: str, expected: Path, tmp_dir: Path) -> Path | None:
    if tool in ("pdftoppm", "pdftocairo"):
        # poppler appends a page-number suffix whose exact shape varies by
        # version when -f/-l is given; discover it rather than guess it.
        candidates = sorted(tmp_dir.glob(expected.name + "*.png"))
        return candidates[0] if candidates else None
    return expected if expected.is_file() else None


def _attempt_link(tool: str, abs_tool: str, pdf: Path, tmp_dir: Path,
                   dpi: int, timeout: float) -> dict:
    """Try exactly one link. Returns `{"status": "ok", ...}` on success, or
    `{"status": <failure text>}` — never raises; `rasterize` decides what a
    fully-exhausted chain means."""
    page_points: tuple[float, float] | None = None
    if tool == "sips":
        try:
            page_points = _sips_page_points(abs_tool, pdf, timeout)
        except _LinkFailure as exc:
            return {"status": str(exc)}

    argv, expected = _argv_for(tool, abs_tool, pdf, tmp_dir, dpi)
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": f"timed out after {timeout}s"}
    if completed.returncode != 0:
        return {"status": f"exit {completed.returncode}"}

    png_path = _locate_output(tool, expected, tmp_dir)
    if png_path is None:
        return {"status": "wrote no output"}

    header = _read_png_header(png_path)
    if tool == "sips":
        dpi_source = "derived"
        effective_dpi = _effective_dpi(header["width"], page_points[0] if page_points else None)
    else:
        dpi_source = "flag"
        effective_dpi = dpi
    return {
        "status": "ok",
        "argv": argv,
        "png": png_path,
        "dpi": effective_dpi,
        "dpiSource": dpi_source,
        "colorModel": header["colorModel"],
        "pixelWidth": header["width"],
        "pixelHeight": header["height"],
    }


def rasterize(pdf: Path, out_dir: Path, *, dpi: int = DEFAULT_DPI,
              path: str | None = None, timeout: float = RASTER_TIMEOUT_S) -> dict:
    """Rasterize `pdf` into `out_dir`, trying `CHAIN` in order and falling
    through on any link failure. Writes `<id>.png` and
    `raster-provenance.json` into `out_dir` via a per-call temporary
    directory plus an atomic `os.replace` (Threat Matrix, "Scratch write
    collision"). Raises `Refused("RASTER_TOOLCHAIN_ABSENT", ...)` naming
    every probed tool's own status and the searched `PATH` when no link
    produces a raster.

    Never reads or writes a repair-budget ledger, on any path, including
    every-link failure — there is no ledger call anywhere in this module.
    """
    pdf = Path(pdf).resolve()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    search_path = path if path is not None else os.environ.get("PATH", "")

    statuses: dict[str, str] = {}
    tmp_dir = Path(tempfile.mkdtemp(dir=str(out_dir)))
    try:
        for tool in CHAIN:
            abs_tool = shutil.which(tool, path=path)
            if abs_tool is None:
                statuses[tool] = "absent"
                continue
            outcome = _attempt_link(tool, abs_tool, pdf, tmp_dir, dpi, timeout)
            if outcome["status"] != "ok":
                statuses[tool] = outcome["status"]
                continue

            final_png = out_dir / f"{pdf.stem}.png"
            final_provenance = out_dir / "raster-provenance.json"
            provenance = {
                "tool": tool,
                "argv": outcome["argv"],
                "dpi": outcome["dpi"],
                "dpiSource": outcome["dpiSource"],
                "colorModel": outcome["colorModel"],
                "pixelWidth": outcome["pixelWidth"],
                "pixelHeight": outcome["pixelHeight"],
            }
            os.replace(str(outcome["png"]), str(final_png))
            _atomic_write_json(final_provenance, provenance)
            return {"png": str(final_png), "provenance": str(final_provenance), **provenance}

        detail = "; ".join(f"{tool}: {statuses.get(tool, 'absent')}" for tool in CHAIN)
        raise Refused(
            "RASTER_TOOLCHAIN_ABSENT",
            f"no rasterizer link produced a raster ({detail}); PATH={search_path!r}",
        )
    finally:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)


def _atomic_write_json(path: Path, payload: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
