"""Seal a new, unevaluated retrieval split and require explicit human review."""
import hashlib
import json
from pathlib import Path


def validate_review(path, review_path):
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if not (review.get("approved") is True and review.get("reviewer") and review.get("reviewed_at") and review.get("dataset_sha256") == digest):
        raise ValueError("Final evaluation blocked: human review of this exact SHA is required")
    return review


def main():
    path = Path("evaluation/final-v3.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    previous = set()
    for prior in ("evaluation/retrieval_cases.jsonl", "evaluation/final_cases.jsonl"):
        previous.update(json.loads(line)["question"] for line in Path(prior).read_text(encoding="utf-8-sig").splitlines() if line)
    assert not previous.intersection(case["question"] for case in cases)
    target = Path("evaluation/final-v3.review.json")
    if target.exists():
        raise SystemExit("Review seal already exists; do not overwrite an existing review")
    target.write_text(json.dumps({"dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "n": len(cases),
                                  "reviewer": None, "reviewed_at": None, "approved": False,
                                  "status": "FROZEN_NOT_EVALUATED", "human_faithfulness": "NOT_EVALUATED",
                                  "instruction": "Review questions, actual source passages and abstention labels; do not tune on this set."}, indent=2), encoding="utf-8")
    print("Frozen 16 new cases. No final retrieval or agent evaluation performed.")


if __name__ == "__main__":
    main()
