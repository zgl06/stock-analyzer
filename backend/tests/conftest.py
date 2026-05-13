"""Pytest configuration for backend tests.

Ensures the repository root is on `sys.path` so the `backend.*`
package can be imported when tests are invoked from any directory.

Loads the same ``.env`` files as :mod:`backend.app.config` so flags like
``RUN_YFINANCE_SMOKE`` in the root or ``backend/.env`` are visible to pytest
(including ``@pytest.mark.skipif`` that read ``os.environ`` at import time).
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[1]
# Match config.py order: root first, then backend (first wins for duplicate keys).
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env")

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
