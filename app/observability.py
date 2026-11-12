"""Optional sanitized MLflow traces. Never record private chat content or JWTs."""
from contextlib import contextmanager
from contextvars import ContextVar
from app.config import env

current_request = ContextVar("commerceops_request", default="")


@contextmanager
def request_context(request_id):
    token = current_request.set(request_id)
    try:
        yield
    finally:
        current_request.reset(token)

@contextmanager
def sanitized_tool_span(name: str, request_id: str):
    try:
        import mlflow
        if mlflow.get_current_active_span() is None:
            destination = env("MLFLOW_TRACKING_URI", "sqlite:///data/mlflow.sqlite3")
            if mlflow.get_tracking_uri() != destination:
                mlflow.set_tracking_uri(destination)
            mlflow.set_experiment("commerceops-operations")
        context = mlflow.start_span(name=f"tool.{name}")
        span = context.__enter__()
        span.set_attributes({"request_id": request_id, "tool_name": name,
                             "privacy": "no_inputs_no_outputs"})
    except Exception:
        yield None
        return
    try:
        yield span
    finally:
        try:
            context.__exit__(None, None, None)
        except Exception:
            pass
