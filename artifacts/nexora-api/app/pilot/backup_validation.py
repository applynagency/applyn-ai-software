"""Backup archive integrity helpers (Sprint 67E)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def validate_pg_backup_archive(archive_path: str | Path) -> dict:
    """Validate a pg_dump custom-format archive using ``pg_restore --list``.

    Returns a safe result dict without connection strings or secrets.
    """
    path = Path(archive_path)
    if not path.exists():
        return {
            "valid": False,
            "detail": "Backup archive not found",
            "table_count": 0,
        }

    try:
        proc = subprocess.run(
            ["pg_restore", "--list", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        return {
            "valid": False,
            "detail": "pg_restore not available",
            "table_count": 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "valid": False,
            "detail": "pg_restore --list timed out",
            "table_count": 0,
        }

    if proc.returncode != 0:
        return {
            "valid": False,
            "detail": "pg_restore --list failed",
            "table_count": 0,
        }

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip() and not ln.startswith(";")]
    pilot_tables = [ln for ln in lines if "pilot_" in ln.lower()]
    return {
        "valid": True,
        "detail": f"Archive listable; {len(lines)} entries",
        "table_count": len(lines),
        "pilot_table_entries": len(pilot_tables),
    }
