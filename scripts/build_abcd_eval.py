"""Extract reproducible *real* ABCD customer utterances for a coarse evaluation set.

ABCD is research dialogue, not live production conversations. Flow categories are a
proxy label for selecting general tool types, NOT ground-truth end-to-end correctness.
"""
from __future__ import annotations
import gzip
import json
import random
from pathlib import Path

DATA = Path("data/raw/abcd/abcd_v1.1.json.gz")
OUTPUT = Path("data/evaluation/abcd_cases.jsonl")


def expected_for(flow: str) -> str:
    f = flow.lower()
    if "return" in f or "refund" in f or "product defect" in f:
        return "search_knowledge"
    if "shipping" in f or "order" in f or "delivery" in f:
        return "get_order_status"
    if "product" in f or "out of stock" in f or "item" in f:
        return "search_products"
    return "search_knowledge"


if __name__ == "__main__":
    if not DATA.is_file():
        raise SystemExit("Download ABCD first: python scripts/collect_real_sources.py --abcd")
    with gzip.open(DATA, "rt", encoding="utf-8") as handle:
        dataset = json.load(handle)
    random.seed(2026)
    cases = []
    splits = [(name, data) for name, data in dataset.items() if isinstance(data, list)]
    for split, conversations in splits:
        for conv in conversations:
            flow = conv.get("scenario", {}).get("flow", "")
            turns = conv.get("original", [])
            first_customer = None
            for turn in turns:
                if isinstance(turn, dict):
                    if str(turn.get("speaker", "")).lower() == "customer":
                        first_customer = turn.get("text", "")
                        break
                elif isinstance(turn, (list, tuple)) and len(turn) > 1 and str(turn[0]).lower() == "customer":
                    first_customer = turn[1]
                    break
            if first_customer and len(str(first_customer)) >= 15:
                cases.append({"case_id": str(conv.get("convo_id", "")), "split": split,
                              "input": str(first_customer)[:500], "flow": str(flow),
                              "expected_tool_family_proxy": expected_for(str(flow)),
                              "source": "https://github.com/asappresearch/abcd"})
    if not cases:
        raise SystemExit("ABCD structure unexpected; inspect actual dataset before evaluation")
    sample = random.sample(cases, min(100, len(cases)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in sample) + "\n", encoding="utf-8")
    print("Prepared", len(sample), "real-source scenario prompts; expected tools are heuristic PROXIES.")
