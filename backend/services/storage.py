"""Local-disk case storage (D-001, D-004).

`01_architecture.md` § 4.4 specifies a private GCS bucket with 15-minute signed URLs.
The free-tier build writes to local disk instead, keeping the same object-key layout —
``users/{user_id}/cases/{case_id}/original.pdf`` — so the substitution is confined to
the storage backend rather than leaking into the path scheme.

Render's free tier has an ephemeral filesystem: these files are lost on redeploy and
spin-down. See DEVIATIONS.md.
"""

from pathlib import Path

from config import get_settings

OBJECT_NAME = "original.pdf"


def case_pdf_path(user_id: str, case_id: str) -> Path:
    return get_settings().upload_path / "users" / user_id / "cases" / case_id / OBJECT_NAME


def save_case_pdf(user_id: str, case_id: str, data: bytes) -> Path:
    path = case_pdf_path(user_id, case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def delete_case_pdf(user_id: str, case_id: str) -> None:
    """Used when processing fails and no case row is persisted (QUESTIONS.md Q-001)."""
    path = case_pdf_path(user_id, case_id)
    if path.exists():
        path.unlink()
    for parent in (path.parent, path.parent.parent):
        try:
            parent.rmdir()  # only removes it if empty
        except OSError:
            break
