"""Safe subprocess execution for security scanner providers (Sprint 65E)."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

MAX_OUTPUT_BYTES = 1_048_576
DEFAULT_TIMEOUT_SECONDS = 300

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|credential|bearer)\s*[:=]\s*\S+",
)

# binary -> allowed argument prefixes (no shell, argv only)
PROVIDER_BINARIES: dict[str, list[str]] = {
    "trivy": ["image", "fs", "sbom", "version", "--format", "--output", "--quiet", "--severity"],
    "gitleaks": ["detect", "version", "--source", "--no-git", "--report-format", "--report-path"],
    "semgrep": ["scan", "--config", "--json", "--error", "--version"],
    "checkov": ["-f", "-d", "--framework", "--output", "--quiet", "--version"],
    "tfsec": [".", "--format", "json", "--version"],
}

PROVIDER_TYPE_TO_BINARY: dict[str, str] = {
    "TRIVY": "trivy",
    "GITLEAKS": "gitleaks",
    "SEMGREP": "semgrep",
    "CODEQL": "semgrep",
    "CHECKOV": "checkov",
    "TFSEC": "tfsec",
    "SBOM_PARSER": "python",
}


def redact_output(text: str, *, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    if not text:
        return ""
    redacted = _SECRET_RE.sub(r"\1=[REDACTED]", text)
    if len(redacted.encode()) > max_bytes:
        redacted = redacted.encode()[:max_bytes].decode("utf-8", errors="ignore") + "\n...[truncated]"
    return redacted


def validate_argv(binary: str, argv: list[str]) -> None:
    allowed = PROVIDER_BINARIES.get(binary)
    if allowed is None:
        raise ValueError(f"binary not allowlisted: {binary}")
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        if not any(arg == p or arg.startswith(p) for p in allowed if not p.startswith("-")):
            if not any(arg.startswith(p.rstrip("=")) for p in allowed if p.startswith("-")):
                raise ValueError(f"argument not allowlisted for {binary}: {arg}")


def resolve_binary(provider_type: str) -> str | None:
    binary = PROVIDER_TYPE_TO_BINARY.get(provider_type.upper())
    if not binary:
        return None
    return shutil.which(binary)


def detect_mode(provider_type: str, *, enabled: bool) -> str:
    if not enabled:
        return "unavailable"
    binary = PROVIDER_TYPE_TO_BINARY.get(provider_type.upper())
    if not binary:
        return "unavailable"
    if shutil.which(binary):
        return "live"
    return "offline"


async def run_safe_command(
    binary: str,
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute an allowlisted binary via asyncio subprocess (no shell)."""
    validate_argv(binary, argv)
    proc = await asyncio.create_subprocess_exec(
        binary, *argv[1:],
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return {"exit_code": -1, "timed_out": True, "stdout": "", "stderr": "timeout"}
    out = redact_output((stdout or b"").decode("utf-8", errors="replace"))
    err = redact_output((stderr or b"").decode("utf-8", errors="replace"))
    return {
        "exit_code": proc.returncode,
        "timed_out": False,
        "stdout": out,
        "stderr": err,
    }


class ScannerWorkspace:
    """Temporary workspace with guaranteed cleanup."""

    def __init__(self) -> None:
        self._dir: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        self._dir = tempfile.TemporaryDirectory(prefix="nexora-sec-")
        return Path(self._dir.name)

    def __exit__(self, *args: object) -> None:
        if self._dir:
            self._dir.cleanup()
            self._dir = None
