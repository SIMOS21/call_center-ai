"""Offline tests never inherit a live provider key from the local .env."""
import sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture(scope="session")
def documentary_index(tmp_path_factory):
    from app.rag import build_lexical_index
    with TemporaryDirectory(prefix="documentary-", dir=tmp_path_factory.getbasetemp()) as directory:
        index = Path(directory) / "index.json"
        build_lexical_index(Path(__file__).parent / "fixtures/knowledge", dest=index)
        yield index


@pytest.fixture(autouse=True)
def no_live_provider_key(monkeypatch, tmp_path, documentary_index):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("INDEX_FILE", str(documentary_index))
    monkeypatch.setenv("RAG_BACKEND", "lexical")
    monkeypatch.setenv("DB_FILE", str(tmp_path / "isolated.sqlite3"))
    monkeypatch.setattr("app.documentary.sanitized_tool_span", lambda *a: nullcontext(None))
    monkeypatch.setattr("app.medusa.sanitized_tool_span", lambda *a: nullcontext(None))
    if "app.api" in sys.modules:
        monkeypatch.setattr(sys.modules["app.api"].agent, "key", "")
        monkeypatch.setattr(sys.modules["app.api"], "sanitized_tool_span", lambda *a: nullcontext(None))
