import argparse
import json
from pathlib import Path
from app.rag import build_lexical_index, build_chroma
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["lexical", "chroma", "hybrid"], default="lexical")
    p.add_argument("--source", default="data/knowledge")
    p.add_argument("--output", type=Path, help="Publish atomically here; default INDEX_FILE. Existing baseline files are not migrated.")
    p.add_argument("--chunk-words", type=int, default=180)
    p.add_argument("--overlap-words", type=int, default=35)
    a = p.parse_args()
    func = build_chroma if a.backend in ("chroma", "hybrid") else build_lexical_index
    result = func(directory=a.source, chunk_words=a.chunk_words, overlap_words=a.overlap_words, dest=a.output)
    Path("reports").mkdir(exist_ok=True)
    Path(f"reports/index-build-{a.backend}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result)
