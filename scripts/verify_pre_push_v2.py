"""Record local checks or a fresh Python 3.12 test run without private runtime data."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/pre-push/v2"


def run(name, command, cwd=ROOT):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    (OUT / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    record = {"command": command, "exit_code": result.returncode,
              "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    (OUT / (name + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(name, result.returncode, flush=True)
    return result.returncode


def local():
    commands = {
        "pytest-local": [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short", "--basetemp", "data/runtime/v2-tests-" + uuid.uuid4().hex, "-o", "cache_dir=data/runtime/v2-pytest-cache", "--junitxml=reports/pre-push/v2/pytest-local.xml"],
        "ruff": [sys.executable, "-m", "ruff", "check", "app", "tests", "scripts", "--select", "E4,E7,E9,F63,F7,F82"],
        "gate-historical": [sys.executable, "-m", "scripts.quality_gate"],
        "gate-development": [sys.executable, "-m", "scripts.quality_gate", "--results", "reports/rag-v2/gate-results.json", "--baseline", "docs/rag-v2-quality-baseline.json"],
        "secrets": [sys.executable, "-m", "scripts.check_secrets"],
        "pip-check": [sys.executable, "-m", "pip", "check"],
    }
    return max(run(name, command) for name, command in commands.items())


def clean():
    runtime = ROOT / "data/runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="prepush-v2-clean-", dir=runtime) as directory:
        source = Path(directory)
        assert source.resolve().is_relative_to(runtime.resolve())
        shutil.copyfile(ROOT / ".env.example", source / ".env.example")
        for name in ("app", "scripts", "tests", "docs", "evaluation", ".github"):
            shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for path in ROOT.iterdir():
            if path.is_file() and path.suffix in (".txt", ".md", ".toml", ".yml", ".yaml"):
                shutil.copyfile(path, source / path.name)
        for name in ("reports/evaluation.json", "reports/rag-v2/gate-results.json"):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        command = ["docker", "run", "--rm", "--mount", f"type=bind,source={source},target=/source,readonly",
                   "--mount", f"type=bind,source={OUT},target=/evidence", "--workdir", "/source",
                   "--env", "PYTHONDONTWRITEBYTECODE=1", "python:3.12-slim", "sh", "-c",
                   "apt-get update > /evidence/clean-tools.log 2>&1 && "
                   "apt-get install -y --no-install-recommends git >> /evidence/clean-tools.log 2>&1 && "
                   "python -m pip install -r requirements-linux-py312.lock.txt > /evidence/clean-install.log 2>&1 && "
                   "python -m pip freeze --all > /evidence/python312.lock.txt && "
                   "python -m pip check > /evidence/clean-pip-check.log 2>&1 && "
                   "python -m pytest tests -q --tb=short -p no:cacheprovider --junitxml=/evidence/pytest-clean.xml "
                   "> /evidence/pytest-clean.log 2>&1 && "
                   "python -m ruff check app tests scripts --no-cache --select E4,E7,E9,F63,F7,F82 > /evidence/ruff-clean.log 2>&1 && "
                   "python -m scripts.quality_gate > /evidence/gate-historical-clean.log 2>&1 && "
                   "python -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json > /evidence/gate-development-clean.log 2>&1 && "
                   "python -m scripts.check_secrets > /evidence/secrets-clean.log 2>&1"]
        return run("clean-run", command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("local", "clean"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    raise SystemExit(clean() if args.mode == "clean" else local())
