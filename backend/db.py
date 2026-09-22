"""SQLite persistence.

`01_architecture.md` § 5 leaves the metadata store to the implementer ("in-memory dict
or Firestore"); SQLite is chosen for durability across a reload without adding a service.

Timestamps are stored as the contract string (``%Y-%m-%dT%H:%M:%SZ``) rather than as
epoch or SQLite datetimes. That format sorts correctly under lexicographic comparison,
so ``ORDER BY uploaded_at DESC`` gives the § 5.3 ordering for free, and nothing has to
be reformatted on the way out.

Note the ephemeral filesystem on Render's free tier: this database is lost on redeploy
and spin-down. See DEVIATIONS.md.
"""

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional
from uuid import uuid4

from config import get_settings
from models.schemas import now_utc, utc_z

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL DEFAULT '',
    picture     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id         TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    status          TEXT NOT NULL,
    metadata_json   TEXT,
    dimensions_json TEXT,
    retrieval_json  TEXT,
    pdf_path        TEXT,
    uploaded_at     TEXT NOT NULL,
    processed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_cases_user_uploaded
    ON cases(user_id, uploaded_at DESC);

-- Short-lived PKCE state. The code_verifier is held server-side rather than round-
-- tripped through the browser in `state`, which would let anyone who intercepts the
-- authorization code read the verifier too and defeat the point of PKCE.
CREATE TABLE IF NOT EXISTS oauth_states (
    state         TEXT PRIMARY KEY,
    code_verifier TEXT NOT NULL,
    return_to     TEXT NOT NULL DEFAULT '/',
    created_at    TEXT NOT NULL
);
"""


def new_user_id() -> str:
    """`user_<uuidv4>` — lowercase, hyphenated (03_backend_spec.md § 12)."""
    return f"user_{uuid4()}"


def new_case_id() -> str:
    """`case_<uuidv4>` — lowercase, hyphenated (03_backend_spec.md § 5.2)."""
    return f"case_{uuid4()}"


def connect() -> sqlite3.Connection:
    settings = get_settings()
    path = settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    """One connection per operation; commits on success, rolls back on error."""
    conn = connect()
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    get_settings().upload_path.mkdir(parents=True, exist_ok=True)


# --- users ------------------------------------------------------------------


def upsert_user(email: str, name: str, picture: str) -> sqlite3.Row:
    """Find the user by email, or create one. Returns the stored row."""
    with cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if row is not None:
            # Name and picture can change on the Google side between sign-ins.
            cur.execute(
                "UPDATE users SET name = ?, picture = ? WHERE user_id = ?",
                (name, picture, row["user_id"]),
            )
            cur.execute("SELECT * FROM users WHERE user_id = ?", (row["user_id"],))
            return cur.fetchone()

        cur.execute(
            "INSERT INTO users (user_id, email, name, picture, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (new_user_id(), email, name, picture, utc_z(now_utc())),
        )
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        return cur.fetchone()


def get_user(user_id: str) -> Optional[sqlite3.Row]:
    with cursor() as cur:
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()


# --- cases ------------------------------------------------------------------


def create_case(case_id: str, user_id: str, status: str, uploaded_at: str,
                pdf_path: Optional[str] = None) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO cases (case_id, user_id, status, pdf_path, uploaded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (case_id, user_id, status, pdf_path, uploaded_at),
        )


def set_case_processed(case_id: str, metadata: dict[str, Any], processed_at: str) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE cases SET status = 'processed', metadata_json = ?, processed_at = ?"
            " WHERE case_id = ?",
            (json.dumps(metadata, ensure_ascii=False), processed_at, case_id),
        )


def set_case_dimensions(case_id: str, dimensions: list[dict[str, Any]]) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE cases SET dimensions_json = ? WHERE case_id = ?",
            (json.dumps(dimensions, ensure_ascii=False), case_id),
        )


def set_case_retrieval(case_id: str, retrieval: list[dict[str, Any]]) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE cases SET retrieval_json = ? WHERE case_id = ?",
            (json.dumps(retrieval, ensure_ascii=False), case_id),
        )


def get_case(case_id: str, user_id: str) -> Optional[sqlite3.Row]:
    """Scoped to the owner on purpose.

    `01_architecture.md` § 11 requires another user's case to look like it does not
    exist, so ownership is part of the lookup rather than a separate check a caller
    could forget.
    """
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM cases WHERE case_id = ? AND user_id = ?", (case_id, user_id)
        )
        return cur.fetchone()


def list_cases(user_id: str) -> list[sqlite3.Row]:
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM cases WHERE user_id = ? ORDER BY uploaded_at DESC", (user_id,)
        )
        return cur.fetchall()


# --- oauth state ------------------------------------------------------------


def save_oauth_state(state: str, code_verifier: str, return_to: str) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO oauth_states (state, code_verifier, return_to, created_at)"
            " VALUES (?, ?, ?, ?)",
            (state, code_verifier, return_to, utc_z(now_utc())),
        )


def take_oauth_state(state: str) -> Optional[sqlite3.Row]:
    """Consume a state — single use, so a replayed callback cannot succeed twice."""
    with cursor() as cur:
        cur.execute("SELECT * FROM oauth_states WHERE state = ?", (state,))
        row = cur.fetchone()
        if row is not None:
            cur.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return row
