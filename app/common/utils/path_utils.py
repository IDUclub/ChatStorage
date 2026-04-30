from pathlib import Path


def find_project_root() -> Path:
    current = Path.cwd()
    for path in [current, *current.parents]:
        if (path / "pyproject.toml").exists() or (path / ".git").exists():
            return path
    return Path.cwd()
