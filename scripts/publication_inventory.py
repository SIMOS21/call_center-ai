"""Explicit publication candidates and secret scan; no Git index mutation."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/pre-push/global"
TEXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs", ".json", ".jsonl", ".md", ".txt", ".toml", ".yml", ".yaml", ".css", ".scss", ".html", ".ps1", ".patch", ".ini", ".cfg"}
BAD = {".git", ".venv", "node_modules", "__pycache__", ".next", ".medusa", "data", "mlruns", "mlartifacts", ".pytest_cache", ".ruff_cache", ".turbo", ".aws", ".codex", "uploads", "logs", "dist", "build"}
PROOFS = {"live-scenarios.json", "documentary-grounding.json", "trace-privacy.json", "frozen-integrity.json", "services-health.json", "sqlite-acceptance.json", "before-after.json", "dependency-matrix.json", "changes.json", "validation-summary.json", "publication-summary.json"}
PATTERNS = {
    "provider_token": re.compile(r"(?:nvapi-|gsk_|sk-[A-Za-z0-9_-]{2}|hf_|ghp_|github_pat_)[A-Za-z0-9_-]{20,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
IDENTIFIERS = re.compile(r"\b(?:cus|customer|cart|order|return|variant|prod)_(?:[0-9A-HJKMNP-TV-Z]{26}|[0-9a-f]{32})\b|\bsess_[A-Za-z0-9_-]{43}\b|\bappr_[0-9a-f]{32}\b")


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.DEVNULL)


def forbidden(name):
    path = Path(name)
    return (any(part in BAD for part in path.parts) or "credential" in path.name.lower()
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in (".npmrc", ".netrc", ".pypirc")
            or path.suffix.lower() in (".db", ".sqlite", ".sqlite3", ".pem", ".key", ".zip", ".log", ".xml", ".pyc")
            or name.startswith(("evaluation/final", "evaluation/manual_gold")))


def candidate(label, name):
    if forbidden(name):
        return False
    path = Path(name)
    if label == "my-medusa-store":
        return path.suffix in TEXT or path.name in (".gitignore", "LICENSE") or name.startswith("apps/storefront/public/")
    if name.startswith(("app/", "scripts/", "tests/", "docs/", "integrations/", ".github/", "evaluation/")):
        return path.suffix in TEXT
    if name.startswith("reports/pre-push/global/"):
        return path.suffix == ".md" or path.name in PROOFS
    if name.startswith("reports/pre-push/v5/"):
        return path.suffix in (".md", ".csv") or path.name in {"functional-scenarios.json", "nvidia-documentary-scenarios.json", "trace-privacy.json", "frozen-integrity.json", "pdf-validation.json"}
    if path.suffix == ".md" and ("/" not in name or name.startswith("reports/pre-push/FINAL_AUDIT")):
        return True
    return name in {".env.example", ".gitignore", ".gitattributes", "LICENSE", "pyproject.toml", "reports/evaluation.json", "reports/rag-v2/gate-results.json", "output/pdf/CommerceOps_AI_Rapport_Final.pdf"} or ("/" not in name and name.startswith("requirements") and path.suffix == ".txt")


def main():
    values = []
    for file in (ROOT / ".env", ROOT.parent / "my-medusa-store/apps/backend/.env", ROOT.parent / "my-medusa-store/apps/backend/.env.admin", ROOT.parent / "my-medusa-store/.env.docker"):
        if file.exists():
            values.extend(value for key, value in dotenv_values(file).items() if value and len(value) >= 8 and re.search(r"key|secret|password|token|database_url", key, re.I))
    credentials = ROOT / "data/demo-credentials.json"
    if credentials.exists():
        for item in json.loads(credentials.read_text()):
            values.extend(v for v in item.values() if isinstance(v, str) and len(v) >= 8)

    def rules(raw, name):
        text = raw.decode("utf-8-sig", errors="replace")
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages)
        found = [label for label, pattern in PATTERNS.items() if pattern.search(text)]
        if any(value in text for value in values):
            found.append("known_local_credential")
        return found, bool(IDENTIFIERS.search(text))

    summary = {}
    for label, repo in (("commerceops_ai", ROOT), ("my-medusa-store", ROOT.parent / "my-medusa-store")):
        rows, excluded, findings = [], [], []
        names = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
        for name in sorted(set(names) - {""}):
            path = repo / name
            if not path.is_file():
                continue
            if not candidate(label, name):
                excluded.append(name)
                continue
            raw = path.read_bytes()
            detected, identifiers = rules(raw, name)
            if detected:
                findings.append({"path": name, "rules": detected})
                excluded.append(name)
                continue
            try:
                indexed = git(repo, "show", ":" + name)
                same = git(repo, "hash-object", "--path=" + name, name).strip() == git(repo, "rev-parse", ":" + name).strip()
                indexed_hash = hashlib.sha256(indexed).hexdigest()
            except subprocess.CalledProcessError:
                same, indexed_hash = False, None
            rows.append({"path": name, "worktree_sha256": hashlib.sha256(raw).hexdigest(), "indexed_sha256": indexed_hash,
                         "index_matches_with_git_filters": same, "business_identifiers_require_review": identifiers})
        staged = list(filter(None, git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")))
        staged_findings = [{"path": name, "rules": result} for name in staged if (result := rules(git(repo, "show", ":" + name), name)[0])]
        history_rules = rules(git(repo, "log", "--all", "-p", "--format=commit:%H"), "history")[0]
        selected = [row["path"] for row in rows]
        result = {"repo": label, "selected_files": rows, "excluded_paths": excluded, "candidate_secret_findings": findings,
                  "staged_secret_findings": staged_findings, "history_secret_rule_matches": history_rules,
                  "staged_outside_selection": [name for name in staged if name not in selected],
                  "head": git(repo, "rev-parse", "HEAD").decode().strip(),
                  "index_sha256": hashlib.sha256(git(repo, "ls-files", "--stage")).hexdigest(),
                  "git_index_mutated": False}
        (OUT / (label + "-inventory.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        (OUT / (label + "-include.txt")).write_text("\n".join(selected) + "\n", encoding="utf-8")
        summary[label] = {"selected": len(rows), "index_differs": sum(not r["index_matches_with_git_filters"] for r in rows),
                          "staged_outside_selection": len(result["staged_outside_selection"]),
                          "candidate_secret_findings": len(findings), "staged_secret_findings": len(staged_findings), "history_rules": history_rules}
    (OUT / "publication-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return int(any(item["candidate_secret_findings"] or item["staged_secret_findings"] or item["history_rules"] for item in summary.values()))


if __name__ == "__main__":
    raise SystemExit(main())
