EXECUTOR_VERSION = "1.0.0"

# (shell command template, step key) — commands run from workspace root; venv at .venv
EXECUTION_STEPS: list[tuple[str, str]] = [
    ("python -m venv .venv", "venv"),
    (".venv/bin/pip install --upgrade pip", "pip_upgrade"),
    (".venv/bin/pip install -r requirements.txt", "pip_install"),
    ('.venv/bin/python -c "import app.main"', "import_validation"),
    (".venv/bin/python -m compileall app", "syntax_validation"),
    (".venv/bin/python -m ruff check .", "ruff"),
    (".venv/bin/python -m mypy app --ignore-missing-imports", "mypy"),
    (".venv/bin/python -m pytest -q --tb=no", "pytest"),
    (".venv/bin/alembic check", "alembic"),
    ('.venv/bin/python -c "from app.main import app; assert app.title"', "startup"),
    (".venv/bin/pip check", "dependency_check"),
    ('.venv/bin/python -c "from app.core.config import settings; assert settings"', "environment"),
]

STEP_RESULT_FIELDS: dict[str, str] = {
    "ruff": "ruff_results",
    "mypy": "mypy_results",
    "pytest": "pytest_results",
    "alembic": "migration_results",
    "startup": "startup_results",
    "dependency_check": "dependency_results",
    "environment": "environment_results",
}

CRITICAL_STEPS = {"pip_install", "import_validation", "syntax_validation", "startup"}
