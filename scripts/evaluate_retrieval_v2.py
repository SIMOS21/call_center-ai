"""Fixed development comparison. Never trains/tunes on the sealed final set."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import statistics
import time
from datetime import datetime, timezone
from app import rag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true", help="Requires human approval of the exact frozen final-v3 SHA")
    args = parser.parse_args()
    cases_path = Path("evaluation/final-v3.jsonl" if args.final else "evaluation/retrieval_cases.jsonl")
    if args.final:
        from scripts.freeze_final_v3 import validate_review
        try:
            validate_review(cases_path, "evaluation/final-v3.review.json")
        except (ValueError, OSError) as exc:
            destination = Path("reports/rag-v2")
            destination.mkdir(exist_ok=True)
            (destination/"final-status.json").write_text(json.dumps({"status": "BLOCKED_PENDING_HUMAN_REVIEW", "n_evaluated": 0,
                                                                    "dataset_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
                                                                    "faithfulness": {"status": "NOT_EVALUATED", "n": 0}}, indent=2), encoding="utf-8")
            raise SystemExit(str(exc)) from None
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8-sig").splitlines() if line]
    all_cases = cases
    cases = [case for case in all_cases if case.get("flow")]
    configurations = [("legacy_lexical", "lexical", "data/index.json"),
                      ("legacy_dense", "chroma", "data/index.json"),
                      ("metadata_lexical", "lexical", "data/rag-v2/index.json"),
                      ("metadata_dense", "chroma", "data/rag-v2/index.json"),
                      ("hybrid", "hybrid", "data/rag-v2/index.json")]
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "split": "development_already_consulted",
              "annotations": "agent_authored; flow/subflow and source text verified structurally, not human reviewed",
              "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
              "parameters_frozen": {"chunk_words": 90, "overlap_words": 20, "top_k": 5, "fusion_weight": .5, "candidate_pool": 20, "reranker": "disabled"},
              "human_faithfulness": {"status": "NOT_EVALUATED", "n": 0}, "independent_test": {"status": "BLOCKED_PENDING_HUMAN_REVIEW", "n": 0}, "configurations": []}
    guidelines = json.loads(Path("data/raw/abcd/guidelines.json").read_text(encoding="utf-8"))
    negative_questions = ["astrophysics quasar gravitational", "volcanic lava seismograph tectonics"]
    if args.final:
        negative_questions = [case["question"] for case in all_cases if case.get("expected_abstention")]
        report["split"] = "frozen_final_human_reviewed"
        report["annotations"] = "human approval file matched dataset SHA"
        report["independent_test"] = {"status": "RETRIEVAL_ONLY", "n": len(all_cases)}
    fixed = {"RAG_DOCUMENT_GROUPING": "false", "RAG_RERANKER": "", "RAG_TOP_K": "5", "HYBRID_CANDIDATES": "20", "HYBRID_LEXICAL_WEIGHT": "0.5", "HYBRID_MIN_SCORE": "0.06", "RAG_MIN_SCORE": "0.12", "DENSE_MIN_SCORE": "0.3"}
    saved = {key: os.environ.get(key) for key in ("RAG_BACKEND", "INDEX_FILE", *fixed)}
    try:
        os.environ.update(fixed)
        for name, backend, index in configurations:
            os.environ.update(RAG_BACKEND=backend, INDEX_FILE=index)
            times, predictions, hits = [], [], 0
            for case in cases:
                assert case["subflow"] in guidelines[case["flow"]]["subflows"]
                expected = "https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json#flow="+case["flow"]+"&subflow="+case["subflow"]
                rag.search(case["question"])
                start = time.perf_counter()
                rows = rag.search(case["question"])
                times.append((time.perf_counter()-start)*1000)
                hit = any(row["source"] == expected for row in rows)
                hits += hit
                predictions.append({"question": case["question"], "expected_source": expected, "hit_at_5": hit, "abstained": not bool(rows), "sources": [row["source"] for row in rows]})
            negatives = [not bool(rag.search(question)) for question in negative_questions]
            report["configurations"].append({"name": name, "backend": backend, "index_sha256": hashlib.sha256(Path(index).read_bytes()).hexdigest(),
                                             "n": len(cases), "recall_at_5": hits/len(cases),
                                             "positive_abstention_rate": sum(row["abstained"] for row in predictions)/len(cases),
                                             "negative_n": len(negatives), "negative_abstention_rate": sum(negatives)/len(negatives),
                                             "latency_mean_ms": statistics.mean(times), "latency_p95_ms": sorted(times)[int(.95*(len(times)-1))],
                                             "cases": predictions})
    finally:
        for key,value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    out = Path("reports/rag-v2")
    out.mkdir(exist_ok=True)
    (out/("final.json" if args.final else "development.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.final:
        (out/"final-status.json").write_text(json.dumps({"status": "RETRIEVAL_EVALUATED_HUMAN_REVIEWED_INPUTS", "n_evaluated": len(all_cases),
                                                        "dataset_sha256": report["cases_sha256"], "faithfulness": report["human_faithfulness"]}, indent=2), encoding="utf-8")
    print(json.dumps([{key:row[key] for key in ("name", "recall_at_5", "positive_abstention_rate", "negative_abstention_rate", "latency_mean_ms")} for row in report["configurations"]], indent=2))


if __name__ == "__main__":
    main()
