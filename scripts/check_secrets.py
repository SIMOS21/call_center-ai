"""Offline source/committed-file hygiene gate. Prints paths only, never secrets."""
import re
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    problems = []
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    if tracked.returncode == 0:
        for name in tracked.stdout.splitlines():
            path = Path(name)
            if path.name == ".env" or path.suffix in (".sqlite3", ".db") or name.startswith(("data/raw/", "data/knowledge/")) or "credentials" in name:
                problems.append(name)
    patterns = [re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"), re.compile(r"gsk_[A-Za-z0-9]{20,}"), re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}")]
    files = [root / ".env.example", root / "README.md"]
    for folder in ("app", "scripts", "tests", "docs", ".github", "evaluation", "integrations", "reports"):
        files.extend(path for path in (root / folder).rglob("*") if path.is_file()
                     and path.suffix in (".py", ".ts", ".md", ".json", ".jsonl", ".yml", ".yaml"))
    for path in files:
        content = path.read_text(encoding="utf-8-sig")
        if any(pattern.search(content) for pattern in patterns):
            problems.append(str(path.relative_to(root)))
    print("SOURCE HYGIENE", "FAIL" if problems else "PASS")
    for path in sorted(set(problems)):
        print(path)
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
