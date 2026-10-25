from __future__ import annotations

import re
from pathlib import Path
from impl_gitops import read_text, text_files


def prefix_mappings(renames: list[dict], moves: list[dict]) -> list[tuple[str, str]]:
    """Every `old prefix -> new prefix` a migration implies.

    A rename gives one directly. Moves give one too, and forgetting them breaks
    exactly as much: after `Alpha/<Category>/x.csv -> <Name>/<Category>/x.csv`,
    code addressing `Alpha/<Category>` points nowhere. The prefix is derived by
    stripping the longest common suffix, so a move that only nests a folder
    deeper yields `<Category> -> <Name>/<Category>`, not a bare rename.

    The categories themselves are the caller's; this file names none of them.
    """
    mappings: dict[str, set[str]] = {}
    for rename in renames:
        mappings.setdefault(rename["from"], set()).add(rename["to"])

    for move in moves:
        source, dest = Path(move["from"]).parts, Path(move["to"]).parts
        common = 0
        while (common < min(len(source), len(dest))
               and source[-1 - common] == dest[-1 - common]):
            common += 1
        keep = max(1, len(source) - common)
        mappings.setdefault("/".join(source[:keep]), set()).add(
            "/".join(dest[:len(dest) - len(source) + keep])
        )

    # An ambiguous prefix (two destinations) is left alone: rewriting it would
    # have to guess, and a wrong rewrite is worse than a reported one.
    return sorted((old, next(iter(new))) for old, new in mappings.items() if len(new) == 1)


def reference_pattern(needle: str, kind: str, anchored: bool) -> re.Pattern:
    """Match `needle`, anchored to a path boundary only when nesting demands it.

    Two mappings behave differently. A pure rename (`Images -> <Name>`) is safe
    to replace anywhere: the new value cannot contain the old one, so a nested
    occurrence such as a URL `.../blob/main/Images/<Category>/` is a genuine hit
    and must be rewritten. A nesting mapping (`<Category> -> <Name>/<Category>`)
    must be anchored, or `Images/<Category>/` becomes `Images/<Name>/<Category>/`.
    """
    if kind == "path prefix" and anchored:
        return re.compile(r"(?<![\w./-])" + re.escape(needle))
    return re.compile(re.escape(needle))


def is_nesting(old: str, new: str) -> bool:
    """True when the new prefix merely nests the old one deeper."""
    return new.endswith(f"/{old}")


def scan_reference_updates(target: Path, mappings: list[tuple[str, str]],
                           paths: list[str]) -> list[dict]:
    """Files naming an old path that the migration is about to invalidate."""
    updates: list[dict] = []
    for old, new in mappings:
        if old == new:
            continue
        patterns = [(f"{old}/", f"{new}/", "path prefix")]
        # Only a pure one-segment rename is safe to rewrite in quoted form;
        # substituting a multi-segment path into a quoted literal would match
        # unrelated strings.
        if "/" not in old and "/" not in new:
            patterns += [(f'"{old}"', f'"{new}"', "quoted path segment"),
                         (f"'{old}'", f"'{new}'", "quoted path segment")]
        for rel in text_files(target, paths):
            content = read_text(target, rel)
            if not content:
                continue
            for needle, replacement, kind in patterns:
                anchored = is_nesting(old, new)
                hits = len(reference_pattern(needle, kind, anchored).findall(content))
                if hits:
                    updates.append({
                        "file": rel,
                        "occurrences": hits,
                        "kind": kind,
                        "anchored": anchored,
                        "replace": needle,
                        "with": replacement,
                    })
    return updates


def scan_stale_references(target: Path, name: str, paths: list[str],
                          patterns: tuple) -> list[dict]:
    """Textual `<folder>/<Category>` paths under a parent that does not exist.

    `patterns` are the caller's compiled `<folder>/<Category>` matchers, each
    yielding folder as group 1 and category as group 2.

    Deliberately narrow. A quoted single segment (`root / "data"`) is NOT
    flagged: fallback probes for optional dataset roots are legitimately absent,
    so treating every missing directory as breakage buries the real finding.
    That form is still rewritten during a rename, where the exact old name is
    known and the user approves the list first.
    """
    def resolves(folder: str, category: str) -> bool:
        """An empty directory is not a destination: the content it named is gone.

        `git mv` leaves the old parents behind as empty shells, so existence
        alone would report a broken path as healthy.
        """
        directory = target / folder / category
        if not directory.is_dir():
            return False
        return any(entry.name != ".gitkeep" for entry in directory.iterdir())

    stale: list[dict] = []
    for rel in text_files(target, paths):
        content = read_text(target, rel)
        if not content:
            continue
        # The patterns come from the caller because they are built out of ITS
        # product directories. A `<folder>/<Category>` reference means nothing
        # without knowing which categories this domain has, and that is the one
        # thing about reference scanning that is not shared.
        pairs = {(m.group(1), m.group(2))
                 for pattern in patterns for m in pattern.finditer(content)}
        broken = sorted(f"{folder}/{category}" for folder, category in pairs
                        if folder != name and not resolves(folder, category))
        if broken:
            stale.append({"file": rel, "references": broken})
    return stale
