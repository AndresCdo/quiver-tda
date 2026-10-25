"""Level 3 - synthetic data. Deterministic, fixed seed, ground truth by construction.

State each expectation in the docstring BEFORE the assertion, so a passing test
cannot be mistaken for a hypothesis fitted after seeing the output.
"""

from __future__ import annotations

import numpy as np

SEED = {{SEED}}


def test_{{EXPECTATION}}(rng) -> None:
    """Expectation: <what must happen, and why, stated before running>."""
    raise NotImplementedError
