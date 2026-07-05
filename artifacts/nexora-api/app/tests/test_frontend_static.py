import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "static" / "app.js"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-frontend.js"
FRONTEND_TESTS = ROOT / "static" / "frontend.test.mjs"


@pytest.fixture(scope="module")
def node_executable() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for frontend regression tests")
    return node


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def test_app_js_parses_with_node_check(node_executable: str) -> None:
    _run([node_executable, "--check", str(APP_JS)])


def test_validate_frontend_script_passes(node_executable: str) -> None:
    _run([node_executable, str(VALIDATE_SCRIPT)])


def test_frontend_regression_suite_passes(node_executable: str) -> None:
    _run([node_executable, "--test", str(FRONTEND_TESTS)])
