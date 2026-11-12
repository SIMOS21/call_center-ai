import json
from pathlib import Path
import httpx
out = {}
for name, url in {"api": "http://127.0.0.1:8001/health", "ui": "http://127.0.0.1:8501/_stcore/health", "medusa": "http://127.0.0.1:9000/health", "mlflow": "http://127.0.0.1:5000/health"}.items():
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    out[name] = {"status_code": response.status_code, "body": response.text[:500]}
for query in ["return stained product", "Je souhaite un retour pour une mauvaise couleur", "astrophysics quasar gravitational"]:
    response = httpx.post("http://127.0.0.1:8001/knowledge/search", json={"question": query}, timeout=30)
    response.raise_for_status()
    rows = response.json().get("results", [])
    out[query] = {"status_code": response.status_code, "results": len(rows), "sources": [r["source"] for r in rows]}
health = json.loads(out["api"]["body"])
ready = health.get("api") == "ok" and all(health.get(key) for key in ("medusa_reachable", "index_available", "llm_configured"))
out["readiness"] = "READY" if ready else "PARTIAL"
Path("reports/http-smoke.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
raise SystemExit(0 if ready else 1)
