"""{{ONE_LINE_STATEMENT_OF_THE_MATHEMATICAL_OBJECT}}.

One module per mathematical object of the proposal. `__provenance__` is read
statically by `implementation_cli.py verify` — the module is never imported to
obtain it — and it is the only thing that makes revision drift detectable.

Rules:
- `revision` is the exact managed filename this code was written against.
- `sections` and `equations` point at the passage that justifies the code.
- every id in `invariants` MUST have a matching `test_<id>` under tests/.
  A declared invariant with no test fails verification.
- `__provenance__` goes after the docstring and after any `from __future__`
  import; placing it first is a SyntaxError.
"""

from __future__ import annotations

import numpy as np

__provenance__ = {
    "revision": "{{REVISION}}",
    "sections": ["{{SECTION}}"],
    "equations": ["{{EQUATION}}"],
    "invariants": ["{{INVARIANT_ID}}"],
}


def {{FUNCTION_NAME}}(x: np.ndarray) -> np.ndarray:
    """Implement Eq. ({{EQUATION}}). State the assumptions the proposal makes."""
    raise NotImplementedError
