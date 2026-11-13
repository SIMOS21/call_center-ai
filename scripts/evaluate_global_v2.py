"""Fixed public development comparison; frozen final is hashed, never parsed."""
import hashlib
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from app import rag
from app.config import path_env
from scripts.diagnose_v2 import CASES

DEVELOPMENT = [(c[0], c[1], c[2]) for c in CASES] + [
    ("N01", "J'ai reçu une chemise noire au lieu de la verte. Quelle procédure de retour décrit ce problème ?", "Return Due to Color"),
    ("N02", "Un article manque dans mon carton à la réception. Quelle référence consulter ?", "Missing Item"),
    ("N03", "Forgot my username while my password still works. Which recovery procedure applies?", "Recover Username"),
    ("N04", "Paiement rejeté avec une carte valide : quelle procédure de dépannage est documentée ?", "Invalid Credit Card"),
    ("N05", "Quelle référence pour retourner un pantalon taché ?", "Return Due to Stain"),
    ("N06", "My parcel contains the wrong colour. What return workflow is documented?", "Return Due to Color"),
]
NEGATIVES = ["Quelle politique officielle prévoit dix ans de garantie pour vos machines à café ?", "Quelle procédure documente les cratères de la lune ?"]


def main():
    os.environ["HF_HUB_OFFLINE"] = "1"
    index = path_env("INDEX_FILE", "data/index.json")
    model_spec = json.loads(index.read_bytes()).get("dense")
    configurations = [("metadata_chunks_baseline", lambda q: rag.lexical_search(q, path=str(index))),
                      ("source_documents", lambda q: rag.documentary_search(q, path=str(index))),
                      ("dense_baseline", lambda q: rag.dense_search(q))]
    def hybrid(q):
        before = os.environ.get("RAG_BACKEND")
        os.environ["RAG_BACKEND"] = "hybrid"
        try:
            return rag.search(q)
        finally:
            if before is None:
                os.environ.pop("RAG_BACKEND", None)
            else:
                os.environ["RAG_BACKEND"] = before
    configurations.append(("hybrid_existing_score_fusion", hybrid))
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "split": "development_seen_not_independent",
              "annotations": "Agent-reviewed original ABCD text; D01-D04 supplied in mission, N01-N06 new development paraphrases; no human gold review",
              "coverage_note": "Missing Item partially covers the received-incomplete-parcel scenario; username is a simulation, not real recovery",
              "parameters": {"document_body_weight": .65, "document_title_weight": .35, "min_score": .12, "top_k": 5, "reranking": "disabled"},
              "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(), "embedding": model_spec,
              "final_sha256_only": hashlib.sha256(Path("evaluation/final-v3.jsonl").read_bytes()).hexdigest(),
              "human_answer_fidelity": {"n": 0, "status": "NOT_EVALUATED"}, "cost": None, "configurations": []}
    for name, retrieve in configurations:
        results, latencies = [], []
        retrieve(DEVELOPMENT[0][1])  # warm up; not included in timing
        for identity, question, expected in DEVELOPMENT:
            start = time.perf_counter()
            rows = retrieve(question)
            latencies.append((time.perf_counter()-start)*1000)
            correct = [r["title"].endswith("/ " + expected) for r in rows]
            unique = {r["source"]: r["title"].endswith("/ " + expected) for r in rows}
            results.append({"id": identity, "question": question, "expected_subflow": expected, "hit_at_5": any(correct),
                            "top1_correct": bool(correct and correct[0]), "source_precision_unique": sum(unique.values())/len(unique) if unique else 0,
                            "predicted_sources": [{"title": r["title"], "source": r["source"], "score": r["score"], **{k: r[k] for k in ("lexical_score", "dense_score", "body_score", "title_score") if k in r}} for r in rows]})
        negatives = [{"question": q, "abstained": not bool(retrieve(q))} for q in NEGATIVES]
        report["configurations"].append({"name": name, "n": len(results), "recall_at_5": statistics.mean(r["hit_at_5"] for r in results),
                                          "top1_accuracy": statistics.mean(r["top1_correct"] for r in results),
                                          "mean_source_precision_unique": statistics.mean(r["source_precision_unique"] for r in results),
                                          "latency_warm_mean_ms": statistics.mean(latencies), "latency_warm_p95_ms": sorted(latencies)[int(.95*(len(latencies)-1))],
                                          "negative_n": len(negatives), "negative_retrieval_abstention": statistics.mean(r["abstained"] for r in negatives),
                                          "cases": results, "negatives": negatives})
    out = Path("reports/global-v2/development.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{k: r[k] for k in ("name", "n", "recall_at_5", "top1_accuracy", "mean_source_precision_unique", "latency_warm_mean_ms")} for r in report["configurations"]], indent=2))


if __name__ == "__main__":
    main()
