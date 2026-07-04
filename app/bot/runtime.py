from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
MARKER_FILE = PROJECT_ROOT / "main_bot.marker"


def load_local_env(env_path: Path = ENV_FILE) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip("'\"")


def load_app_version() -> str:
    env_version = os.getenv("APP_VERSION", "").strip()
    if env_version:
        return env_version
    try:
        pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown"
    return str((pyproject.get("project") or {}).get("version") or "unknown")


def load_app_revision() -> str:
    env_revision = os.getenv("APP_REVISION", "").strip()
    if env_revision:
        return env_revision[:12]
    git_dir = PROJECT_ROOT / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref_path = git_dir / head.split(":", 1)[1].strip()
            revision = ref_path.read_text(encoding="utf-8").strip()
        else:
            revision = head
    except OSError:
        return "unknown"
    return revision[:12] if revision else "unknown"


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


load_local_env()
APP_VERSION = load_app_version()
APP_REVISION = load_app_revision()
