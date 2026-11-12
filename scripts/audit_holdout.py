"""Freeze distinct draft cases; measure retrieval, never invent human review."""
import hashlib
import json
import statistics
import time
from pathlib import Path
from app import rag


def main():
    source = Path("evaluation/final_cases.jsonl")
    cases = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line]
    previous = [json.loads(line)["question"] for line in Path("evaluation/retrieval_cases.jsonl").read_text(encoding="utf-8-sig").splitlines() if line]
    assert not set(previous) & {row["question"] for row in cases}
    target = Path("data/evaluation/manual_gold.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {"dataset_sha256": digest, "cases": len(cases), "status": "DRAFT_NOT_HUMAN_REVIEWED", "independent_validated": False, "retrieval": [],
              "agent": {"status": "NOT_EVALUATED", "n": 0, "reason": "Rotation and human-reviewed labels required"},
              "task_success": {"status": "NOT_EVALUATED", "n": 0},
              "citation_faithfulness": {"status": "HUMAN_REVIEW_REQUIRED", "n": 0}}
    annotated = [c for c in cases if c.get("flow")]
    for backend in ("lexical", "chroma"):
        hits, latency, rows = 0, [], []
        for case in annotated:
            expected = "https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json#flow=" + case["flow"] + "&subflow=" + case["subflow"]
            if backend == "lexical":
                search = rag.lexical_search
            else:
                import os
                os.environ["RAG_BACKEND"] = "chroma"
                search = rag.search
            search(case["question"])
            start = time.perf_counter()
            result = search(case["question"])
            latency.append((time.perf_counter()-start)*1000)
            hit = any(r["source"] == expected for r in result)
            hits += hit
            rows.append({"case_id": case["id"], "hit": hit, "expected_source": expected, "sources": [r["source"] for r in result]})
        report["retrieval"].append({"backend": backend, "n": len(annotated), "recall_at_5": hits/len(annotated), "mean_ms": statistics.mean(latency), "p95_ms": sorted(latency)[int(.95*(len(latency)-1))], "cases": rows})
    Path("reports/final-audit/holdout-draft.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    review = {"dataset_sha256": digest, "reviewer": None, "reviewed_at": None, "approved": False, "instructions": "Human must review all expected labels, documentary excerpts and authorization behavior before independent evaluation."}
    review_path = Path("evaluation/manual_gold.review.json")
    if not review_path.exists():
        review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "cases": len(cases), "sha256": digest, "retrieval_n": len(annotated)}))


if __name__ == "__main__":
    main()
