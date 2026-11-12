"""Fail closed on missing, empty, nonfinite or regressing benchmark results."""
import argparse
import json
import math
from pathlib import Path


def check_results(results, baseline):
    checks = baseline.get("checks")
    if not isinstance(checks, dict) or not checks:
        return ["At least one documented quality check is required"]
    errors = []
    if not baseline.get("justification"):
        errors.append("Baseline justification is required")
    for metric, config in checks.items():
        try:
            group, key = metric.split(".", 1)
            observed = results[group][key]
            reference = config["baseline"]
            drop = config.get("max_drop", 0)
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (observed, reference, drop)) or drop < 0:
                raise ValueError("Finite numeric scores required")
            direction = config.get("direction", "min")
            if direction not in ("min", "max"):
                raise ValueError("Invalid direction")
            if (direction == "min" and observed < reference-drop) or (direction == "max" and observed > reference+drop):
                errors.append(f"Regression {metric}: observed={observed}, baseline={reference}")
        except (KeyError, TypeError, ValueError):
            errors.append(f"Missing or invalid score/baseline: {metric}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="reports/evaluation.json")
    parser.add_argument("--baseline", default="docs/quality_baseline.json")
    args = parser.parse_args()
    try:
        results = json.loads(Path(args.results).read_text(encoding="utf-8-sig"))
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8-sig"))
        errors = check_results(results, baseline)
    except (OSError, ValueError):
        errors = ["Evaluation and documented baseline are required"]
    print("QUALITY GATE", "FAIL" if errors else "PASS")
    for error in errors:
        print(error)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
