"""Validated documentary inputs and atomic, single-writer index publication."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse


def load_documents(directory):
    root = Path(directory)
    docs = []
    sidecars = {p.with_name(p.name + ".meta.json") for p in root.rglob("*") if p.suffix.lower() in (".txt", ".md")}
    for path in sorted(root.rglob("*")):
        if path in sidecars or not path.is_file():
            continue
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError):
                raise ValueError(f"Invalid documentary JSON: {path.name}") from None
            records = data.get("documents", [data]) if isinstance(data, dict) else data
            if not isinstance(records, list):
                raise ValueError(f"Expected document object/list: {path.name}")
        elif path.suffix.lower() in (".txt", ".md"):
            meta = path.with_name(path.name + ".meta.json")
            body = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
            front = {}
            if body.startswith("---\n"):
                import yaml
                parts = body.split("\n---\n", 1)
                if len(parts) != 2:
                    raise ValueError(f"Unclosed front matter: {path.name}")
                front = yaml.safe_load(parts[0][4:])
                if not isinstance(front, dict):
                    raise ValueError(f"Invalid front matter: {path.name}")
                body = parts[1]
            if not meta.is_file() and not front:
                raise ValueError(f"Explicit provenance sidecar required: {path.name}.meta.json")
            data = json.loads(meta.read_text(encoding="utf-8-sig")) if meta.is_file() else front
            if not isinstance(data, dict):
                raise ValueError(f"Invalid provenance: {meta.name}")
            if front.get("source") and data.get("source") != front["source"]:
                raise ValueError(f"Conflicting provenance: {path.name}")
            records = [{**front, **data, "text": body}]
        else:
            continue
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"Invalid document: {path.name}")
            text = record.get("text", record.get("content"))
            source = record.get("source", record.get("url"))
            if not isinstance(text, str) or not text.strip() or not isinstance(source, str):
                raise ValueError(f"Nonempty text and explicit source required: {path.name}")
            parsed = urlparse(source)
            if parsed.scheme not in ("http", "https", "urn") or (parsed.scheme != "urn" and not parsed.netloc):
                raise ValueError(f"Invalid provenance URI: {path.name}")
            doc = {**record, "text": text.strip(), "source": source,
                   "title": record.get("title") or path.stem,
                   "category": record.get("category") or record.get("flow") or record.get("source_type") or "unspecified"}
            if any(not isinstance(doc[key], str) for key in ("title", "category")):
                raise ValueError(f"Invalid documentary metadata: {path.name}")
            doc["sha256"] = sha256(doc["text"].encode()).hexdigest()
            docs.append(doc)
    return docs


def make_payload(directory, chunk_words, overlap_words, chunker):
    docs = load_documents(directory)
    rows = []
    for doc in docs:
        for number, content in enumerate(chunker(doc["text"], chunk_words, overlap_words)):
            rows.append({"id": sha256(f'{doc["source"]}:{number}:{content}'.encode()).hexdigest()[:24],
                         "title": doc["title"], "category": doc["category"], "source": doc["source"],
                         "source_type": doc.get("source_type") or "unspecified", "retrieved_at": doc.get("retrieved_at") or "",
                         "document_sha256": doc["sha256"], "content": content,
                         "indexed_text": f'Title: {doc["title"]}\nCategory: {doc["category"]}\nSource: {doc["source"]}\n{content}'})
    if not rows:
        raise ValueError("Aucun document réel importé")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate source/chunk identifiers; resolve duplicate documents before publishing")
    generation = sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"schema_version": 2, "generation": generation, "chunks": rows,
            "parameters": {"chunk_words": chunk_words, "overlap_words": overlap_words},
            "built_at": datetime.now(timezone.utc).isoformat(), "documents_count": len(docs)}


@contextmanager
def writer_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("Index rebuild already running; a crash lock requires operator review") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def publish(path, payload):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
