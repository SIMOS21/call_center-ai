"""Read-only real Streamlit/HTTP/Medusa quantity regression, without approvals."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from streamlit.testing.v1 import AppTest

from app.config import env

OUT = Path("reports/pre-push/quantity-fix")
CASES = [
    "Je veux 2 Medusa Sweatshirts taille L.",
    "Je veux deux Medusa Sweatshirts taille L.",
    "Je veux deux sweatshirts taille L.",
    "Je veux un Medusa Sweatshirt taille L, quantité 2.",
]


def main(phase):
    base = env("COMMERCEOPS_API_URL", "http://127.0.0.1:8001").rstrip("/")
    assert urlparse(base).hostname in ("localhost", "127.0.0.1")
    assert urlparse(env("MEDUSA_URL", "http://localhost:9000")).hostname in ("localhost", "127.0.0.1")
    requests.get(base + "/health", timeout=20).raise_for_status()
    ui = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/ui.py"), default_timeout=120).run()
    next(b for b in ui.button if b.label == "Connexion au compte de test").click().run()
    assert ui.session_state.customer_jwt
    rows = []

    def reset():
        next(b for b in ui.button if b.label == "Nouvelle conversation").click().run()
        assert not ui.exception

    def ask(message, expected_quantity, expected_size="L"):
        ui.chat_input[0].set_value(message).run()
        assert not ui.exception
        item = ui.session_state.history[-1]
        assert item["role"] == "assistant"
        selected = item.get("product_selection")
        tools = ui.session_state.debug_data.get("used_tools", [])
        assert not ui.session_state.pending_actions and "prepare_cart" not in tools
        assert not ui.json
        passed = bool(selected and selected["quantity"] == expected_quantity and selected["variant"] == expected_size)
        rows.append({"message": message, "expected_quantity": expected_quantity, "expected_size": expected_size,
                     "observed_selection": selected, "answer": item["content"], "tools_called": tools,
                     "status": "PASS" if passed else "FAIL"})
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / ("streamlit-" + phase + ".json")).write_text(json.dumps({
            "phase": phase, "mode": "real_Streamlit_AppTest_HTTP_Medusa", "api": base,
            "approval_or_business_write_requests": 0, "visual_browser_inspection": "NOT_PERFORMED",
            "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(phase, len(rows), rows[-1]["status"], flush=True)

    for message in CASES:
        reset()
        ask(message, 2)
    if phase == "after":
        ask("Finalement, prends-en trois.", 3)
        ask("Non, plutôt la taille M.", 3, "M")
        ask("Quantité 2, pour un Medusa Sweatshirt taille L.", 2)
        ask("Je veux 4 Medusa Sweatshirts taille L, quantité 2.", 2)
    reset()
    if phase == "after":
        assert all(row["status"] == "PASS" for row in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("before", "after"))
    main(parser.parse_args().phase)
