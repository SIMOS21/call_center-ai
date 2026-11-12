"""Measured two-configuration development benchmark; no human-validation claim."""
import hashlib
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import mlflow
from app.rag import build_lexical_index, lexical_search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-baseline", action="store_true", help="Explicitly replace the reviewed baseline")
    args = parser.parse_args()
    cases_path = Path("evaluation/retrieval_cases.jsonl")
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8-sig").splitlines() if line]
    mlflow.set_tracking_uri("sqlite:///data/mlflow.sqlite3")
    mlflow.set_experiment("commerceops-rag-development")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "annotation": "agent_reviewed_not_human_validated", "n": len(cases), "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(), "configurations": []}
    Path("reports").mkdir(exist_ok=True)
    for words, overlap in [(90, 20), (180, 35)]:
        index = Path(f"data/benchmark-{words}.json")
        built = build_lexical_index(chunk_words=words, overlap_words=overlap, dest=index)
        latencies, hits, predictions = [], 0, []
        for case in cases:
            source = "https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json#flow=" + case["flow"] + "&subflow=" + case["subflow"]
            # Warm-up separately; report warm-query latency, excluding index vectorization.
            lexical_search(case["question"], path=str(index))
            started = time.perf_counter()
            rows = lexical_search(case["question"], path=str(index))
            latencies.append((time.perf_counter()-started)*1000)
            hit = any(row["source"] == source for row in rows)
            hits += hit
            predictions.append({"question": case["question"], "expected_source": source, "hit_at_5": hit, "retrieved_sources": [row["source"] for row in rows]})
        metrics = {"recall_at_5": hits/len(cases), "n_annotated": len(cases), "mean_retrieval_ms": statistics.mean(latencies), "p95_retrieval_ms": sorted(latencies)[int(.95*(len(latencies)-1))]}
        with mlflow.start_run(run_name=f"lexical-{words}") as run:
            mlflow.log_params({"backend": "lexical", "chunk_words": words, "overlap_words": overlap, "top_k": 5, "annotation": report["annotation"], "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest()})
            mlflow.log_metrics(metrics)
            prediction_path = Path(f"reports/predictions-{words}.json")
            prediction_path.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(prediction_path))
            report["configurations"].append({"chunk_words": words, "overlap_words": overlap, **built, **metrics, "mlflow_run_id": run.info.run_id})
    selected = max(report["configurations"], key=lambda row: row["recall_at_5"])
    report["selected_chunk_words"] = selected["chunk_words"]
    report["retrieval"] = {k: selected[k] for k in ("recall_at_5", "n_annotated", "mean_retrieval_ms", "p95_retrieval_ms")}
    build_lexical_index(chunk_words=selected["chunk_words"], overlap_words=selected["overlap_words"])
    report["agent"] = {"status": "NOT_EVALUATED", "reason": "LLM key absent; Medusa task success measured separately"}
    live = Path("reports/agent-live.json")
    if live.exists():
        live_report = json.loads(live.read_text(encoding="utf-8"))
        report["agent"] = {**live_report["metrics"], "status": "EVALUATED_GUIDED_DEVELOPMENT",
                           "model": live_report["model"], "limitation": live_report["limitation"]}
    Path("reports/evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    baseline = {"justification": "Observed development baseline, 12 agent-annotated cases. Zero recall regression permitted on this fixed corpus. Not human-validated or an end-to-end success criterion.", "checks": {"retrieval.recall_at_5": {"baseline": report["retrieval"]["recall_at_5"], "max_drop": 0}, "retrieval.n_annotated": {"baseline": len(cases), "max_drop": 0}}}
    if args.record_baseline:
        Path("docs/quality_baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
