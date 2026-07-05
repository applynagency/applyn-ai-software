def bump_version(current: str | None) -> str:
    """Increment semantic-ish app version for lifecycle releases."""
    if not current:
        return "v1.0"

    value = current.strip().lstrip("v")
    parts = value.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return "v1.0"

    minor += 1
    return f"v{major}.{minor}"
