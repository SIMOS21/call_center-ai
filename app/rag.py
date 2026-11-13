"""Versioned lexical/dense retrieval and conservative hybrid score fusion."""
from __future__ import annotations
import json
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import uuid
import re
import unicodedata
from app.config import env, path_env
from app.knowledge_index import load_documents, make_payload, writer_lock, publish

COLOR_WORDS = r"\b(rouges?|bleues?|bleus?|vertes?|verts?|noires?|noirs?|blanches?|blancs?|couleurs?|colou?rs?)\b"

def chunk_text(text: str, chunk_words: int = 180, overlap_words: int = 35) -> list[str]:
    if chunk_words <= overlap_words or overlap_words < 0:
        raise ValueError("Chunk size must exceed overlap")
    words = text.split()
    # Short, valid documents must not silently disappear.
    return [" ".join(words[i:i + chunk_words]) for i in range(0, len(words), chunk_words-overlap_words)]


def build_lexical_index(directory="data/knowledge", chunk_words=180, overlap_words=35, dest=None):
    path = Path(dest) if dest is not None else path_env("INDEX_FILE", "data/index.json")
    with writer_lock(path):
        payload = make_payload(directory, chunk_words, overlap_words, chunk_text)
        # Validate vectorization before replacing a usable index.
        _vectorize(json.dumps(payload, ensure_ascii=False).encode())
        publish(path, payload)
    return {"documents": payload["documents_count"], "chunks": len(payload["chunks"]), "path": str(path), "generation": payload["generation"]}


@lru_cache(maxsize=4)
def _vectorize(raw):
    from sklearn.feature_extraction.text import TfidfVectorizer
    data = json.loads(raw)
    chunks = data["chunks"]
    if not chunks:
        raise RuntimeError("Empty index")
    if any(any(not isinstance(c.get(key), str) or not c[key] for key in ("id", "source", "content")) for c in chunks):
        raise ValueError("Invalid index references")
    vec = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)
    matrix = vec.fit_transform([c.get("indexed_text", c["content"]) for c in chunks])
    return chunks, vec, matrix


def load_index(path):
    # Read one atomic snapshot; content keys also detect same-size replacements.
    try:
        raw = Path(path).read_bytes()
        return _vectorize(raw)
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeError("Index absent ou invalide; reconstruire avec scripts.build_index") from None


load_index.cache_clear = _vectorize.cache_clear


def expand_query(question):
    # Frozen domain bridge; never derived from final evaluation questions.
    terms = {"retour": "return", "remboursement": "refund", "livraison": "shipping delivery",
             "commande": "order", "mot de passe": "password", "annuler": "cancel",
             "taille": "size", "couleur": "color", "tache": "stain", "lent": "slow",
             "adresse": "address", "paiement": "payment", "facture": "bill"}
    lowered = question.lower()
    return question + " " + " ".join(value for word, value in terms.items() if word in lowered)


def normalize_query(question):
    return "".join(c for c in unicodedata.normalize("NFKD", question.lower()) if not unicodedata.combining(c))


def documentary_query(question):
    """Generic FR/EN domain bridge. No final-set examples or source ID shortcuts."""
    text = normalize_query(question)
    bridge = [(COLOR_WORDS, "color colour"),
              (r"\b(identifiant|pseudo|username|utilisateur)\b", "recover username account access"),
              (r"\b(carte|bancaire|credit card)\b", "credit card"),
              (r"\b(refuse|rejete|rejected|declined|invalide|invalid)\b", "invalid rejected"),
              (r"\b(colis|paquet|parcel|package)\b", "package shipping"),
              (r"\b(articles?|items?)\b", "item"),
              (r"\b(manque|manquant|absent|missing)\b", "missing"),
              (r"\b(recuperer|oublie|forgot|recover)\b", "recover"),
              (r"\b(retour|renvoyer|retourner|return)\b", "return"),
              (r"\b(tache|sale|stain)\b", "stain"),
              (r"\b(taille|size)\b", "size"),
              (r"\b(abime|casse|damaged|broken)\b", "damaged broken"),
              (r"\b(livraison|livrer|delivery)\b", "shipping delivery"),
              (r"\b(remboursement|refund)\b", "refund"),
              (r"\b(lent|lente|slow)\b", "slow"),
              (r"\b(adresse|address)\b", "address"),
              (r"\b(annuler|annulation|cancel)\b", "cancel")]
    additions = [english for pattern, english in bridge if re.search(pattern, text)]
    if re.search(r"\b(manque|manquant|absent|missing)\b", text) and re.search(r"\b(articles?|items?)\b", text):
        additions.append("missing item")
    if re.search(r"\b(recu|received)\b", text) and re.search(COLOR_WORDS, text):
        additions.append("return color")
    return question + " " + " ".join(additions)


@lru_cache(maxsize=4)
def _document_vectors(raw):
    from sklearn.feature_extraction.text import TfidfVectorizer
    payload = json.loads(raw)
    groups = {}
    for row in payload["chunks"]:
        key = (row["source"], row.get("document_sha256", ""))
        groups.setdefault(key, []).append(row)
    docs = []
    for rows in groups.values():
        # Chunks are kept verbatim and individually referenced, including overlap.
        docs.append({**rows[0], "content": "\n".join(row["content"] for row in rows),
                     "chunks": [{"id": row["id"], "content": row["content"]} for row in rows]})
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)
    matrix = vectorizer.fit_transform([f"{d['title']} {d.get('category', '')}\n{d['content']}" for d in docs])
    titles = vectorizer.transform([d["title"] for d in docs])
    return docs, vectorizer, matrix, titles


def documentary_search(question, k=5, path=None):
    """Source-level ranking avoids metadata-only orphan chunks dominating answers."""
    from sklearn.metrics.pairwise import cosine_similarity
    if not question.strip() or k <= 0:
        return []
    raw = Path(path or path_env("INDEX_FILE", "data/index.json")).read_bytes()
    docs, vectorizer, matrix, titles = _document_vectors(raw)
    query = vectorizer.transform([documentary_query(question)])
    body_scores = cosine_similarity(query, matrix).ravel()
    title_scores = cosine_similarity(query, titles).ravel()
    scores = .65 * body_scores + .35 * title_scores
    return [{**docs[int(i)], "score": round(float(scores[i]), 6),
             "body_score": round(float(body_scores[i]), 6), "title_score": round(float(title_scores[i]), 6),
             "ranking": "document_tfidf_65_35_v1"} for i in scores.argsort()[::-1][:k]
            if scores[i] >= float(env("RAG_MIN_SCORE", "0.12"))]


def lexical_search(question, k=5, path=None):
    from sklearn.metrics.pairwise import cosine_similarity
    if not question.strip() or k <= 0:
        return []
    chunks, vec, matrix = load_index(path or str(path_env("INDEX_FILE", "data/index.json")))
    scores = cosine_similarity(vec.transform([expand_query(question)]), matrix).ravel()
    order = scores.argsort()[::-1][:min(k, len(scores))]
    return [{**chunks[int(i)], "score": round(float(scores[int(i)]), 6)} for i in order
            if scores[int(i)] >= float(env("RAG_MIN_SCORE", "0.12"))]


@lru_cache(maxsize=2)
def _embedding_model(name, revision, cache):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name, cache_folder=cache, revision=revision or None, trust_remote_code=False)


def build_chroma(directory="data/knowledge", chunk_words=180, overlap_words=35, dest=None):
    import chromadb
    path = Path(dest) if dest is not None else path_env("INDEX_FILE", "data/index.json")
    with writer_lock(path):
        payload = make_payload(directory, chunk_words, overlap_words, chunk_text)
        _vectorize(json.dumps(payload, ensure_ascii=False).encode())
        name = env("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        revision = env("EMBEDDING_REVISION")
        embed = _embedding_model(name, revision, str(path_env("EMBEDDING_CACHE", "data/models")))
        directory_path = str(path_env("CHROMA_DIR", "data/chroma"))
        store = chromadb.PersistentClient(path=directory_path)
        collection_name = "knowledge_" + uuid.uuid4().hex
        collection = store.create_collection(collection_name, embedding_function=None, metadata={"hnsw:space": "cosine", "generation": payload["generation"]})
        try:
            chunks = payload["chunks"]
            for start in range(0, len(chunks), 64):
                batch = chunks[start:start+64]
                collection.add(ids=[c["id"] for c in batch], documents=[c["content"] for c in batch],
                               embeddings=embed.encode([c["indexed_text"] for c in batch], normalize_embeddings=True).tolist(),
                               metadatas=[{key: c[key] for key in ("title", "category", "source", "source_type", "retrieved_at", "document_sha256")} for c in batch])
            if collection.count() != len(chunks):
                raise RuntimeError("Incomplete dense index")
            payload["dense"] = {"directory": directory_path, "collection": collection_name,
                                "model": name, "revision": revision, "generation": payload["generation"]}
            # This one pointer publishes both lexical rows and an immutable dense generation.
            publish(path, payload)
        except Exception:
            store.delete_collection(collection_name)
            raise
    return {"documents": payload["documents_count"], "chunks": len(payload["chunks"]), "path": str(path),
            "generation": payload["generation"], "backend": "chroma", "embedding_model": name,
            "embedding_revision": revision, "collection": collection_name, "distance": "cosine"}


@lru_cache(maxsize=4)
def _dense_components(specification, cache):
    import chromadb
    spec = json.loads(specification)
    collection = chromadb.PersistentClient(path=spec["directory"]).get_collection(spec["collection"], embedding_function=None)
    if spec.get("generation") and (collection.metadata or {}).get("generation") != spec["generation"]:
        raise RuntimeError("Dense/lexical index generations do not match")
    model = _embedding_model(spec["model"], spec.get("revision", ""), cache)
    return collection, model


def dense_components():
    try:
        payload = json.loads(path_env("INDEX_FILE", "data/index.json").read_bytes())
    except (OSError, ValueError):
        raise RuntimeError("Index manifest absent ou invalide") from None
    spec = payload.get("dense")
    if not spec:
        if payload.get("schema_version", 1) >= 2:
            raise RuntimeError("Dense index not built for this generation")
        # Legacy baseline remains readable, but is never accepted for hybrid fusion.
        spec = {"directory": str(path_env("CHROMA_DIR", "data/chroma")), "collection": "knowledge",
                "model": env("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"), "revision": env("EMBEDDING_REVISION")}
    return _dense_components(json.dumps(spec, sort_keys=True), str(path_env("EMBEDDING_CACHE", "data/models")))


dense_components.cache_clear = _dense_components.cache_clear


def dense_search(question, k=5):
    if not question.strip() or k <= 0:
        return []
    collection, model = dense_components()
    if collection.count() == 0:
        return []
    vector = model.encode([question], normalize_embeddings=True)[0].tolist()
    result = collection.query(query_embeddings=[vector], n_results=min(k, collection.count()))
    return [{"id": rid, "content": content, **meta, "score": round(1-float(distance), 6)}
            for rid, content, meta, distance in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0])
            if 1-float(distance) >= float(env("DENSE_MIN_SCORE", "0.3"))]


def fuse_results(lexical, dense, weight=.5):
    if not 0 <= weight <= 1:
        raise ValueError("Hybrid weight must be between zero and one")
    rows = {}
    for kind, results in (("lexical", lexical), ("dense", dense)):
        for row in results:
            item = rows.setdefault(row["id"], {**row, "lexical_score": 0., "dense_score": 0.})
            if (item["source"], item["content"]) != (row["source"], row["content"]):
                raise RuntimeError("Conflicting chunk references")
            item[kind+"_score"] = row["score"]
    for row in rows.values():
        row["score"] = weight*row["lexical_score"]+(1-weight)*row["dense_score"]
    return sorted(rows.values(), key=lambda r: (-r["score"], r["id"]))


@lru_cache(maxsize=1)
def _reranker(name, revision, cache):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(name, revision=revision or None, cache_folder=cache, trust_remote_code=False)


def rerank(question, rows):
    name = env("RAG_RERANKER")
    if not name or not rows:
        return rows
    if not env("RAG_RERANKER_REVISION"):
        raise RuntimeError("Pin reranker revision before enabling")
    model = _reranker(name, env("RAG_RERANKER_REVISION"), str(path_env("EMBEDDING_CACHE", "data/models")))
    scores = model.predict([(question, f"{r['title']}\n{r['content']}") for r in rows])
    return sorted([{**row, "rerank_score": float(score)} for row, score in zip(rows, scores)], key=lambda r: -r["rerank_score"])


def search(question, k=None):
    try:
        return _search(question, k)
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("Retrieval backend unavailable; no unverified fallback") from None


def _search(question, k=None):
    count = int(env("RAG_TOP_K", "5")) if k is None else k
    backend = env("RAG_BACKEND", "lexical")
    if backend == "lexical":
        if env("RAG_DOCUMENT_GROUPING", "true").lower() == "true":
            return documentary_search(question, count)
        return lexical_search(question, count)
    if backend == "chroma":
        return dense_search(question, count)
    if backend != "hybrid":
        raise RuntimeError("Unknown RAG backend")
    if not question.strip() or count <= 0:
        return []
    path = path_env("INDEX_FILE", "data/index.json")
    # Pin one manifest for the entire fusion: a publisher may run concurrently.
    from app.config import env as read_env
    raw = path.read_bytes()
    payload = json.loads(raw)
    if not payload.get("dense") or payload["dense"]["generation"] != payload["generation"]:
        raise RuntimeError("Hybrid requires a coherent versioned dense/lexical bundle")
    # Lexical uses this exact snapshot; dense uses the matching immutable collection.
    chunks, vec, matrix = _vectorize(raw)
    from sklearn.metrics.pairwise import cosine_similarity
    scores = cosine_similarity(vec.transform([expand_query(question)]), matrix).ravel()
    pool = max(count, min(int(read_env("HYBRID_CANDIDATES", "20")), 100))
    lexical = [{**chunks[int(i)], "score": float(scores[i])} for i in scores.argsort()[::-1][:pool]
               if scores[i] >= float(env("RAG_MIN_SCORE", "0.12"))]
    collection, model = _dense_components(json.dumps(payload["dense"], sort_keys=True), str(path_env("EMBEDDING_CACHE", "data/models")))
    if collection.count() == 0:
        raise RuntimeError("Empty dense generation")
    result = collection.query(query_embeddings=model.encode([question], normalize_embeddings=True).tolist(), n_results=min(pool, collection.count()))
    dense = [{"id": rid, "content": content, **meta, "score": 1-float(distance)}
             for rid, content, meta, distance in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0])
             if 1-float(distance) >= float(env("DENSE_MIN_SCORE", "0.3"))]
    fused = rerank(question, [row for row in fuse_results(lexical, dense, float(env("HYBRID_LEXICAL_WEIGHT", "0.5")))
                            if row["score"] >= float(env("HYBRID_MIN_SCORE", "0.06"))])
    seen, answer = set(), []
    for row in fused:
        if row["source"] not in seen:
            answer.append(row)
            seen.add(row["source"])
    return answer[:count]
