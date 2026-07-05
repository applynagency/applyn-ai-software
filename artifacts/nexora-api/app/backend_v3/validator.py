import ast
import re

from app.schemas.backend_v3 import BackendDeveloperV3Output, ValidationResult

MINIMUM_TOTAL_FILES = 50
REQUIRED_FILE_NAMES = ("requirements.txt", "README.md", "Dockerfile")
PLACEHOLDER_PATTERN = re.compile(r"\b(TODO|FIXME)\b")
PYTHON_IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)


class BackendDeveloperV3Validator:
    """Validates Backend Developer V3 output against code generation rules."""

    def _has_required_file(self, paths: set[str], name: str) -> bool:
        return any(path == name or path.endswith(f"/{name}") for path in paths)

    def _is_balanced(self, content: str) -> bool:
        pairs = {"(": ")", "{": "}", "[": "]"}
        stack: list[str] = []
        for char in content:
            if char in pairs:
                stack.append(pairs[char])
            elif char in pairs.values():
                if not stack or stack.pop() != char:
                    return False
        return not stack

    def _validate_python_syntax(self, output: BackendDeveloperV3Output) -> list[str]:
        errors: list[str] = []
        for file in output.generated_files:
            if not file.path.endswith(".py"):
                continue
            try:
                ast.parse(file.content)
            except SyntaxError as exc:
                errors.append(f"{file.path}: Python syntax error — {exc.msg}")
        return errors

    def _validate_imports(self, output: BackendDeveloperV3Output, paths: set[str]) -> list[str]:
        errors: list[str] = []
        path_set = {path.lstrip("./") for path in paths}
        module_paths = {
            path.replace("/", ".").removesuffix(".py").removesuffix(".__init__")
            for path in path_set
            if path.endswith(".py")
        }
        stdlib_and_third_party_prefixes = (
            "fastapi",
            "pydantic",
            "sqlalchemy",
            "alembic",
            "redis",
            "jwt",
            "pytest",
            "httpx",
            "uvicorn",
            "typing",
            "datetime",
            "enum",
            "os",
            "re",
            "json",
            "logging",
            "contextlib",
            "functools",
            "dataclasses",
            "uuid",
        )
        for file in output.generated_files:
            if not file.path.endswith(".py"):
                continue
            for match in PYTHON_IMPORT_PATTERN.finditer(file.content):
                import_path = match.group(1)
                if import_path.startswith(stdlib_and_third_party_prefixes):
                    continue
                if import_path.startswith("app."):
                    subpath = import_path.replace(".", "/") + ".py"
                    init_path = import_path.replace(".", "/") + "/__init__.py"
                    if subpath not in path_set and init_path not in path_set:
                        if import_path not in module_paths:
                            errors.append(f"{file.path}: unresolved import '{import_path}'")
        return errors

    def validate(self, output: BackendDeveloperV3Output) -> ValidationResult:
        paths = {file.path for file in output.generated_files}
        counts: dict[str, int | bool] = {
            "total_files": len(output.generated_files),
            "has_requirements_txt": self._has_required_file(paths, "requirements.txt"),
            "has_readme": self._has_required_file(paths, "README.md"),
            "has_dockerfile": self._has_required_file(paths, "Dockerfile"),
            "has_requirements_txt_field": bool(output.requirements_txt.strip()),
            "has_readme_field": bool(output.readme.strip()),
            "has_docker_configuration": bool(output.docker_configuration),
        }

        errors: list[str] = []
        score_components: list[float] = []

        if len(output.generated_files) < MINIMUM_TOTAL_FILES:
            errors.append(
                f"total_files: requires at least {MINIMUM_TOTAL_FILES}, "
                f"got {len(output.generated_files)}"
            )
            score_components.append(
                (len(output.generated_files) / MINIMUM_TOTAL_FILES) * 100
            )
        else:
            score_components.append(100.0)

        for required in REQUIRED_FILE_NAMES:
            if not self._has_required_file(paths, required):
                errors.append(f"missing required file: {required}")
                score_components.append(0.0)
            else:
                score_components.append(100.0)

        if not output.requirements_txt.strip():
            errors.append("requirements_txt field is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.readme.strip():
            errors.append("readme field is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.docker_configuration:
            errors.append("docker_configuration field is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        empty_files = [
            file.path
            for file in output.generated_files
            if not file.content.strip() and not file.path.endswith("__init__.py")
        ]
        if empty_files:
            errors.append(f"empty content in files: {', '.join(empty_files[:5])}")

        placeholder_files = [
            file.path
            for file in output.generated_files
            if PLACEHOLDER_PATTERN.search(file.content)
        ]
        if placeholder_files:
            errors.append(
                f"TODO/FIXME placeholders found in: {', '.join(placeholder_files[:5])}"
            )

        unbalanced_files = [
            file.path
            for file in output.generated_files
            if file.path.endswith(".py") and not self._is_balanced(file.content)
        ]
        if unbalanced_files:
            errors.append(
                f"unbalanced Python syntax in: {', '.join(unbalanced_files[:5])}"
            )

        syntax_errors = self._validate_python_syntax(output)
        if syntax_errors:
            errors.extend(syntax_errors[:5])

        import_errors = self._validate_imports(output, paths)
        if import_errors:
            errors.extend(import_errors[:5])

        base_score = sum(score_components) / len(score_components) if score_components else 0
        penalty = min(40.0, len(errors) * 5)
        score = max(0.0, min(100.0, base_score - penalty))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
