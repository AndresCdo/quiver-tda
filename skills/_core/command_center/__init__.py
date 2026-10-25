"""Paper Command Center: a local dashboard and health control plane.

The package lives at ``skills/_core/command_center/`` inside a PaperSmith
workspace. Because ``skills/`` is a kit entry every workspace receives, the
whole command center travels with ``papersmith init``/``upgrade`` and runs
standalone from the workspace root::

    python -m skills._core.command_center.server --port 8080

Nothing here writes to the workspace. Every reader is read-only and
best-effort: a damaged file degrades one field, never the whole payload.
"""

from __future__ import annotations

__all__ = ["__version__"]

#: Kept in lockstep with the served frontend build under ``static/``.
__version__ = "0.1.0"
