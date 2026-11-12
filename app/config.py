"""Configuration is env-only; no credentials in Git."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def path_env(name: str, default: str) -> Path:
    path = Path(env(name, default))
    return path if path.is_absolute() else PROJECT_ROOT / path
