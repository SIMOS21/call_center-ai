"""Verify hashes and source versions for reproducibility; no raw data committed."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from scripts.collect_real_sources import ABCD_REVISION
from app.config import env, path_env
out = {"created_at": datetime.now(timezone.utc).isoformat(), "files": []}
out["abcd_revision"] = ABCD_REVISION
out["source_urls"] = {
    "abcd": f"https://raw.githubusercontent.com/asappresearch/abcd/{ABCD_REVISION}/data/",
    "ebay": "NOT_COLLECTED_PERMISSION_REQUIRED",
    "olist": "NOT_IMPORTED",
}
for base in (Path("data/raw"), Path("data/knowledge")):
    if not base.is_dir():
        continue
    for file in sorted(base.rglob("*")):
        if file.is_file():
            h = hashlib.sha256()
            with file.open("rb") as f:
                for block in iter(lambda:f.read(1024*1024), b""):
                    h.update(block)
            out["files"].append({"path": str(file), "size_bytes": file.stat().st_size, "sha256": h.hexdigest()})
index = path_env("INDEX_FILE", "data/index.json")
if index.exists():
    payload = json.loads(index.read_text(encoding="utf-8"))
    out["index"] = {"path": str(index), "sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
                    "parameters": payload["parameters"], "backend": env("RAG_BACKEND", "lexical"), "top_k": 5,
                    "documents": payload["documents_count"], "chunks": len(payload["chunks"])}
out["retrieval_reader"] = {"document_grouping": env("RAG_DOCUMENT_GROUPING", "true"), "body_weight": .65, "title_weight": .35, "minimum_score": env("RAG_MIN_SCORE", "0.12")}
out["application_sha256"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path("app").glob("*.py"))}
out["frozen_final_sha256_only"] = hashlib.sha256(Path("evaluation/final-v3.jsonl").read_bytes()).hexdigest()
out["legacy_index_sha256"] = hashlib.sha256(Path("data/index.json").read_bytes()).hexdigest()
out["llm"] = {"model": env("LLM_MODEL"), "documentary_generation": "verified_fact_selection_only"}
olist_report = Path("reports/olist-import.json")
if olist_report.exists():
    out["olist"] = json.loads(olist_report.read_text(encoding="utf-8"))
    out["source_urls"]["olist"] = out["olist"]["source"]
out["embedding"] = {"model": env("EMBEDDING_MODEL"), "revision": env("EMBEDDING_REVISION")}
Path("reports").mkdir(exist_ok=True)
Path("reports/source_manifest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("Hashed", len(out["files"]), "files, see reports/source_manifest.json")
