from __future__ import annotations


class Refused(Exception):
    """A guard refused to run. Nothing was modified."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class NameRefused(Exception):
    """The name the user typed cannot become a directory and a package."""
