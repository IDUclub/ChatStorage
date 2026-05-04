from pathlib import Path


def find_project_root() -> Path:
    return Path(__file__).resolve().parents[3]
