from __future__ import annotations

import fnmatch, subprocess
from pathlib import Path
from impl_layout import IGNORED_DIRS, LFS_POINTER_PREFIX, TEXT_EXT
from impl_refusals import Refused


def git(target: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=target, capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise Refused("GIT_FAILED", f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def tracked_files(target: Path) -> list[str]:
    out = git(target, "ls-files", "-z")
    return [p for p in out.split("\0") if p]


def present_files(target: Path) -> list[str]:
    """What the repository actually holds, minus what it deliberately ignores.

    The index is the wrong enumerator for an inspection. A file that exists, is not
    ignored and is doing real work stays invisible until somebody commits it — so a
    misplaced module is reported after it has entered the history rather than before,
    which is the opposite of useful.

    Two questions were being answered by one list, and they are different: *does this
    exist* is answered by the disk, and *is this part of the record* is answered by
    the ignore rules. Both are local; nothing here reaches a remote.
    """
    candidates = [
        path for path in sorted(target.rglob("*"))
        if path.is_file() and not any(part in IGNORED_DIRS or part == ".git"
                                      for part in path.relative_to(target).parts)
    ]
    if not candidates:
        return []
    relative = [str(path.relative_to(target)) for path in candidates]
    # One call rather than one per file; `check-ignore` reads the same rules git
    # itself does, including any nested .gitignore.
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"], cwd=target,
        input="\0".join(relative), capture_output=True, text=True,
    )
    ignored = {p for p in proc.stdout.split("\0") if p}
    return [p for p in relative if p not in ignored]


def repository_ignored(target: Path, paths: list[str]) -> set[str]:
    """Which of `paths` this repository declares it does not ship.

    `paths` are repository-relative, POSIX-spelled, and asked in ONE batch.
    Returns the subset git names, verbatim as supplied.

    Never raises, never refuses, and deliberately does not route through
    `git()` above: that helper raises `GIT_FAILED` on any non-zero exit, and
    `check-ignore` exits 1 when nothing matched and 128 outside a work tree.
    Both mean the same thing to a caller asking which paths to drop, so the
    return code is not read at all -- a non-zero exit carries no output and
    the parse below yields the empty set on its own. An empty `paths` spawns
    nothing.

    `--no-index` is deliberately NOT passed. Empirically confirmed (scratch
    repository, a tracked file plus a rule that would match it if it were
    untracked): the default consults the index and reports exit 1 (not
    ignored) for the tracked path, while `--no-index` on the identical path
    reports exit 0 (ignored). The default is therefore exactly the intended
    semantics -- a tracked path is already in the history, so it is not a
    product the history never took.
    """
    if not paths:
        return set()
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"], cwd=target,
            input="\0".join(paths), capture_output=True, text=True,
            check=False,
        )
    except OSError:
        return set()
    return {p for p in proc.stdout.split("\0") if p}


def text_files(target: Path, paths: list[str]) -> list[str]:
    return [p for p in paths if Path(p).suffix.lower() in TEXT_EXT]


def read_text(target: Path, rel: str) -> str | None:
    try:
        return (target / rel).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def lfs_state(target: Path) -> dict:
    """Which files are placeholders, and what fetching them would cost.

    Cloning with the smudge filter skipped is already the rule — pointers are enough
    to reorganize a repository, and materializing gigabytes to move them around burns
    a quota that does not come back. What was missing is saying so. A four-kilobyte
    text file sitting where a model checkpoint is expected fails at load time with an
    error about the file format, and the reason is nowhere near the symptom.

    Nothing here fetches anything. The quota is the user's, spending it is their
    decision, and the command that would do it is reported rather than run.
    """
    attributes = target / ".gitattributes"
    if not attributes.exists():
        return {"status": "none", "patterns": []}

    patterns = [line.split()[0] for line in attributes.read_text(
        encoding="utf-8", errors="replace").splitlines()
        if "filter=lfs" in line and line.split()]
    if not patterns:
        return {"status": "none", "patterns": []}

    pointers, materialized = [], []
    for path in target.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = str(path.relative_to(target))
        if not any(fnmatch.fnmatch(relative, p) or fnmatch.fnmatch(path.name, p)
                   for p in patterns):
            continue
        try:
            head = path.open("rb").read(256)
        except OSError:
            continue
        if head.startswith(LFS_POINTER_PREFIX):
            # The pointer states the real file's size. Reading it is what turns
            # "some files are missing" into a number the user can weigh.
            declared = 0
            for line in head.decode("utf-8", "replace").splitlines():
                if line.startswith("size "):
                    declared = int(line.split()[1]) if line.split()[1].isdigit() else 0
            pointers.append({"path": relative, "bytes": declared})
        else:
            # Named, not merely counted. The contract promises to report
            # "which large files are real content and which are unfetched
            # pointers"; a count answers the second half and tallies the
            # first, so a reader needing one specific checkpoint could not
            # tell whether it had arrived. The size here is what is ON DISK,
            # a different measurement from a pointer's declared size, which
            # is a claim printed inside the placeholder -- which is why
            # `bytesToFetch` below stays about pointers alone.
            try:
                on_disk = path.stat().st_size
            except OSError:
                on_disk = 0
            materialized.append({"path": relative, "bytes": on_disk})

    total = sum(p["bytes"] for p in pointers)
    return {
        "status": "pointers" if pointers else "materialized",
        "patterns": patterns,
        "pointerCount": len(pointers),
        "materializedCount": len(materialized),
        "materialized": sorted(materialized, key=lambda entry: -entry["bytes"])[:20],
        "materializedTruncated": max(0, len(materialized) - 20),
        "bytesToFetch": total,
        "humanBytesToFetch": f"{total / 1024**3:.2f} GiB" if total else "0",
        "pointers": sorted(pointers, key=lambda p: -p["bytes"])[:20],
        "truncated": max(0, len(pointers) - 20),
        # Reported, never run.
        "fetchCommand": "git lfs pull --include=" + ",".join(f'"{p}"' for p in patterns),
        "note": ("These files are placeholders of a few hundred bytes. Anything that "
                 "opens one as data fails with an error about its format rather than "
                 "about its absence, so treat them as missing material: the flow reads "
                 "none of them."),
        # The tempting workaround does not exist, and believing it does is worse than
        # knowing the cost. GitHub counts every download against the repository
        # owner's bandwidth — the command below, the browser's download button, even a
        # source archive that happens to contain LFS objects. The free allowance is
        # 1 GiB a month. There is no route that avoids it.
        "quota": ("Every download counts against the repository owner's LFS bandwidth, "
                  "by any route: the command below, the web interface's download "
                  "button, or a source archive containing these objects. Clicking "
                  "download in a browser costs exactly the same as fetching them here."),
        # Where the material might come from instead — read from the repository's own
        # code, not guessed. Weights fetched from a drive, unpacked from an archive or
        # produced by training do not touch the quota at all.
        "insteadOfFetching": ("Before spending it, check what `probe` reports under "
                              "`acquisition`: material this repository downloads, "
                              "clones or unpacks by itself costs nothing, and anything "
                              "training produced can be produced again."),
    }
