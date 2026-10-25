from __future__ import annotations

from pathlib import Path

# The forge root: <root>/skills/_core/implementation/impl_layout.py.
#
# Four path components, exactly as many as the CLI that used to own this
# constant had from <root>/skills/proposal-implementation/scripts/. The
# equality is a coincidence of two directory names, not a rule, and a test pins
# it: a future move of either file changes the count in silence, and nothing
# that reads a repository from the wrong root fails loudly.
FORGE_ROOT = Path(__file__).resolve().parents[3]

#: Where every target repository is cloned. Gitignored, and the only place a
#: guard will let an implementation skill write.
WORKSPACE = FORGE_ROOT / "implementations"


IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints",
    ".mypy_cache", ".ruff_cache", ".idea", ".vscode", "node_modules", ".codegraph",
}


#: The first bytes of a Git LFS pointer. A pointer is a few hundred bytes of text
#: standing where a large file is declared to be; anything that opens it as data
#: gets a parse error that names the format it expected and not the reason.
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/"


TEXT_EXT = {".py", ".ipynb", ".md", ".rst", ".txt", ".toml", ".cfg", ".ini",
            ".yaml", ".yml", ".json", ".sh"}
