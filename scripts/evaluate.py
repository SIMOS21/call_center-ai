"""Offline retrieval test + optional agent task-evaluation; no invented scores."""
from __future__ import annotations
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from app.rag import lexical_search
from app.agent import Agent


def recall_at_k(cases: list[dict], k: int) -> dict:
    hits, valid, latencies = 0, 0, []
    for case in cases:
        # Requires human-reviewed relevant_source URL; not possible to infer from labels.
        if not case.get("relevant_source"):
            continue
        start = time.perf_counter()
        result = lexical_search(case["question"], k)
        latencies.append((time.perf_counter()-start)*1000)
        valid += 1
        if any(r["source"] == case["relevant_source"] for r in result):
            hits += 1
    return {f"recall_at_{k}": hits/valid if valid else None, "n_annotated": valid,
            "mean_retrieval_ms": round(statistics.mean(latencies),2) if latencies else None}


def agent_selection_proxy(cases: list[dict], limit: int) -> dict:
    agent = Agent()
    n, correct, failed = 0, 0, 0
    for case in cases[:limit]:
        try:
            # This does NOT assess full action success: real Medusa customer tokens are absent.
            output = agent.respond(case["input"])
            correct += int(case["expected_tool_family_proxy"] in output.get("used_tools", []))
        except Exception:
            failed += 1
        n += 1
    return {"tool_selection_proxy_accuracy": correct/n if n else None,
            "failed_interactions": failed, "n_scenarios": n,
            "limitation": "ABCD heuristic mapping; not an end-to-end or customer-authenticated benchmark"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--retrieval-cases", default="data/evaluation/retrieval_gold.jsonl")
    p.add_argument("--abcd-cases", default="data/evaluation/abcd_cases.jsonl")
    p.add_argument("--agent", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--output", default="reports/scenario-evaluation.json")
    args = p.parse_args()
    report = {"created_at": datetime.now(timezone.utc).isoformat()}
    gold = Path(args.retrieval_cases)
    if gold.is_file():
        examples = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
        report["retrieval"] = recall_at_k(examples, 5)
    else:
        report["retrieval"] = {"status": "NOT_EVALUATED", "reason": "No manually annotated gold sources provided"}
    abcd = Path(args.abcd_cases)
    if args.agent and abcd.is_file():
        examples = [json.loads(line) for line in abcd.read_text(encoding="utf-8").splitlines() if line.strip()]
        report["agent"] = agent_selection_proxy(examples, args.limit)
    else:
        report["agent"] = {"status": "NOT_EVALUATED", "reason": "Use --agent after ABCD download and LLM setup"}
    Path("reports").mkdir(exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    try:
        import mlflow
        from app.config import env
        mlflow.set_tracking_uri(env("MLFLOW_TRACKING_URI", "sqlite:///data/mlflow.sqlite3"))
        mlflow.set_experiment("commerceops-agentic-rag")
        with mlflow.start_run(run_name="evaluation"):
            mlflow.log_params({"evaluation_source": "ABCD + human annotated retrieval", "index_backend": "lexical"})
            for group in ("retrieval", "agent"):
                for key, value in report[group].items():
                    if isinstance(value, (int,float)) and not isinstance(value, bool):
                        mlflow.log_metric(f"{group}_{key}", value)
            mlflow.log_artifact(args.output)
    except ImportError:
        print("MLflow not installed (pip install -r requirements-mlops.txt). Raw evaluation JSON saved.")
