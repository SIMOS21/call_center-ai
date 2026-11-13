"""Public development diagnostics only; never reads frozen final questions."""
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

from app import storage

CASES = [
    ("D01", "J'ai commandé un vêtement rouge mais j'ai reçu le bleu. Quelle procédure de support dois-je suivre ?", "Return Due to Color"),
    ("D02", "Mon colis est arrivé, mais il manque un des articles que j'avais achetés. Comment signaler ce problème ?", "Missing Item"),
    ("D03", "Je connais mon mot de passe, mais j'ai oublié mon identifiant utilisateur. Comment récupérer mon accès ?", "Recover Username"),
    ("D04", "Le site refuse ma carte lorsque j'essaie de payer. Quelles vérifications puis-je faire ?", "Invalid Credit Card"),
]


def main():
    destination = Path("reports/global-v2")
    destination.mkdir(exist_ok=True)
    def inspect(case):
        name, question, expected = case
        search = requests.post("http://127.0.0.1:8001/knowledge/search", json={"question": question}, timeout=90)
        chat = requests.post("http://127.0.0.1:8001/chat", json={"message": question}, timeout=360)
        result = {"id": name, "question": question, "expected_subflow_hypothesis": expected,
                  "search_http": search.status_code, "chat_http": chat.status_code}
        result["candidates"] = [{"rank": n, **{k: row.get(k) for k in ("id", "title", "source", "score")}} for n, row in enumerate(search.json().get("results", []), 1)]
        data = chat.json()
        result["chat"] = {k: data.get(k) for k in ("answer", "request_id", "used_tools", "generation", "source_checked", "latency_ms")}
        with storage.conn() as cx:
            result["audit"] = [dict(r) for r in cx.execute("SELECT tool_name,success,duration_ms,error_type FROM audit_events WHERE request_id=?", (data.get("request_id"),))]
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(inspect, CASES))
    status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "split": "development_seen_diagnostic",
              "local_changes": status, "cases": rows,
              "protected_final_sha256": hashlib.sha256(Path("evaluation/final-v3.jsonl").read_bytes()).hexdigest(),
              "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path("app/rag.py"), Path("app/agent.py"), Path("app/conversations.py"), Path("app/api.py"), Path("app/medusa.py"), Path("app/ui.py")]}}
    (destination / "diagnostic-before.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Diagnostic saved", [(r["id"], r["search_http"], r["chat_http"], r["chat"]["used_tools"]) for r in rows])


if __name__ == "__main__":
    main()
