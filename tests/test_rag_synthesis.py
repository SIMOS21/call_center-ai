"""Public source excerpts, independent of the frozen final question set."""
import json
import re
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from app import api as application
from app import documentary, rag
from app.agent import Agent
from app.documentary_format import compose, requested_format

# Exact excerpts read from ABCD Return Due to Color; fixture, not an imported doc.
EXCERPTS = [
    "Action: Validate Purchase Confirm that their purchase is valid with [Validate Purchase] Action: Membership Privileges Confirm their order can be returned, by checking their membership level.",
    "If the customer can return, tell them the good news and go to the next step If the customer cannot return, apologize and explain the problem. Then [End Conversation] Action: Enter Details Since the customer will print out a shipping label for the return, you need their full address.",
    "Action: Update Order Ask the customer how they would like to process their return: Options include: 'By Mail', 'In Store', or 'Drop off Center' Fill in the form with one of these three values and submit to [Update Order]",
]


@pytest.fixture
def row():
    return {"id": "eligibility", "title": "ABCD: Product Defect / Return Due to Color", "source": "https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json#flow=Product Defect&subflow=Return Due to Color", "document_sha256": "fixture-source-v1", "content": "\n".join(EXCERPTS), "chunks": [{"id": str(n), "content": t} for n, t in enumerate(EXCERPTS)]}


@pytest.fixture
def dialogue(monkeypatch, tmp_path, row):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "state.sqlite3"))
    monkeypatch.setattr(application.medusa, "customer", lambda token: {"id": token})
    monkeypatch.setattr("app.agent.sanitized_tool_span", lambda *a: nullcontext(None))
    monkeypatch.setattr(rag, "search", lambda q: [row])
    client = TestClient(application.api)
    def chat(message, session=None, owner="A"):
        body = {"message": message}
        if session:
            body["session_id"] = session
        return client.post("/chat", json=body, headers={"Authorization": "Bearer " + owner})
    return chat


def test_exact_reported_dialogue_keeps_request_and_three_concrete_steps(dialogue, row):
    first = dialogue("J'ai reçu mon sweatshirt dans la mauvaise couleur. Comment puis-je le retourner ?").json()
    second = dialogue("Peux-tu résumer cette procédure en trois étapes ?", first["session_id"]).json()
    assert first["answer"] != second["answer"]
    assert second["presentation_format"] == {"mode": "steps", "requested_steps": 3, "provided_steps": 3}
    assert len(re.findall(r"^\d\. ", second["answer"], re.M)) == 3
    units = second["answer_units"]
    assert units[0]["fact_ids"] == ["purchase", "eligibility"]
    assert "niveau d'adhésion" in units[0]["text"]
    assert units[1]["fact_ids"] == ["return_accepted", "return_label"]
    assert units[1]["text"].startswith("Si le retour est accepté") and "étiquette" in units[1]["text"]
    assert "imprimer" in units[1]["text"] and "adresse complète" in units[1]["text"]
    assert "ABCD" in units[2]["text"] and "magasin" in units[2]["text"] and "dépôt" in units[2]["text"]
    assert "pas les politiques officielles" in second["answer"]
    assert "ne confirment ni votre éligibilité" in second["answer"]
    assert not second["pending_actions"] and second["used_tools"] == ["search_knowledge"]
    for unit in units:
        for evidence in unit["evidence"]:
            assert evidence["quote"] in row["content"]
            assert any(evidence["quote"] in c["content"] for c in row["chunks"] if c["id"] in evidence["chunk_ids"])
    assert not re.search(r"\b(30|90|6)\b|jours|mois|remboursement garanti", second["answer"])


@pytest.mark.parametrize("wording,count", [("En deux points, s'il te plaît", 2), ("Décris cette procédure en 3 étapes", 3), ("Résume-la en quatre étapes", 4)])
def test_other_step_requests_not_from_final(dialogue, wording, count):
    first = dialogue("Comment retourner un vêtement reçu dans la mauvaise couleur ?").json()
    second = dialogue(wording, first["session_id"]).json()
    assert second["presentation_format"]["provided_steps"] == count
    assert len(second["answer_units"]) == count


def test_short_detailed_and_one_sentence(dialogue):
    first = dialogue("Comment retourner un article de couleur incorrecte ?").json()
    short = dialogue("Fais plus court", first["session_id"]).json()
    detailed = dialogue("Donne une explication détaillée de cette procédure", first["session_id"]).json()
    assert short["presentation_format"]["mode"] == "short"
    assert detailed["presentation_format"]["mode"] == "detailed"
    assert len(short["answer"]) < len(first["answer"]) < len(detailed["answer"])
    assert "Si le retour est refusé" in detailed["answer"]
    facts = documentary.supported_facts({"id": "a", "title": "ABCD", "content": " ".join(EXCERPTS)})
    body = compose("Résume cette procédure en une phrase", facts)["body"]
    assert body.count(".") == 1


def test_source_without_shipping_cannot_invent_three_steps(dialogue, row):
    row["content"] = EXCERPTS[0]
    row["chunks"] = [{"id": "0", "content": EXCERPTS[0]}]
    result = dialogue("Comment retourner ce produit ? Résume en trois étapes.").json()
    assert len(result["answer_units"]) == 2
    assert "pas 3" in result["answer"] and "ne précisent pas comment préparer l'étiquette" in result["answer"]
    assert "envoi postal" not in result["answer"] and "en magasin" not in result["answer"]


def test_changed_reference_is_not_reused(dialogue, row):
    first = dialogue("Quelle procédure pour une mauvaise couleur ?").json()
    row["document_sha256"] = "changed"
    second = dialogue("Résume cette procédure en trois étapes", first["session_id"]).json()
    assert second["abstained"] and not second["answer_units"]
    assert "n'est plus disponible à l'identique" in second["answer"]


def test_missing_acceptance_condition_is_not_inferred(dialogue, row):
    condition = "If the customer can return, tell them the good news and go to the next step"
    row["chunks"][1]["content"] = row["chunks"][1]["content"].replace(condition, "")
    result = dialogue("Explique la procédure de retour en trois étapes").json()
    assert "passage reliant l'acceptation" in result["answer"]
    assert not any("return_label" in u["fact_ids"] for u in result["answer_units"])
    assert result["presentation_format"]["provided_steps"] == 2


def test_other_customer_cannot_reuse_documentary_context(dialogue):
    first = dialogue("Quelle procédure pour une mauvaise couleur ?").json()
    assert dialogue("Résume en trois étapes", first["session_id"], "B").status_code == 404


def test_selection_does_not_erase_format_or_operational_dependencies(monkeypatch, tmp_path, row):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setattr(rag, "search", lambda q: [row])
    monkeypatch.setattr("app.agent.sanitized_tool_span", lambda *a: nullcontext(None))
    # Mimic the exact former selector bias; format/render must still cover shipping.
    monkeypatch.setattr(documentary, "choose_facts", lambda *a: (["purchase", "eligibility"], "verified_fact_fallback", None))
    result = Agent().respond("Quelle procédure de retour ? En trois étapes.")
    assert len(result["answer_units"]) == 3
    assert "étiquette" in result["answer"] and "dépôt" in result["answer"]


def test_format_with_a_different_document_and_topic_change(dialogue, monkeypatch, row):
    first = dialogue("Quelle procédure pour une mauvaise couleur ?").json()
    card_text = "Instruct the customer to try entering their credit card information again. Instruct the customer to log out of their account and log back in. Have the customer check the expiration date, maybe the credit card is too old."
    card = {"id": "card", "source": "https://example.test/abcd#subflow=Invalid%20Credit%20Card", "title": "ABCD: Troubleshoot Site / Invalid Credit Card", "document_sha256": "card-v1", "content": card_text}
    monkeypatch.setattr(rag, "search", lambda q: [card])
    second = dialogue("Résume les vérifications pour une carte refusée en trois points.", first["session_id"]).json()
    assert len(second["answer_units"]) == 3 and not second["abstained"]
    assert second["sources"][0]["title"].endswith("Invalid Credit Card")
    assert "reconnecter" in second["answer"] and "magasin" not in second["answer"]
    assert "Return Due to Color" not in second["answer"]


def test_empty_source_and_over_requested_steps(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setattr("app.agent.sanitized_tool_span", lambda *a: nullcontext(None))
    monkeypatch.setattr(rag, "search", lambda q: [])
    result = Agent().respond("Quelle procédure de retour ? En trois étapes.")
    assert result["abstained"] and "aucun passage" in result["answer"]
    assert not result["answer_units"] and result["missing_information"]
    assert requested_format("Résume en 100 étapes")["requested_steps"] == 100
