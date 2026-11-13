from contextlib import nullcontext

import httpx

from app import rag
from app.agent import Agent


def test_french_explanation_and_citation_not_chunk_dump(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("LLM_API_KEY", "offline-test")
    monkeypatch.setattr("app.agent.sanitized_tool_span", lambda *a: nullcontext(None))
    row = {"id": "test", "title": "ABCD couleur", "source": "https://example.test/reference", "content": "Action: Validate Purchase"}
    monkeypatch.setattr(rag, "search", lambda *a: [row])
    sent = []
    def post(client, url, **kwargs):
        sent.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={"choices": [{"message": {"content": '{"fact_ids":["purchase"],"invented":"remboursement garanti"}'}}]})
    monkeypatch.setattr(httpx.Client, "post", post)
    result = Agent().respond("Quelle procédure ABCD pour une mauvaise couleur ?")
    assert "vérifier l'achat" in result["answer"] and "remboursement garanti" not in result["answer"]
    assert row["source"] in result["answer"] and "pas les politiques officielles de Medusa" in result["answer"]
    assert result["generation"] == "nvidia_verified_fact_selection"
    assert result["evidence"][0]["quote"] in row["content"]
    assert result["pending_actions"] == [] and "tools" not in sent[0]


def test_documentary_provider_failure_has_honest_fallback(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "offline-test")
    def unavailable(*a, **kw):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.Client, "post", unavailable)
    from app.documentary import choose_facts
    ids, mode, usage = choose_facts(Agent(), "Quelle politique ?", [{"id": "purchase", "text": "Vérification de l'achat", "quote": "Action: Validate Purchase", "chunk_ids": ["test"]}])
    assert ids == ["purchase"] and mode == "verified_fact_fallback" and usage is None
