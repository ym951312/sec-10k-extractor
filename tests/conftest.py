"""Shared pytest fixtures and path setup.

``pythonpath = ["src"]`` in pyproject already puts the package on the path, but
we add it here too so the suite runs even when invoked without the pytest config
(e.g. ``python -m pytest tests/test_x.py`` from an odd cwd).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
