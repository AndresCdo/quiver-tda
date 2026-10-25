"""Level 2 - properties and invariants. The bridge between proposal and code.

One test per mathematical claim the proposal makes. The name MUST be
`test_<invariant_id>`, matching an id declared in a module's
`__provenance__["invariants"]`; verification pairs them by that exact name.

Each docstring cites the passage it enforces. A test whose claim cannot be
traced back to the proposal does not belong here.
"""

from __future__ import annotations

from {{PKG}}.{{MODULE}} import {{FUNCTION_NAME}}  # noqa: F401

TOL = 1e-10


def test_{{INVARIANT_ID}}() -> None:
    """<revision> § <section>, Eq. (<n>): <the claim, in words>."""
    raise NotImplementedError
