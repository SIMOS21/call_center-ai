"""Read back a persisted sanitized application trace (one request, one fetch)."""
import json
import argparse
import time
from pathlib import Path
import mlflow
from app.agent import Agent
from app.config import env

mlflow.set_tracking_uri(env("MLFLOW_TRACKING_URI", "sqlite:///data/mlflow.sqlite3"))
parser = argparse.ArgumentParser()
parser.add_argument("--tool", choices=["search_knowledge", "search_products"], default="search_knowledge")
args = parser.parse_args()
start_ms = int(time.time()*1000)
arguments = {"question": "wrong color return"} if args.tool == "search_knowledge" else {"query": ""}
result = Agent()._observed_tool(args.tool, arguments, "", "trace-verification")
trace_id = mlflow.get_last_active_trace_id()
Path("reports/trace-id.txt").write_text(str(trace_id), encoding="utf-8")
mlflow.flush_trace_async_logging()
trace = mlflow.get_trace(trace_id)
assert trace is not None and trace.data.spans
assert trace.info.request_time >= start_ms
serialized = trace.to_json()
assert "Authorization" not in serialized and "Bearer " not in serialized
out = {"trace_id": trace_id, "persisted": True, "spans": [s.name for s in trace.data.spans], "results_found": result.get("found")}
Path("reports/trace-verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
Path(f"reports/trace-{args.tool}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out))
