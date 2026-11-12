"""Authorized NVIDIA demo: public corpus/catalog and local test IDs/statuses only.

JWTs, passwords, addresses and tracking data never enter model messages.
Creates one test cart after explicit API confirmation; no financial payment.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from app.config import env
from app.medusa import Medusa


def main():
    api = httpx.Client(base_url="http://127.0.0.1:8001", timeout=180)
    assert api.get("/health").json()["llm_configured"]
    credentials = json.loads(Path("data/demo-credentials.json").read_text())
    auth = httpx.post(env("MEDUSA_URL") + "/auth/customer/emailpass", json=credentials[0], timeout=30)
    auth.raise_for_status()
    token = auth.json()["token"]
    headers = {"Authorization": "Bearer " + token}
    medusa = Medusa()
    variant = medusa.products()["products"][0]["variants"][0]["id"]
    order = json.loads(Path("reports/medusa-smoke.json").read_text())["order_id"]
    cases = [
        ("rag", "Recherche dans les consignes ABCD comment retourner un produit reçu dans une mauvaise couleur. Cite la vraie source et distingue cette référence des règles de notre boutique.", "search_knowledge"),
        ("catalogue", "Quels produits sont disponibles dans notre boutique ? Consulte le catalogue réel.", "search_products"),
        ("suivi", f"Quel est le statut de ma commande {order} ? Consulte Medusa.", "get_order_status"),
        ("panier", f"Je souhaite un panier avec une unité de la variante {variant}. Prépare la demande de confirmation sans finaliser de commande.", "prepare_cart"),
    ]
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "provider": "NVIDIA", "model": env("LLM_MODEL"), "cases": []}
    def save():
        Path("reports/agent-live.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, prompt, expected in cases:
        start = time.perf_counter()
        response = api.post("/chat", json={"message": prompt}, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"{name}: HTTP {response.status_code}; {response.json().get('detail', 'error')}")
        result = response.json()
        row = {"scenario": name, "expected_tool": expected, "used_tools": result["used_tools"], "tool_calls": result["tool_calls"], "request_id": result["request_id"], "answer": result["answer"], "latency_ms": (time.perf_counter()-start)*1000, "selection_correct": expected in result["used_tools"], "escalation": result.get("escalation_recommended", False)}
        report["cases"].append(row)
        save()
        print(name, row["used_tools"], round(row["latency_ms"]), "ms")
        assert row["selection_correct"], f"Wrong tool for {name}"
        if name == "panier":
            approval = result["pending_actions"][0]["approval_id"]
            waiting = api.post("/actions/confirm", json={"approval_id": approval, "confirm": False}, headers=headers)
            assert waiting.json()["status"] == "awaiting_customer_confirmation"
            confirmed = api.post("/actions/confirm", json={"approval_id": approval, "confirm": True}, headers=headers)
            assert confirmed.status_code == 200 and confirmed.json()["status"] == "done"
            cart_id = confirmed.json()["result"]["cart_id"]
            medusa.owned_cart(cart_id, token)
            repeat = api.post("/actions/confirm", json={"approval_id": approval, "confirm": True}, headers=headers)
            assert repeat.status_code == 409
            report.update(confirmed_cart_id=cart_id, repeat_confirmation_status=409)
    n = len(report["cases"])
    report["metrics"] = {"n_scenarios": n, "tool_selection_accuracy": sum(r["selection_correct"] for r in report["cases"])/n, "mean_tool_calls": sum(r["tool_calls"] for r in report["cases"])/n, "mean_latency_ms": sum(r["latency_ms"] for r in report["cases"])/n}
    report["limitation"] = "Four guided development scenarios, not an independent benchmark. Checkout tested separately. Authorized return and token/cost metrics not evaluated."
    save()
    import mlflow
    mlflow.set_tracking_uri(env("MLFLOW_TRACKING_URI"))
    mlflow.set_experiment("commerceops-agent-live")
    with mlflow.start_run(run_name="nvidia-four-scenarios") as run:
        mlflow.log_params({"provider": "NVIDIA", "model": env("LLM_MODEL"), "scenarios": "guided_development"})
        mlflow.log_metrics(report["metrics"])
        mlflow.log_artifact("reports/agent-live.json")
        report["mlflow_run_id"] = run.info.run_id
    save()
    print("REAL AGENT DEMO PASS", report["metrics"])


if __name__ == "__main__":
    main()
