from __future__ import annotations

import re
from impl_refusals import NameRefused, Refused


def validate_name(name: str) -> str:
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        raise Refused("INVALID_NAME", f"Name {name!r} must be alphanumeric (- and _ allowed).")
    return name


def package_name(name: str) -> str:
    """The importable form of the name.

    A hyphen is legal in a directory but not in a Python identifier, so
    `Example-Method/` pairs with `<sources>/Example_Method/`. The correspondence the layout
    exists to make visible survives; `import Example-Method` would not.
    """
    return name.replace("-", "_")


def normalize_name(raw: str) -> dict:
    """Turn whatever the user typed into the `<Name>/` + `<sources>/<Package>/` pair.

    The user types `deep set`, `DEEP-SET` or `deepSet` and means the same thing.
    Splitting happens on any separator and on a lower-to-upper boundary; an all-caps
    token of two or more letters is an acronym and survives untouched, because
    lowercasing an acronym renames the method rather than tidying the folder.
    """
    text = (raw or "").strip()
    if not text:
        raise NameRefused("NAME_EMPTY")
    # Split first on explicit separators, then inside each piece on camel boundaries.
    # The trailing alternative catches any run the ASCII patterns above it do not:
    # a stray symbol or a non-ASCII letter. Nothing is left to fall through
    # unmatched, so nothing is silently dropped -- it becomes a token and meets
    # the guard below instead. Before this, a character no alternative matched
    # (an accent, a CJK letter) simply vanished from the name; "münchen" became
    # "M-Nchen" with no refusal at all. Losing letters silently is worse than
    # refusing the name, so the guard is made reachable rather than removed.
    tokens: list[str] = []
    for piece in re.split(r"[\s\-_]+", text):
        if not piece:
            continue
        tokens.extend(re.findall(
            r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+|[^A-Za-z0-9]+", piece))
    if not tokens:
        raise NameRefused("NAME_HAS_NO_WORDS")
    for token in tokens:
        # `str.isalnum` is Unicode-aware and accepts letters like 'é'; the
        # tokenizer above only ever hands ASCII patterns a match, so a token
        # that survives here is either every character the ASCII patterns
        # matched, or the catch-all run of whatever they did not. An ASCII
        # check is what actually distinguishes the two.
        if not (token.isascii() and token.isalnum()):
            raise NameRefused(f"NAME_NOT_ALPHANUMERIC:{token}")
    if tokens[0][0].isdigit():
        raise NameRefused("NAME_STARTS_WITH_DIGIT")
    parts = [token if token.isupper() and len(token) >= 2 else token.capitalize()
             for token in tokens]
    return {"input": raw, "directory": "-".join(parts), "package": "_".join(parts)}
