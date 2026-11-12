"""FastAPI, authenticated Medusa customer actions, mandatory confirmations."""
from __future__ import annotations
import json
import time
import uuid
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from app.agent import Agent
from app.medusa import BackendError, Medusa
from app import storage, rag

api = FastAPI(title="CommerceOps AI", version="0.1.0", description="Agentic e-commerce support (independent academic demo)")
medusa = Medusa()
agent = Agent(medusa)


@api.middleware("http")
async def observe_request(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request.state.request_id
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unknown")
        storage.http_request(request.state.request_id, route, request.method, status,
                             (time.perf_counter()-start)*1000)


class ChatInput(BaseModel):
    message: str = Field(min_length=3, max_length=3000)

class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approval_id: str = Field(min_length=10, max_length=80)
    confirm: bool = False

class SearchInput(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


def bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token du client Medusa requis")
    return authorization[7:]


@api.get("/health")
def health():
    # No claim that remote services are ready when they're not.
    from app.config import path_env, env
    try:
        if env("RAG_BACKEND", "lexical") == "chroma":
            index_ready = rag.dense_components()[0].count() > 0
        else:
            index_ready = bool(rag.load_index(str(path_env("INDEX_FILE", "data/index.json")))[0])
    except Exception:
        index_ready = False
    return {"api": "ok", "medusa_reachable": medusa.health(),
            "index_available": index_ready,
            "llm_configured": bool(agent.key)}


@api.post("/chat")
def chat(body: ChatInput, request: Request, authorization: str | None = Header(default=None)):
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    try:
        return agent.respond(body.message, token, request_id=request.state.request_id)
    except BackendError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.post("/knowledge/search")
def knowledge_search(body: SearchInput, request: Request):
    try:
        result = agent._observed_tool("search_knowledge", {"question": body.question}, "", request.state.request_id)
        if "error" in result:
            raise HTTPException(503, "Recherche indisponible")
        return {"results": result["results"], "request_id": request.state.request_id}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.get("/tickets")
def tickets(authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    try:
        customer = medusa.customer(token)
        return {"tickets": storage.get_tickets(customer["id"])}
    except BackendError as exc:
        raise HTTPException(403, str(exc)) from exc


@api.post("/actions/confirm")
def confirm(body: ApprovalInput, authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    try:
        customer_id = medusa.customer(token)["id"]
        approval = storage.get_approval(body.approval_id, customer_id)
        if not approval:
            raise HTTPException(404, "Validation inexistante ou non autorisée")
        if approval["status"] != "pending":
            raise HTTPException(409, "Demande déjà traitée")
        if not body.confirm:
            # No state change without positive consent.
            return {"status": "awaiting_customer_confirmation", "kind": approval["kind"]}
        if not storage.mark_approval(body.approval_id, customer_id):
            raise HTTPException(409, "Cette action est déjà en cours")
        args = json.loads(approval["arguments_json"])
        request_id = uuid.uuid4().hex
        start = time.perf_counter()
        try:
            if approval["kind"] == "prepare_cart":
                result = medusa.create_cart(args["variant_id"], args["quantity"], token)
            elif approval["kind"] == "complete_cart":
                result = medusa.complete_cart(args["cart_id"], token)
            elif approval["kind"] == "request_return":
                result = medusa.request_return(args["order_id"], args["items"],
                                               args["shipping_option_id"], args["location_id"], token)
            else:
                raise HTTPException(400, "Action inconnue")
            with storage.conn() as cx:
                cx.execute("UPDATE approvals SET status='done' WHERE id=?", (body.approval_id,))
            storage.audit(request_id, approval["kind"], "confirmed_action", True,
                          (time.perf_counter()-start)*1000)
            return {"status": "done", "result": result}
        except Exception as exc:
            # Failed is not retried silently: prevents duplicate financial operations.
            with storage.conn() as cx:
                cx.execute("UPDATE approvals SET status='failed' WHERE id=?", (body.approval_id,))
            storage.audit(request_id, approval["kind"], "confirmed_action", False,
                          (time.perf_counter()-start)*1000, type(exc).__name__)
            raise
    except BackendError as exc:
        raise HTTPException(502, str(exc)) from exc


@api.get("/metrics")
def metrics():
    return storage.metrics()
