"""Real Streamlit/FastAPI/Medusa regression dialogue on authorized demo fixtures."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from streamlit.testing.v1 import AppTest

from app.config import env, path_env
from app.medusa import Medusa

OUT = Path("reports/pre-push/conversation-final")
POLICY = "Votre boutique garantit-elle officiellement tous les appareils électroniques pendant 36 mois ?"
CHANGE = "Je veux deux sweatshirts taille M. Finalement, je préfère la taille L."
CANCEL = "Je ne veux plus ajouter cet article. Annule la préparation du panier."


def button(ui, label):
    return next(item for item in ui.button if item.label == label)


def main(phase):
    assert urlparse(env("MEDUSA_URL")).hostname in ("localhost", "127.0.0.1")
    credentials = json.loads(path_env("DEMO_CREDENTIALS", "data/demo-credentials.json").read_text(encoding="utf-8"))
    assert len(credentials) == 2 and all(c["email"].split("@")[-1].endswith((".test", ".local", ".invalid")) for c in credentials)
    base = env("COMMERCEOPS_API_URL", "http://127.0.0.1:8001")
    ui = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/ui.py"), default_timeout=180).run()
    button(ui, "Connexion au compte de test").click().run()
    headers = {"Authorization": "Bearer " + ui.session_state.customer_jwt}
    medusa = Medusa()
    before_orders = {o["id"] for o in medusa.customer_orders(ui.session_state.customer_jwt)}
    report = {"phase": phase, "ui_checks": "Streamlit AppTest with actual HTTP services, structural checks", "dialogue": []}
    def ask(question):
        ui.chat_input[0].set_value(question).run()
        assert not ui.exception
        item = ui.session_state.history[-1]
        assert item["role"] == "assistant"
        report["dialogue"].append({"question": question, "answer": item["content"],
                                  "selection": item.get("product_selection"),
                                  "generation": ui.session_state.debug_data.get("generation"),
                                  "used_tools": ui.session_state.debug_data.get("used_tools")})
        return item
    ask(POLICY)
    if phase == "after":
        assert "search_knowledge" in ui.session_state.debug_data["used_tools"]
        assert "source" in report["dialogue"][-1]["answer"].lower()
        assert "modèle de langage" not in report["dialogue"][-1]["answer"]
    button(ui, "Nouvelle conversation").click().run()
    selection = ask(CHANGE).get("product_selection")
    if phase == "after":
        assert selection["variant"] == "L" and selection["quantity"] == 2
        ask("Finalement, prends-en trois.")
        selected = ask("Non, plutôt la taille M.")["product_selection"]
        assert selected["variant"] == "M" and selected["quantity"] == 3
        ask("Finalement, prends-en deux.")
    ask("Oui")
    pending = ui.session_state.pending_actions[0]
    session = ui.session_state.session_id
    ask(CANCEL)
    status = requests.get(base + "/actions/" + pending["approval_id"], headers=headers, timeout=20)
    status.raise_for_status()
    report["cancelled_approval_status"] = status.json()["status"]
    if phase == "before":
        if status.json()["status"] == "pending":
            requests.post(base + "/actions/cancel", json={"approval_id": pending["approval_id"], "session_id": session}, headers=headers, timeout=20).raise_for_status()
    else:
        assert status.json()["status"] == "cancelled" and not ui.session_state.pending_actions
        refused = requests.post(base + "/actions/confirm", json={"approval_id": pending["approval_id"], "session_id": session, "confirm": True}, headers=headers, timeout=20)
        assert refused.status_code == 409
        report["cancelled_confirmation_http"] = refused.status_code
        button(ui, "Nouvelle conversation").click().run()
        ask("Je veux trois sweatshirts taille M.")
        ask("Non, plutôt la taille L.")
        ask("Finalement, prends-en deux.")
        ask("Oui")
        assert button(ui, "Confirmer").disabled
        ui.checkbox(key="confirm_action").check().run()
        button(ui, "Confirmer").click().run()
        assert not ui.exception and ui.session_state.action_feedback
        cart = requests.get(base + "/sessions/" + ui.session_state.session_id + "/cart", headers=headers, timeout=30)
        cart.raise_for_status()
        item = cart.json()["cart"]["items"][0]
        assert item["variant_title"] == "L" and item["quantity"] == 2
        report["confirmed_cart"] = {k: item[k] for k in ("product_title", "variant_title", "quantity")}
        ask("Que contient mon panier ?")
        assert "get_cart" in ui.session_state.debug_data["used_tools"]
        ask("Annule ma dernière demande.")
        assert not ui.success and "supprim" not in ui.session_state.history[-1]["content"].lower()
        report["stale_success_cleared"] = True
        assert requests.get(base + "/sessions/" + ui.session_state.session_id + "/cart", headers=headers, timeout=30).ok
        report["created_cart_still_readable"] = True
    report["orders_unchanged"] = before_orders == {o["id"] for o in medusa.customer_orders(ui.session_state.customer_jwt)}
    assert report["orders_unchanged"]
    assert not ui.json
    report.update(demo_cart_writes=1 if phase == "after" else 0, orders_or_refunds_requested=0)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / (phase + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(phase, "dialogue saved", len(report["dialogue"]), "turns")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("before", "after", "clean"))
    phase = parser.parse_args().phase
    if phase == "clean":
        from scripts import verify_pre_push_v2
        OUT.mkdir(parents=True, exist_ok=True)
        verify_pre_push_v2.OUT = OUT.resolve()
        raise SystemExit(verify_pre_push_v2.clean())
    main(phase)
