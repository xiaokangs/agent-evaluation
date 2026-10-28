import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def python_on_path(monkeypatch):
    """Make sure `python` (used by task validator commands) resolves to this interpreter."""
    bindir = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", bindir + os.pathsep + os.environ.get("PATH", ""))
    return bindir
