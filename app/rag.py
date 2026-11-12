"""Document-grounded retrieval with explicit provenance; lexical baseline or Chroma dense index."""
from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path
from app.config import env, path_env


def chunk_text(text: str, chunk_words: int = 180, overlap_words: int = 35) -> list[str]:
    if chunk_words <= overlap_words or overlap_words < 0:
        raise ValueError("Chunk size must exceed overlap")
    words = text.split()
    step = chunk_words - overlap_words
    return [" ".join(words[i:i + chunk_words]) for i in range(0, len(words), step)
            if len(words[i:i + chunk_words]) >= 12]


def load_documents(directory: Path | str = "data/knowledge") -> list[dict]:
    """One JSON per original source, or .txt/.md with sidecar origin in filename."""
    docs = []
    for path in sorted(Path(directory).rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(record, dict) and record.get("text") and record.get("source"):
            docs.append(record)
    return docs


def build_lexical_index(directory: Path | str = "data/knowledge", chunk_words: int = 180,
                        overlap_words: int = 35, dest: Path | None = None) -> dict:
    from hashlib import sha256
    from datetime import datetime, timezone
    docs = load_documents(directory)
    rows = []
    for doc in docs:
        for index, chunk in enumerate(chunk_text(doc["text"], chunk_words, overlap_words)):
            rows.append({"id": sha256(f'{doc["source"]}:{index}:{chunk}'.encode()).hexdigest()[:24],
                         "title": doc.get("title", ""), "source": doc["source"],
                         "source_type": doc.get("source_type", "unknown"),
                         "retrieved_at": doc.get("retrieved_at", ""), "content": chunk})
    if not rows:
        raise ValueError("Aucun document réel importé. Lancez scripts/collect_real_sources.py")
    path = dest or path_env("INDEX_FILE", "data/index.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"chunks": rows, "parameters": {"chunk_words": chunk_words, "overlap_words": overlap_words},
               "built_at": datetime.now(timezone.utc).isoformat(), "documents_count": len(docs)}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    load_index.cache_clear()
    return {"documents": len(docs), "chunks": len(rows), "path": str(path)}


@lru_cache(maxsize=2)
def load_index(path: str):
    from sklearn.feature_extraction.text import TfidfVectorizer
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    chunks = data["chunks"]
    vec = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)
    matrix = vec.fit_transform([c["content"] for c in chunks])
    return chunks, vec, matrix


def lexical_search(question: str, k: int = 5, path: str | None = None) -> list[dict]:
    from sklearn.metrics.pairwise import cosine_similarity
    source = path or str(path_env("INDEX_FILE", "data/index.json"))
    if not Path(source).is_file():
        raise RuntimeError("Index absent. Exécutez python scripts/build_index.py")
    if not question.strip():
        return []
    chunks, vec, matrix = load_index(source)
    # Small, explicit vocabulary bridge for French support queries on English ABCD.
    terms = {"retour": "return", "remboursement": "refund", "livraison": "shipping delivery",
             "commande": "order", "mot de passe": "password", "annuler": "cancel",
             "taille": "size", "couleur": "color", "tache": "stain", "lent": "slow",
             "adresse": "address", "paiement": "payment", "facture": "bill"}
    lowered = question.lower()
    expanded = question + " " + " ".join(v for word, v in terms.items() if word in lowered)
    scores = cosine_similarity(vec.transform([expanded]), matrix).ravel()
    order = scores.argsort()[::-1][:min(k, len(scores))]
    return [{**chunks[int(i)], "score": round(float(scores[int(i)]), 4)}
            for i in order if scores[int(i)] >= float(env("RAG_MIN_SCORE", "0.12"))]


def build_chroma(directory: str = "data/knowledge", chunk_words: int = 180, overlap_words: int = 35) -> dict:
    """Optional dense RAG: reuses the versioned lexical chunk manifest."""
    import chromadb
    from sentence_transformers import SentenceTransformer
    result = build_lexical_index(directory, chunk_words, overlap_words)
    data = json.loads(path_env("INDEX_FILE", "data/index.json").read_text(encoding="utf-8"))
    chunks = data["chunks"]
    store = chromadb.PersistentClient(path=env("CHROMA_DIR", "data/chroma"))
    try:
        store.delete_collection("knowledge")
    except Exception:
        pass
    collection = store.get_or_create_collection("knowledge", metadata={"hnsw:space": "cosine"})
    model_name = env("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    embed = SentenceTransformer(model_name, cache_folder=str(path_env("EMBEDDING_CACHE", "data/models")),
                                revision=env("EMBEDDING_REVISION") or None)
    for start in range(0, len(chunks), 64):
        batch = chunks[start:start+64]
        embeddings = embed.encode([x["content"] for x in batch], normalize_embeddings=True).tolist()
        collection.add(ids=[x["id"] for x in batch], documents=[x["content"] for x in batch],
                       embeddings=embeddings,
                       metadatas=[{"title": x["title"], "source": x["source"],
                                   "source_type": x["source_type"]} for x in batch])
    dense_components.cache_clear()
    return {**result, "backend": "chroma", "embedding_model": model_name,
            "embedding_revision": env("EMBEDDING_REVISION"), "distance": "cosine"}


@lru_cache(maxsize=1)
def dense_components():
    import chromadb
    from sentence_transformers import SentenceTransformer
    return (chromadb.PersistentClient(path=env("CHROMA_DIR", "data/chroma")).get_collection("knowledge"),
            SentenceTransformer(env("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
                                cache_folder=str(path_env("EMBEDDING_CACHE", "data/models")),
                                revision=env("EMBEDDING_REVISION") or None))


def search(question: str, k: int | None = None) -> list[dict]:
    count = k or int(env("RAG_TOP_K", "5"))
    if env("RAG_BACKEND", "lexical") != "chroma":
        return lexical_search(question, count)
    collection, model = dense_components()
    v = model.encode([question], normalize_embeddings=True)[0].tolist()
    if not question.strip() or collection.count() == 0:
        return []
    result = collection.query(query_embeddings=[v], n_results=min(count, collection.count()))
    return [dict(id=rid, content=content, title=meta.get("title"), source=meta.get("source"),
                 source_type=meta.get("source_type"), score=round(1.0-float(distance), 4))
            for rid, content, meta, distance in zip(result["ids"][0], result["documents"][0],
                                                     result["metadatas"][0], result["distances"][0])
            if 1.0-float(distance) >= float(env("DENSE_MIN_SCORE", "0.3"))]
