"""Test configuration.

The environment is redirected to a temporary directory **at import time**, before any
test module is loaded. That timing matters: `main.py` calls `get_settings()` while the
module body executes (to build the CORS allow-list), and `get_settings` is
`lru_cache`d, so anything set later would arrive too late and the suite would read and
write the real development database.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="minijurinex-tests-"))

# Environment variables outrank the .env file in pydantic-settings, so these win.
os.environ["SQLITE_PATH"] = str(_TMP / "test.db")
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used-gemini-is-mocked")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("JWT_SIGNING_SECRET", "test-signing-secret-for-tests-only")
os.environ.setdefault("EVAL_TOKEN", "test-eval-token")

import pytest  # noqa: E402

from config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return _TMP
