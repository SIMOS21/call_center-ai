"""Approval invariants and ambiguous writes, using isolated safe fixtures."""
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient

from app import api, conversations, storage
from app.medusa import BackendError, BusinessOutcomeUnknown, Medusa


@pytest.fixture
def approval(monkeypatch):
    monkeypatch.setattr("app.agent.sanitized_tool_span", lambda *a: nullcontext(None))
    monkeypatch.setattr(api.medusa, "customer", lambda token: {"id": token})
    product = {"id": "prod_test", "title": "Medusa Sweatshirt", "variants": [{
        "id": "variant_test", "title": "M", "options": [{"id": "opt_size", "value": "M"}],
        "calculated_price": {"calculated_amount": 30, "currency_code": "eur"}}]}
    catalog = [product]
    monkeypatch.setattr(api.medusa, "products", lambda *a, **kw: {"products": catalog})
    writes = []
    monkeypatch.setattr(api.medusa, "create_cart", lambda *a: writes.append(a) or {"cart_id": "cart_fixture"})
    client = TestClient(api.api)
    headers = {"Authorization": "Bearer A"}
    session = client.post("/chat", json={"message": "Medusa Sweatshirt taille M"}, headers=headers).json()["session_id"]
    action = client.post("/chat", json={"message": "oui", "session_id": session}, headers=headers).json()["pending_actions"][0]
    return client, {"approval_id": action["approval_id"], "session_id": session, "confirm": True}, catalog, writes


@pytest.mark.parametrize("change", ["size", "missing", "product", "price", "currency", "option", "sku", "price_missing"])
def test_catalog_change_requires_new_approval(approval, change):
    client, body, catalog, writes = approval
    product = catalog[0]
    variant = product["variants"][0]
    if change == "size":
        variant["title"] = "L"
    elif change == "missing":
        product["variants"] = []
    elif change == "product":
        product["id"] = "prod_different"
    elif change == "price":
        variant["calculated_price"]["calculated_amount"] = 35
    elif change == "currency":
        variant["calculated_price"]["currency_code"] = "usd"
    elif change == "option":
        variant["options"][0]["value"] = "L"
    elif change == "sku":
        variant["sku"] = "changed"
    else:
        variant.pop("calculated_price")
    response = client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"})
    assert response.status_code == 409 and "approbation" in response.json()["detail"]
    assert storage.get_approval(body["approval_id"], "A")["status"] == "invalidated"
    assert not writes


def test_legacy_approval_requires_new_snapshot(approval):
    client, _, _, writes = approval
    old = storage.create_approval("A", "prepare_cart", {"variant_id": "variant_test", "quantity": 1})
    response = client.post("/actions/confirm", json={"approval_id": old["approval_id"], "confirm": True}, headers={"Authorization": "Bearer A"})
    assert response.status_code == 409 and not writes


def test_checkout_repricing_requires_new_approval(approval, monkeypatch):
    from app.catalog import cart_snapshot
    client, _, _, writes = approval
    cart = {"cart_id": "cart_fixture", "currency_code": "eur", "total": 30, "items": []}
    monkeypatch.setattr(api.medusa, "get_cart", lambda *a: cart)
    monkeypatch.setattr(api.medusa, "complete_cart", lambda *a: writes.append(a))
    action = storage.create_approval("A", "complete_cart", {"cart_id": "cart_fixture"}, cart_snapshot(cart))
    cart["total"] = 35
    response = client.post("/actions/confirm", json={"approval_id": action["approval_id"], "confirm": True}, headers={"Authorization": "Bearer A"})
    assert response.status_code == 409 and not writes


def test_chroma_model_loaders_disable_remote_code(monkeypatch):
    import sys
    from types import SimpleNamespace
    from app import rag
    calls = []
    def model(*a, **kw):
        calls.append(kw)
        return object()
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=model, CrossEncoder=model))
    rag._reranker.cache_clear()
    rag._embedding_model("fixture", "revision", "cache")
    rag._reranker("fixture", "revision", "cache")
    assert len(calls) == 2 and all(c["trust_remote_code"] is False for c in calls)
    rag._reranker.cache_clear()


def test_concurrent_confirm_and_cancel_only_one_write(approval, monkeypatch):
    client, body, _, writes = approval
    started, release = Event(), Event()
    def create(*args):
        writes.append(args)
        started.set()
        assert release.wait(5)
        return {"cart_id": "cart_fixture"}
    monkeypatch.setattr(api.medusa, "create_cart", create)
    headers = {"Authorization": "Bearer A"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, "/actions/confirm", json=body, headers=headers)
        assert started.wait(5)
        assert client.post("/actions/confirm", json=body, headers=headers).status_code == 409
        assert client.post("/actions/cancel", json=body, headers=headers).status_code == 409
        release.set()
        assert first.result().json()["status"] == "done"
    assert len(writes) == 1


def test_catalog_unavailable_prevents_write(approval, monkeypatch):
    client, body, _, writes = approval
    def unavailable(*a, **kw):
        raise BackendError("unavailable")
    monkeypatch.setattr(api.medusa, "products", unavailable)
    assert client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"}).status_code == 502
    assert storage.get_approval(body["approval_id"], "A")["status"] == "verification_failed"
    assert not writes


def test_partial_cart_is_linked_for_read_without_second_write(approval, monkeypatch):
    client, body, _, writes = approval
    def uncertain(*args):
        writes.append(args)
        raise BusinessOutcomeUnknown("line_item", "cart_fixture")
    monkeypatch.setattr(api.medusa, "create_cart", uncertain)
    response = client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"})
    assert response.status_code == 202 and response.json()["status"] == "needs_review"
    assert "n'est pas confirmé" in response.json()["customer_message"]
    assert conversations.active_cart(body["session_id"], "A") == "cart_fixture"
    assert client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"}).status_code == 409
    assert client.get("/sessions/" + body["session_id"] + "/cart", headers={"Authorization": "Bearer B"}).status_code == 404
    assert len(writes) == 1


@pytest.mark.parametrize("inserted", [False, True])
def test_lost_line_response_reconciles_only_by_owned_read(monkeypatch, inserted):
    monkeypatch.setenv("MEDUSA_PUBLISHABLE_KEY", "fixture")
    monkeypatch.setenv("MEDUSA_REGION_ID", "reg_fixture")
    calls = []
    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json={"customer": {"id": "A"}})
        if request.url.path.endswith("line-items"):
            raise httpx.ReadTimeout("sensitive transport details")
        cart = {"id": "cart_fixture", "customer_id": "A", "items": []}
        if request.method == "GET" and inserted:
            cart["items"] = [{"variant_id": "variant_test", "quantity": 1}]
        return httpx.Response(200, json={"cart": cart})
    medusa = Medusa(transport=httpx.MockTransport(handle))
    if inserted:
        assert medusa.create_cart("variant_test", 1, "A")["reconciled_by_read"]
    else:
        with pytest.raises(BusinessOutcomeUnknown) as error:
            medusa.create_cart("variant_test", 1, "A")
        assert error.value.result["cart_creation_confirmed"]
        assert "sensitive" not in str(error.value)
    assert len([c for c in calls if c[0] == "POST"]) == 2


def test_lost_cart_creation_response_is_uncertain_without_retry(monkeypatch):
    monkeypatch.setenv("MEDUSA_PUBLISHABLE_KEY", "fixture")
    monkeypatch.setenv("MEDUSA_REGION_ID", "reg_fixture")
    writes = []
    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"customer": {"id": "A"}})
        writes.append(request.url.path)
        raise httpx.ReadTimeout("private")
    with pytest.raises(BusinessOutcomeUnknown) as error:
        Medusa(transport=httpx.MockTransport(handle)).create_cart("variant_test", 1, "A")
    assert "cart_id" not in error.value.result and len(writes) == 1


@pytest.mark.parametrize("failure,reason", [("timeout", "provider_timeout"), ("http", "provider_http_error"), ("json", "invalid_payload"), ("facts", "unverified_fact_ids")])
def test_fallback_diagnostics_are_bounded(monkeypatch, failure, reason):
    from app.agent import Agent
    from app.documentary import choose_facts
    monkeypatch.setenv("LLM_API_KEY", "fixture-key")
    def post(client, url, **kwargs):
        request = httpx.Request("POST", url)
        if failure == "timeout":
            raise httpx.ReadTimeout("Bearer private-value")
        if failure == "http":
            return httpx.Response(429, request=request, text="Bearer private-value")
        content = 'bad-json' if failure == "json" else '{"fact_ids":["invented"]}'
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", post)
    diagnostics = {}
    ids, mode, _ = choose_facts(Agent(), "Quelle procédure ?", [{"id": "purchase"}], diagnostics)
    assert ids == ["purchase"] and mode == "verified_fact_fallback"
    assert diagnostics["reason"] == reason and "private-value" not in json.dumps(diagnostics)
