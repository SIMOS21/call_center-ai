"""Read-only final secret/history audit. Never prints matched values."""
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path


def main():
    patterns = [re.compile(rb"nvapi-[A-Za-z0-9_-]{20,}"), re.compile(rb"gsk_[A-Za-z0-9]{20,}"), re.compile(rb"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}")]
    findings = []
    checked = 0
    for directory in ("app", "scripts", "tests", "docs", "evaluation", "integrations", "reports", "output", ".github"):
        for base, folders, files in os.walk(directory):
            folders[:] = [f for f in folders if f not in (".git", "__pycache__", "release", "clean-source")]
            for name in files:
                path = Path(base)/name
                if path.suffix.lower() in (".py", ".ts", ".md", ".json", ".jsonl", ".log", ".xml", ".yml", ".ps1", ".cmd", ".txt"):
                    checked += 1
                    if any(p.search(path.read_bytes()) for p in patterns):
                        findings.append(str(path))
    for path in (Path(".env.example"), Path("README.md")):
        if any(p.search(path.read_bytes()) for p in patterns):
            findings.append(str(path))
    histories = []
    for root in (Path("."), Path("reports/final-audit/release")):
        commits = subprocess.check_output(["git", "-C", str(root), "rev-list", "--all"], text=True).splitlines()
        for commit in commits:
            files = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "--name-only", commit], text=True).splitlines()
            for name in files:
                data = subprocess.check_output(["git", "-C", str(root), "show", f"{commit}:{name}"])
                if any(p.search(data) for p in patterns):
                    findings.append(f"history:{commit[:12]}:{name}")
        histories.append({"repository": str(root), "commits_scanned": len(commits)})
    db = Path("data/mlflow.sqlite3")
    trace_cells = 0
    if db.exists():
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as cx:
            tables = [row[0] for row in cx.execute("SELECT name FROM sqlite_master WHERE type='table'") if "trace" in row[0] or "span" in row[0]]
            for table in tables:
                for row in cx.execute('SELECT * FROM "'+table.replace('"','""')+'"'):
                    for cell in row:
                        if isinstance(cell, str):
                            trace_cells += 1
                            if any(p.search(cell.encode()) for p in patterns):
                                findings.append("mlflow:"+table)
    history_path = Path(os.environ.get("APPDATA", ""))/"Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"
    history_status = "NOT_AVAILABLE"
    try:
        content = history_path.read_bytes()
        history_status = "SCANNED"
        if any(p.search(content) for p in patterns):
            findings.append("local_shell_history")
    except OSError:
        pass
    report = {"status": "PASS" if not findings else "FAIL", "text_files_scanned": checked, "trace_text_cells_scanned": trace_cells, "git_history": histories, "shell_history": history_status, "findings_paths_only": sorted(set(findings)), "limitation": "Pattern-based audit; chat/tool history cannot be erased or independently inspected. Rotation is user-attested."}
    Path("reports/final-audit/security.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    raise SystemExit(bool(findings))


if __name__ == "__main__":
    main()
