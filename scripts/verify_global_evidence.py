"""Read-only checks of persisted acceptance evidence, source quotes and MLflow."""
import hashlib
import json
import re
import socket
import sqlite3
from pathlib import Path

import requests
from dotenv import dotenv_values

from app.config import env, path_env

OUT = Path("reports/pre-push/global")


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import mlflow
    from mlflow import MlflowClient

    live = json.loads((OUT / "live-scenarios.json").read_text(encoding="utf-8"))
    payload = json.loads(path_env("INDEX_FILE", "data/index.json").read_bytes())
    chunks = {c["id"]: c for c in payload["chunks"]}
    def clean(text):
        return " ".join(text.split())
    rows = []
    for scenario in live["rows"]:
        data = scenario["observed"]
        for unit in data.get("answer_units", []):
            evidences = unit.get("evidence", [])
            valid = bool(evidences) and all(
                any(chunk_id in chunks and clean(evidence["quote"]) in clean(chunks[chunk_id]["content"])
                    and chunks[chunk_id]["source"] in {source["source"] for source in data.get("sources", [])}
                    for chunk_id in evidence["chunk_ids"]) for evidence in evidences)
            rows.append({"scenario": scenario["scenario"], "assertion": unit["text"],
                         "fact_ids": unit["fact_ids"], "evidence": evidences,
                         "quotes_present_in_original_index_chunks": valid,
                         "status": "PASS" if valid else "FAIL"})
    save("documentary-grounding.json", {"method": "Each rendered unit mapped to original quoted passages; no human semantic score inferred",
         "index_sha256": hashlib.sha256(path_env("INDEX_FILE", "data/index.json").read_bytes()).hexdigest(),
         "rows": rows, "human_semantic_review": "PENDING"})
    assert rows and all(r["status"] == "PASS" for r in rows)

    values = []
    for file in (Path(".env"), Path("../my-medusa-store/apps/backend/.env"), Path("../my-medusa-store/apps/backend/.env.admin")):
        if file.exists():
            values.extend(value for key, value in dotenv_values(file).items()
                          if value and len(value) >= 8 and re.search(r"key|secret|password|token|database_url", key, re.I))
    for credential in json.loads(Path("data/demo-credentials.json").read_text()):
        values.extend(v for v in credential.values() if isinstance(v, str) and len(v) >= 8)
    rules = {"provider_token": re.compile(r"(?:nvapi-|gsk_|ghp_|github_pat_)[A-Za-z0-9_-]{20,}"),
             "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}"),
             "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
             "bearer": re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}")}
    mlflow.set_tracking_uri(env("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
    client = MlflowClient()
    experiment = client.get_experiment_by_name("commerceops-operations")
    traces = client.search_traces(locations=[experiment.experiment_id], max_results=50)
    findings, names, correlations = [], set(), []
    expected_ids = set(live["confirmation_request_ids"])
    for item in traces:
        trace = client.get_trace(item.info.trace_id)
        serialized = json.dumps(trace.to_dict(), ensure_ascii=False, default=str)
        findings.extend(name for name, pattern in rules.items() if pattern.search(serialized))
        if any(value in serialized for value in values):
            findings.append("known_local_credential")
        for span in trace.data.spans:
            names.add(span.name)
            attributes = span.attributes
            if span.name == "tool.action_confirmation" and attributes.get("request_id") in expected_ids:
                correlations.append({"request_id": attributes["request_id"], "span_name": span.name,
                                     "approval_status": attributes.get("approval_status"),
                                     "write_completed": attributes.get("write_completed"),
                                     "child_span_count": len(trace.data.spans) - 1,
                                     "privacy": attributes.get("privacy")})
    save("trace-privacy.json", {"traces_read": len(traces), "findings": sorted(set(findings)), "span_names": sorted(names),
         "confirmation_correlations": correlations, "status": "PASS" if not findings and len(correlations) == len(expected_ids) else "FAIL",
         "scope": "Latest 50 persisted traces; no raw trace contents or trace identifiers exported"})
    assert not findings and len(correlations) == len(expected_ids)

    health = {}
    for name, url in {"api": "http://127.0.0.1:8001/health", "streamlit": "http://127.0.0.1:8501/_stcore/health",
                      "medusa": "http://127.0.0.1:9000/health", "mlflow": "http://127.0.0.1:5000/health"}.items():
        response = requests.get(url, timeout=15)
        health[name] = {"http_status": response.status_code, "reachable": response.ok}
    for name, port in (("postgresql", 5433), ("redis", 6380)):
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            health[name] = {"tcp_reachable": True, "port": port}
    save("services-health.json", health)
    checkpoint = json.loads(Path("data/runtime/global-live-checkpoint.json").read_text(encoding="utf-8"))
    with sqlite3.connect(path_env("DB_FILE", "data/commerceops.sqlite3").resolve().as_uri() + "?mode=ro", uri=True) as database:
        session = checkpoint["session_id"]
        approvals = database.execute("SELECT a.kind,a.status,a.customer_id=s.customer_id FROM approvals a JOIN chat_approvals c ON a.id=c.approval_id JOIN chat_sessions s ON c.session_id=s.id WHERE c.session_id=?", (session,)).fetchall()
        results = [json.loads(row[0]) for row in database.execute("SELECT r.references_json FROM chat_action_results r JOIN chat_approvals c ON c.approval_id=r.approval_id WHERE c.session_id=?", (session,))]
        state, history = database.execute("SELECT state_json,history_json FROM chat_sessions WHERE id=?", (session,)).fetchone()
        links = database.execute("SELECT count(*) FROM chat_session_carts WHERE session_id=?", (session,)).fetchone()[0]
        locks = database.execute("SELECT count(*) FROM cart_action_locks WHERE cart_id=?", (checkpoint["cart_id"],)).fetchone()[0]
    passed = (len(approvals) == 3 and sorted(a[1] for a in approvals) == ["cancelled", "done", "done"]
              and all(a[2] for a in approvals) and len(results) == 2
              and all(r.get("cart_id") == checkpoint["cart_id"] for r in results)
              and not links and not locks and not json.loads(state)["draft_items"] and not json.loads(history))
    save("sqlite-acceptance.json", {"approvals": [{"kind": a[0], "status": a[1], "matches_session_owner": bool(a[2])} for a in approvals],
         "confirmed_results_link_same_cart": all(r.get("cart_id") == checkpoint["cart_id"] for r in results),
         "session_cart_links_after_reset": links, "cart_locks_after_done": locks,
         "draft_and_history_empty_after_reset": not json.loads(state)["draft_items"] and not json.loads(history),
         "status": "PASS" if passed else "FAIL"})
    assert passed
    print("Original source quote checks", len(rows), "PASS; trace privacy and two HTTP confirmations correlated; services reachable")


if __name__ == "__main__":
    main()
