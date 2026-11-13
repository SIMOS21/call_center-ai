"""Live public development answer checks; no personal input or frozen final."""
import hashlib
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import env, path_env
from scripts.evaluate_global_v2 import DEVELOPMENT, NEGATIVES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/rag-format/answers-development.json")
    args = parser.parse_args()
    index = path_env("INDEX_FILE", "data/index.json")
    chunks = {r["id"]: r for r in json.loads(index.read_bytes())["chunks"]}
    cases = []
    for identity, question, expected in DEVELOPMENT + [("NEG" + str(i), q, None) for i, q in enumerate(NEGATIVES)]:
        start = time.perf_counter()
        response = requests.post("http://127.0.0.1:8001/chat", json={"message": question}, timeout=100)
        response.raise_for_status()
        result = response.json()
        elapsed = (time.perf_counter()-start)*1000
        evidence = result.get("evidence", [])
        quotes_attested = all(any(c in chunks and f["quote"] in chunks[c]["content"] for c in f["chunk_ids"]) for f in evidence)
        if "answer_units" in result:
            units = result["answer_units"]
            ids = {e["id"] for e in evidence}
            attested = quotes_attested and all(u["text"] in result["answer"] and set(u["fact_ids"]).issubset(ids) for u in units)
        else:
            attested = quotes_attested and all(f["text"] in result["answer"] for f in evidence)
        cited_correctly = bool(result.get("sources")) and all(s["title"].endswith("/ " + expected) for s in result["sources"]) if expected else not result.get("sources")
        correct = bool(evidence) and attested and cited_correctly if expected else bool(result.get("abstained"))
        cases.append({"id": identity, "question": question, "expected_subflow": expected, "answer": result["answer"],
                      "sources": result.get("sources"), "evidence": evidence, "latency_http_ms": elapsed,
                      "exact_quote_and_claim_plan_checks": attested, "citation_matches_development_label": cited_correctly,
                      "expected_behavior_passed": correct, "abstained": result.get("abstained"),
                      "source_found": result.get("source_found"), "source_relevant": result.get("source_relevant"),
                      "source_supports_answer": result.get("source_supports_answer"), "generation": result.get("generation"), "usage": result.get("usage")})
    positives = [c for c in cases if c["expected_subflow"]]
    negatives = [c for c in cases if not c["expected_subflow"]]
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "split": "development_seen_not_independent",
              "annotations": "Agent verified source text and code translations, no human semantic annotation review",
              "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(), "model": env("LLM_MODEL"),
              "positive_n": len(positives), "citation_correct": sum(c["citation_matches_development_label"] for c in positives),
              "positive_abstention_count": sum(bool(c["abstained"]) for c in positives),
              "evidence_n": sum(len(c["evidence"]) for c in cases),
              "exact_quote_and_claim_plan_checks_passed": sum(c["exact_quote_and_claim_plan_checks"] for c in positives),
              "negative_n": len(negatives), "correct_abstention_count": sum(bool(c["abstained"]) for c in negatives),
              "latency_http_mean_ms": statistics.mean(c["latency_http_ms"] for c in cases),
              "token_usage_available_n": sum(c["usage"] is not None for c in cases), "monetary_cost": None,
              "human_fidelity": {"n": 0, "status": "NOT_EVALUATED"}, "cases": cases}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Development answers:", sum(c["expected_behavior_passed"] for c in cases), "/", len(cases), "exact excerpt checks, not human semantic fidelity")
    return int(not all(c["expected_behavior_passed"] for c in cases))


if __name__ == "__main__":
    raise SystemExit(main())
