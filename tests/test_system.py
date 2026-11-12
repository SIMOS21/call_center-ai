import json
from pathlib import Path
import httpx
import pytest
from app.rag import chunk_text, build_lexical_index, lexical_search
from app.agent import Agent
from app.medusa import Medusa, BackendError
from app import storage


def test_chunking_and_invalid_overlap():
    assert len(chunk_text(" ".join(["test"]*200), 100, 20)) >= 2
    with pytest.raises(ValueError):
        chunk_text("hello", 20, 20)


def test_knowledge_provenance_and_retrieval(tmp_path):
    source_dir = tmp_path / "kb"
    source_dir.mkdir()
    source = "https://example.org/original-policy"
    (source_dir / "doc.json").write_text(json.dumps({"source": source, "title": "Shipping policy",
        "source_type": "test", "text": "Delivery tracking allows customers to view parcel progress. "*30}))
    index = tmp_path / "index.json"
    report = build_lexical_index(source_dir, 90, 20, index)
    assert report["documents"] == 1
    found = lexical_search("parcel delivery tracking", k=3, path=str(index))
    assert found and found[0]["source"] == source


def test_no_fabricated_index(tmp_path):
    with pytest.raises(ValueError, match="Aucun document"):
        build_lexical_index(tmp_path, dest=tmp_path / "index.json")


def test_invalid_tool_and_model_arguments(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "temp.sqlite3"))
    a = Agent()
    result = a.execute_tool("transfer_money", {}, "", "r1")
    assert "error" in result
    result = a.execute_tool("prepare_cart", {"variant_id": "var_ok", "quantity": -5}, "", "r1")
    assert "error" in result


def test_no_protected_action_without_authenticated_customer(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "temp.sqlite3"))
    a = Agent()
    result = a.execute_tool("prepare_cart", {"variant_id": "variant_test", "quantity": 2}, "", "r1")
    assert "error" in result


def test_customer_isolation_medusa(monkeypatch):
    monkeypatch.setenv("MEDUSA_PUBLISHABLE_KEY", "test_publishable_key")
    def handler(req):
        if req.url.path == "/store/customers/me":
            return httpx.Response(200, json={"customer":{"id":"cus_A"}})
        if req.url.path == "/store/orders/order_987":
            return httpx.Response(200, json={"order":{"id":"order_987", "customer_id":"cus_B"}})
        return httpx.Response(404)
    m = Medusa(transport=httpx.MockTransport(handler))
    with pytest.raises(BackendError, match="Accès refusé"):
        m.order("order_987", "fake-customer-token")


def test_confirm_not_automatic(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "temp.sqlite3"))
    created = storage.create_approval("cus_A", "prepare_cart", {"variant_id": "var_123", "quantity": 1})
    assert storage.get_approval(created["approval_id"], "cus_B") is None
    assert storage.get_approval(created["approval_id"], "cus_A")["status"] == "pending"
    assert storage.mark_approval(created["approval_id"], "cus_B") is False
    assert storage.mark_approval(created["approval_id"], "cus_A") is True
    assert storage.mark_approval(created["approval_id"], "cus_A") is False


def test_tickets_persist_with_ownership(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "temp.sqlite3"))
    t = storage.create_ticket("cus_A", "delivery", "Package is delayed", "order_1")
    assert t["status"] == "open"
    assert len(storage.get_tickets("cus_A")) == 1
    assert len(storage.get_tickets("cus_B")) == 0


def test_quality_metrics(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path / "temp.sqlite3"))
    storage.audit("r1", "search_knowledge", "read", True, 22)
    storage.audit("r2", "get_order_status", "read", False, 30, "BackendError")
    m = storage.metrics()
    assert m["tool_calls"] == 2 and m["tool_errors"] == 1
