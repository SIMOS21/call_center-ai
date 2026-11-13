"""Public live dialogue evidence; no commerce write or frozen evaluation access."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import env, path_env

QUESTIONS = [
    "J'ai reçu mon sweatshirt dans la mauvaise couleur. Comment puis-je le retourner ?",
    "Peux-tu résumer cette procédure en trois étapes ?",
    "Fais plus court, s'il te plaît.",
    "Donne une explication détaillée de cette procédure et précise ce qui reste inconnu.",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()
    folder = Path("reports/rag-format")
    folder.mkdir(exist_ok=True)
    output = folder / (args.phase + ".json")
    if output.exists():
        raise SystemExit("Evidence exists; preserve before/after files instead of overwriting")
    credentials = json.loads(path_env("DEMO_CREDENTIALS", "data/demo-credentials.json").read_text(encoding="utf-8"))[0]
    login = requests.post(env("MEDUSA_URL") + "/auth/customer/emailpass", json=credentials, timeout=20)
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["token"]}
    base = env("COMMERCEOPS_API_URL", "http://127.0.0.1:8001")
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "phase": args.phase,
              "split": "public_development_dialogue_not_independent", "commerce_write": False, "turns": []}
    session = None
    for question in QUESTIONS[:2] if args.phase == "before" else QUESTIONS:
        body = {"message": question}
        if session:
            body["session_id"] = session
        response = requests.post(base + "/chat", json=body, headers=headers, timeout=100)
        response.raise_for_status()
        data = response.json()
        session = data["session_id"]
        report["turns"].append({"question": question, **{k: data.get(k) for k in ("answer", "generation", "composition", "presentation_format", "answer_units", "evidence", "sources", "used_tools", "usage", "missing_information", "latency_ms")}})
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    reset = requests.delete(base + "/sessions/" + session, headers=headers, timeout=20)
    reset.raise_for_status()
    if args.phase == "after":
        summary = report["turns"][1]
        assert summary["presentation_format"]["provided_steps"] == 3
        assert len(summary["answer_units"]) == 3
        assert all(str(n) + ". " in summary["answer"] for n in (1, 2, 3))
        assert "étiquette" in summary["answer"] and "dépôt" in summary["answer"]
        assert report["turns"][2]["presentation_format"]["mode"] == "short"
        assert report["turns"][3]["presentation_format"]["mode"] == "detailed"
    print("Live dialogue saved:", output)


if __name__ == "__main__":
    main()
