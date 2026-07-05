import re

from app.schemas.frontend_v3 import FrontendDeveloperV3Output, ValidationResult

MINIMUM_TOTAL_FILES = 50
REQUIRED_FILE_NAMES = ("package.json", "README.md", "Dockerfile")
PLACEHOLDER_PATTERN = re.compile(r"\b(TODO|FIXME)\b")
IMPORT_PATTERN = re.compile(r"""from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]""")


class FrontendDeveloperV3Validator:
    """Validates Frontend Developer V3 output against code generation rules."""

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

    def _validate_imports(self, output: FrontendDeveloperV3Output, paths: set[str]) -> list[str]:
        errors: list[str] = []
        path_set = {path.lstrip("./") for path in paths}
        for file in output.generated_files:
            if not file.path.endswith((".ts", ".tsx")):
                continue
            for match in IMPORT_PATTERN.finditer(file.content):
                import_path = match.group(1) or match.group(2)
                if not import_path or import_path.startswith("@") or import_path.startswith("next"):
                    continue
                if import_path.startswith("."):
                    normalized = import_path.lstrip("./")
                    candidates = {
                        normalized,
                        f"{normalized}.ts",
                        f"{normalized}.tsx",
                        f"{normalized}/index.ts",
                        f"{normalized}/index.tsx",
                    }
                    if not any(candidate in path_set for candidate in candidates):
                        errors.append(f"{file.path}: unresolved import '{import_path}'")
        return errors

    def validate(self, output: FrontendDeveloperV3Output) -> ValidationResult:
        paths = {file.path for file in output.generated_files}
        counts: dict[str, int | bool] = {
            "total_files": len(output.generated_files),
            "has_package_json": self._has_required_file(paths, "package.json"),
            "has_readme": self._has_required_file(paths, "README.md"),
            "has_dockerfile": self._has_required_file(paths, "Dockerfile"),
            "has_package_json_field": bool(output.package_json),
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

        if not output.package_json:
            errors.append("package_json field is required")
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

        empty_files = [file.path for file in output.generated_files if not file.content.strip()]
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
            if file.path.endswith((".ts", ".tsx", ".js", ".jsx"))
            and not self._is_balanced(file.content)
        ]
        if unbalanced_files:
            errors.append(
                f"unbalanced TypeScript syntax in: {', '.join(unbalanced_files[:5])}"
            )

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
