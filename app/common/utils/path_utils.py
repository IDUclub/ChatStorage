from pathlib import Path


def resolve_logs_path(raw_path: str | None, workdir: Path) -> Path:
    """
    Function resolves log path based on provided raw path.
    Args:
        raw_path (str | None): Raw path provided from env variable. Can be None.
        workdir (Path): Path to current working directory.
    Returns:
        Path: Resolved path to target log file.
    """

    if raw_path is None or not raw_path.strip():  # default logs path
        return workdir / "logs"
    logs_path = Path(raw_path.strip()).expanduser()
    if logs_path.is_absolute():  # absolute logs path
        return logs_path
    return workdir / logs_path  # relative logs path
