"""Real UI/API/RAG/NVIDIA/Medusa, one explicitly confirmed local demo cart."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from streamlit.testing.v1 import AppTest

from app.config import env, path_env
from app.medusa import BackendError, Medusa
from scripts.diagnose_v2 import CASES
from scripts.evaluate_global_v2 import DEVELOPMENT


def button(ui, label):
    return next(b for b in ui.button if b.label == label)


def check_ui(ui):
    assert not ui.exception
    assert not ui.json, "No technical JSON may be visible in customer mode"
    assert not any("appr_" in m.value or "cart_" in m.value or "variant_" in m.value for m in ui.markdown)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--documentary", action="store_true")
    args = parser.parse_args()
    if not args.execute_live:
        parser.error("Explicit --execute-live required: creates one local demonstration cart, no order")
    if urlparse(env("MEDUSA_URL")).hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError("Local demonstration Medusa required")
    base = env("COMMERCEOPS_API_URL", "http://127.0.0.1:8001")
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "harness": "Actual Streamlit via AppTest, actual HTTP FastAPI/Medusa, no mocks; browser visual/manual validation not performed"}
    output = Path("reports/global-v2/live.json")
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        stamp = previous["timestamp_utc"].replace(":", "-")
        output.with_name("live-" + stamp + ".json").write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")
    def checkpoint():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ui = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/ui.py"), default_timeout=150).run()
    button(ui, "Connexion au compte de test").click().run()
    check_ui(ui)
    token = ui.session_state["customer_jwt"]
    headers = {"Authorization": "Bearer " + token}
    medusa = Medusa()
    orders_before = {o["id"] for o in medusa.customer_orders(token)}
    ui.chat_input[0].set_value("Je souhaite un Medusa Sweatshirt taille M").run()
    ui.chat_input[0].set_value("Oui").run()
    check_ui(ui)
    cancelled = ui.session_state["pending_actions"][0]["approval_id"]
    button(ui, "Annuler").click().run()
    check_ui(ui)
    status = requests.get(f"{base}/actions/{cancelled}", headers=headers, timeout=20).json()["status"]
    assert status == "cancelled"
    report["cancel_before_execution"] = status
    ui.chat_input[0].set_value("Medusa Sweatshirt taille M").run()
    ui.chat_input[0].set_value("Oui").run()
    check_ui(ui)
    session = ui.session_state["session_id"]
    action = ui.session_state["pending_actions"][0]
    assert action["details"]["variant"] == "M"
    assert button(ui, "Confirmer").disabled
    report["pending"] = {"approval_id": action["approval_id"], "kind": action["kind"], "arguments": action["arguments"], "details": action["details"], "no_json_in_customer_ui": True, "button_disabled_without_explicit_checkbox": True}
    ui.checkbox(key="confirm_action").check().run()
    button(ui, "Confirmer").click().run()
    check_ui(ui)
    assert "panier a été créé" in ui.session_state["action_feedback"]
    cart = ui.session_state["cart_view"]
    assert cart and cart["items"]
    assert any(i["variant_id"] == action["arguments"]["variant_id"] and i["quantity"] == 1 for i in cart["items"])
    medusa.get_cart(cart["cart_id"], token)  # Repeat real ownership check, read-only.
    report["confirmed"] = {"cart_id": cart["cart_id"], "actual_total": cart.get("total"), "currency_code": cart.get("currency_code"), "status": cart["status"], "exact_variant_and_quantity_verified": True}
    ui.chat_input[0].set_value("Quels articles ai-je actuellement dans mon panier ?").run()
    check_ui(ui)
    assert ui.session_state["debug_data"]["used_tools"] == ["get_cart"]
    report["cart_answer"] = ui.session_state["history"][-1]["content"]
    assert "Medusa Sweatshirt" in report["cart_answer"] and "Mémoire serveur" not in report["cart_answer"]
    body = {"approval_id": action["approval_id"], "session_id": session, "confirm": True}
    twice = requests.post(f"{base}/actions/confirm", json=body, headers=headers, timeout=20)
    assert twice.status_code == 409
    report["double_confirmation_http"] = twice.status_code
    credentials = json.loads(path_env("DEMO_CREDENTIALS", "data/demo-credentials.json").read_text(encoding="utf-8"))[1]
    auth = requests.post(env("MEDUSA_URL") + "/auth/customer/emailpass", json=credentials, timeout=20)
    auth.raise_for_status()
    foreign = auth.json()["token"]
    denied = requests.get(f"{base}/sessions/{session}/cart", headers={"Authorization": "Bearer " + foreign}, timeout=20)
    assert denied.status_code == 404
    try:
        medusa.get_cart(cart["cart_id"], foreign)
        raise AssertionError("Foreign cart readable")
    except BackendError:
        pass
    report["other_customer_session_cart_http"] = denied.status_code
    report["direct_foreign_cart_connector_denied"] = True
    report["documentary"] = []
    report["result"] = "IN_PROGRESS"
    checkpoint()
    if args.documentary:
        for case in [CASES[0], CASES[2], DEVELOPMENT[4], DEVELOPMENT[7]]:
            ui.chat_input[0].set_value(case[1]).run()
            check_ui(ui)
            answer = ui.session_state["history"][-1]["content"]
            debug = ui.session_state["debug_data"]
            report["documentary"].append({"id": case[0], "question": case[1], "answer": answer, "generation": debug["generation"], "usage": debug.get("usage"), "source_found": debug["source_found"], "source_relevant": debug["source_relevant"], "source_supports_answer": debug["source_supports_answer"]})
            checkpoint()
            assert case[2] in answer and "Source : [" in answer and "%20" in answer
            assert debug["source_supports_answer"]
        ui.chat_input[0].set_value("Quelle est la garantie officielle de 36 mois de votre boutique sur les drones ?").run()
        check_ui(ui)
        assert not ui.session_state["debug_data"]["source_supports_answer"]
        ui.chat_input[0].set_value("Peux-tu résumer en trois étapes la procédure que tu viens de consulter ?").run()
        check_ui(ui)
        report["missing_source_followup"] = ui.session_state["history"][-1]["content"]
        assert "Aucune procédure pertinente" in report["missing_source_followup"]
    after = {o["id"] for o in medusa.customer_orders(token)}
    assert after == orders_before
    report["new_orders_created"] = 0
    button(ui, "Nouvelle conversation").click().run()
    check_ui(ui)
    missing = requests.get(f"{base}/sessions/{session}/cart", headers=headers, timeout=20)
    assert missing.status_code == 404
    report["cart_link_cleared_on_reset_http"] = missing.status_code
    report["human_fidelity"] = {"status": "NOT_EVALUATED", "n": 0}
    report["result"] = "PASS"
    checkpoint()
    print("PASS: real customer UI/API/Medusa cart, owner checks, reset; public RAG/NVIDIA questions:", len(report["documentary"]))


if __name__ == "__main__":
    main()
