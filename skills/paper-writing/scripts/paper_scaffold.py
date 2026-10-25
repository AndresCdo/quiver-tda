"""paper_scaffold: creates and re-enters `paper/` without clobbering.

Mirrors how this repository already treats `proposals/` and `experiments/`:
the folder travels (`paper/.gitkeep` is tracked), its contents stay home
(`paper/*` is gitignored). A second run leaves every existing byte
untouched, regardless of what those bytes are — hand edits included.

Standard library only. All writes are of empty files; nothing here opens
`main.tex` for content, so binary-vs-text mode does not apply to this
module (that discipline belongs to `paper_block.py`, which does read and
rewrite `main.tex` content).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: Five path components up from this file to the repository root:
#: `<root>/skills/paper-writing/scripts/paper_scaffold.py`. Same
#: convention `_core/implementation/impl_layout.py` uses for its own
#: `FORGE_ROOT`, at the same directory depth from root — measured, not
#: assumed; a test pins the value this returns.
FORGE_ROOT = Path(__file__).resolve().parents[3]

#: The block-region-bounded content this scaffold ships empty. `open` (a
#: sibling capability, not this module) is what ever writes bytes into
#: `main.tex`'s block regions; scaffold's `main.tex` starts with none.
_SCAFFOLD_ENTRIES: tuple[tuple[str, str], ...] = (
    ("main.tex", "file"),
    ("refs.bib", "file"),
    ("Figures", "dir"),
    (".gitkeep", "file"),
)


def resolve_paper_dir(paper_arg: str | None, *, forge_root: Path = FORGE_ROOT) -> Path:
    """Resolve `--paper <dir>` (or the default `<forge_root>/paper`).

    Refuses `PAPER_OUTSIDE_REPOSITORY` (invocation-defect) when the resolved
    path does not sit under `forge_root`. `forge_root` is injectable so a
    test can exercise this boundary against a throwaway root instead of the
    real repository.
    """
    root = forge_root.resolve()
    target = Path(paper_arg).resolve() if paper_arg else (root / "paper")
    try:
        target.relative_to(root)
    except ValueError:
        raise Refused(
            "PAPER_OUTSIDE_REPOSITORY",
            f"{target} does not resolve inside the repository root {root}",
        )
    return target


def scaffold(paper_dir: Path) -> dict:
    """Create `paper_dir`'s tree if absent; never overwrite what exists.

    Refuses `PAPER_NOT_A_DIRECTORY` when `paper_dir` exists as a
    non-directory, and `SCAFFOLD_ENTRY_WRONG_TYPE` when one of the four
    entries exists as the wrong type (a file where a directory is expected,
    or the reverse). Both refusals are raised before any entry is written,
    so a wrong-typed entry never leaves a partial scaffold behind it.
    """
    if paper_dir.exists() and not paper_dir.is_dir():
        raise Refused(
            "PAPER_NOT_A_DIRECTORY", f"{paper_dir} exists and is not a directory"
        )

    # Check pass first: every existing entry's type is validated before any
    # entry is written, so `Figures` being a file refuses before `main.tex`
    # or `.gitkeep` ever get created underneath it.
    for name, kind in _SCAFFOLD_ENTRIES:
        entry = paper_dir / name
        if not entry.exists():
            continue
        is_dir = entry.is_dir()
        if kind == "dir" and not is_dir:
            raise Refused(
                "SCAFFOLD_ENTRY_WRONG_TYPE",
                f"{name} exists as a file, expected a directory",
            )
        if kind == "file" and is_dir:
            raise Refused(
                "SCAFFOLD_ENTRY_WRONG_TYPE",
                f"{name} exists as a directory, expected a file",
            )

    paper_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    for name, kind in _SCAFFOLD_ENTRIES:
        entry = paper_dir / name
        if entry.exists():
            continue
        if kind == "dir":
            entry.mkdir()
        else:
            entry.write_bytes(b"")
        created.append(name)

    return {"paper": str(paper_dir), "created": created}
