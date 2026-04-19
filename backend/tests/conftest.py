"""Pytest configuration for backend tests.

Ensures the repository root is on `sys.path` so the `backend.*`
package can be imported when tests are invoked from any directory.
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
