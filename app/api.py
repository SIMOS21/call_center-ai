"""FastAPI, authenticated Medusa customer actions, mandatory confirmations."""
from __future__ import annotations
import json
import time
import uuid
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from app.agent import Agent, CartItemsArgs
from app.medusa import BackendError, BusinessOutcomeUnknown, Medusa
from app.catalog import CatalogMismatch, batch_snapshot, cart_snapshot, variant_snapshot
from app import storage, rag, conversations, presentation
from app.observability import request_context, sanitized_tool_span

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
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=3000)
    session_id: str | None = Field(default=None, pattern=r"^sess_[A-Za-z0-9_-]{43}$")

class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approval_id: str = Field(min_length=10, max_length=80)
    confirm: bool = False
    session_id: str | None = Field(default=None, pattern=r"^sess_[A-Za-z0-9_-]{43}$")

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
        if env("RAG_BACKEND", "lexical") in ("chroma", "hybrid"):
            index_ready = rag.dense_components()[0].count() > 0
            if env("RAG_BACKEND") == "hybrid":
                index_ready = index_ready and bool(json.loads(path_env("INDEX_FILE", "data/index.json").read_bytes()).get("dense"))
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
        if token or body.session_id:
            token = bearer(authorization)
            try:
                customer_id = medusa.customer(token)["id"]
            except BackendError:
                raise HTTPException(403, "Authentification client refusée") from None
            session_id = body.session_id or conversations.create(customer_id)
            return conversations.respond(agent, body.message, token, customer_id, session_id, request.state.request_id)
        return agent.respond(body.message, token, request_id=request.state.request_id)
    except conversations.SessionMissing:
        raise HTTPException(404, "Session inexistante ou non autorisée") from None
    except conversations.SessionBusy:
        raise HTTPException(409, "Un échange est déjà en cours ; réessayez après sa fin") from None
    except BackendError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.get("/sessions/{session_id}")
def session_state(session_id: str, authorization: str | None = Header(default=None)):
    try:
        customer = medusa.customer(bearer(authorization))
        return conversations.read(session_id, customer["id"])
    except conversations.SessionMissing:
        raise HTTPException(404, "Session inexistante ou non autorisée") from None
    except BackendError:
        raise HTTPException(403, "Authentification client refusée") from None


@api.delete("/sessions/{session_id}")
def reset_session(session_id: str, authorization: str | None = Header(default=None)):
    try:
        customer = medusa.customer(bearer(authorization))
        conversations.reset(session_id, customer["id"])
        return {"status": "reset", "session_id": session_id}
    except conversations.SessionMissing:
        raise HTTPException(404, "Session inexistante ou non autorisée") from None
    except conversations.SessionBusy:
        raise HTTPException(409, "Conversation occupée") from None
    except BackendError:
        raise HTTPException(403, "Authentification client refusée") from None


@api.get("/actions/{approval_id}")
def approval_details(approval_id: str, authorization: str | None = Header(default=None)):
    try:
        customer = medusa.customer(bearer(authorization))
        return conversations.action_details(approval_id, customer["id"])
    except conversations.SessionMissing:
        raise HTTPException(404, "Approbation inexistante ou non autorisée") from None
    except BackendError:
        raise HTTPException(403, "Authentification client refusée") from None


@api.post("/knowledge/search")
def knowledge_search(body: SearchInput, request: Request):
    try:
        result = agent._observed_tool("search_knowledge", {"question": body.question}, "", request.state.request_id)
        if "error" in result:
            raise HTTPException(503, "Recherche indisponible")
        return {"results": result["results"], "request_id": request.state.request_id}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.get("/sessions/{session_id}/cart")
def read_session_cart(session_id: str, request: Request, authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    try:
        customer = medusa.customer(token)
        cart_id = conversations.active_cart(session_id, customer["id"])
        if not cart_id:
            raise HTTPException(404, "Aucun panier associé à cette conversation")
        result = agent._observed_tool("get_cart", {"cart_id": cart_id}, token, request.state.request_id)
        if "error" in result:
            raise HTTPException(503, "Ce panier n'est pas accessible pour le moment")
        return {**result, "answer": presentation.cart_text(result["cart"])}
    except conversations.SessionMissing:
        raise HTTPException(404, "Session inexistante ou non autorisée") from None
    except BackendError:
        raise HTTPException(403, "Authentification client refusée") from None


@api.post("/actions/cancel")
def cancel(body: ApprovalInput, authorization: str | None = Header(default=None)):
    try:
        customer = medusa.customer(bearer(authorization))
        if not body.session_id:
            raise HTTPException(422, "Session requise")
        conversations.cancel_action(body.approval_id, body.session_id, customer["id"])
        return {"status": "cancelled", "message": "Demande annulée. Aucune opération Medusa n'a été exécutée."}
    except conversations.SessionMissing:
        raise HTTPException(404, "Demande non accessible") from None
    except conversations.SessionBusy:
        raise HTTPException(409, "Demande déjà traitée ou échange en cours") from None
    except BackendError:
        raise HTTPException(403, "Authentification client refusée") from None


@api.get("/tickets")
def tickets(authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    try:
        customer = medusa.customer(token)
        return {"tickets": storage.get_tickets(customer["id"])}
    except BackendError as exc:
        raise HTTPException(403, str(exc)) from exc


@api.post("/actions/confirm")
def confirm(body: ApprovalInput, request: Request, authorization: str | None = Header(default=None)):
    request_id = request.state.request_id
    outcome = "error"
    with request_context(request_id), sanitized_tool_span("action_confirmation", request_id) as span:
        try:
            response = confirm_action(body, authorization, request_id)
            payload = response if isinstance(response, dict) else json.loads(response.body)
            value = payload.get("status")
            outcome = value if value in ("done", "needs_review", "awaiting_customer_confirmation") else "unknown"
            return response
        except HTTPException as exc:
            outcome = "refused" if exc.status_code < 500 else "error"
            raise
        finally:
            if span is not None:
                try:
                    span.set_attributes({"approval_status": outcome, "write_completed": outcome == "done"})
                except Exception:
                    pass


def confirm_action(body, authorization, request_id):
    token = bearer(authorization)
    try:
        customer_id = medusa.customer(token)["id"]
        conversations.require_action_session(body.approval_id, customer_id, body.session_id)
        if body.session_id:
            try:
                conversations.action_details(body.approval_id, customer_id, body.session_id)
            except conversations.SessionMissing:
                raise HTTPException(404, "Approbation étrangère à cette session") from None
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
        start = time.perf_counter()
        write_started = False
        target_cart = args.get("cart_id") if approval["kind"] in ("prepare_cart_items", "complete_cart") else None
        try:
            if target_cart and not storage.claim_cart_action(target_cart, body.approval_id, customer_id):
                raise HTTPException(409, "Ce panier fait déjà l'objet d'une opération. Consultez son état avant une nouvelle approbation.")
            if approval["kind"] == "prepare_cart":
                approved = storage.approval_snapshot(body.approval_id)
                current = None
                if approved:
                    products = medusa.products("", product_id=approved["product_id"]).get("products", [])
                    matches = [(p, v) for p in products if p.get("id") == approved["product_id"]
                               for v in p.get("variants", []) if v.get("id") == args["variant_id"]]
                    if len(matches) == 1:
                        current = variant_snapshot(*matches[0])
                if not approved or current != approved:
                    raise HTTPException(409, "Le catalogue a changé ou cette approbation est ancienne. Demandez un nouveau récapitulatif et une nouvelle approbation.")
                write_started = True
                result = medusa.create_cart(args["variant_id"], args["quantity"], token)
            elif approval["kind"] == "prepare_cart_items":
                try:
                    args = CartItemsArgs.model_validate(args).model_dump()
                    current, _ = batch_snapshot(medusa, args["items"], token, args["cart_id"])
                except (CatalogMismatch, ValueError):
                    raise HTTPException(409, "Les articles ne correspondent plus au récapitulatif. Demandez une nouvelle approbation.") from None
                if current != storage.approval_snapshot(body.approval_id):
                    raise HTTPException(409, "Le catalogue ou le panier a changé. Toutes les lignes nécessitent une nouvelle approbation.")
                write_started = True
                result = medusa.apply_cart_items(args["items"], token, args["cart_id"])
                for item, commercial in zip(args["items"], current["variants"]):
                    price = commercial.get("price")
                    if price and price.get("calculated_amount") is not None and item["operation"] != "remove":
                        actual = [line for line in result["cart"]["items"] if line.get("variant_id") == item["variant_id"]]
                        if len(actual) != 1 or actual[0].get("unit_price") != price["calculated_amount"] or result["cart"].get("currency_code") != price.get("currency_code"):
                            raise BusinessOutcomeUnknown("commercial_validation", result.get("cart_id"))
            elif approval["kind"] == "complete_cart":
                current = cart_snapshot(medusa.get_cart(args["cart_id"], token))
                if current != storage.approval_snapshot(body.approval_id):
                    raise HTTPException(409, "Le contenu ou le montant du panier a changé. Une nouvelle approbation est nécessaire.")
                write_started = True
                result = medusa.complete_cart(args["cart_id"], token)
            elif approval["kind"] == "request_return":
                write_started = True
                result = medusa.request_return(args["order_id"], args["items"],
                                               args["shipping_option_id"], args["location_id"], token)
            else:
                raise HTTPException(400, "Action inconnue")
            with storage.conn() as cx:
                cx.execute("UPDATE approvals SET status='done' WHERE id=?", (body.approval_id,))
            try:
                conversations.record_result(body.approval_id, result)
            except Exception:
                pass  # A memory failure must not relabel a successful commerce action.
            storage.audit(request_id, approval["kind"], "confirmed_action", True,
                          (time.perf_counter()-start)*1000)
            return {"status": "done", "kind": approval["kind"], "result": result,
                    "customer_message": presentation.action_text(approval["kind"], result)}
        except BusinessOutcomeUnknown as exc:
            if exc.result.get("cart_id"):
                target_cart = exc.result["cart_id"]
                storage.claim_cart_action(target_cart, body.approval_id, customer_id)
            with storage.conn() as cx:
                cx.execute("UPDATE approvals SET status='needs_review' WHERE id=?", (body.approval_id,))
            conversations.record_result(body.approval_id, exc.result)
            storage.audit(request_id, approval["kind"], "confirmed_action", False,
                          (time.perf_counter()-start)*1000, "business_outcome_unknown")
            from fastapi.responses import JSONResponse
            message = ("Le panier existe, mais l'ajout de l'article n'est pas confirmé. Consultez le panier ou contactez un conseiller. Ne relancez pas cette création."
                       if exc.result.get("cart_id") else
                       "La réponse de création n'a pas été confirmée. Un panier peut exister. Demandez une vérification à un conseiller avant toute nouvelle création.")
            if approval["kind"] == "prepare_cart_items" and exc.result.get("cart_id"):
                message = "Le panier existe, mais l'application de toutes les modifications n'est pas confirmée. Consultez son contenu ou contactez un conseiller. Cette opération ne sera pas réexécutée automatiquement."
            return JSONResponse(status_code=202, content={"status": "needs_review", "kind": approval["kind"],
                                                        "result": exc.result, "customer_message": message})
        except Exception as exc:
            # Revalidation happens before any write. Later failures can be uncertain.
            status = "needs_review" if write_started else "verification_failed"
            if isinstance(exc, HTTPException) and exc.status_code == 409:
                status = "invalidated"
            with storage.conn() as cx:
                cx.execute("UPDATE approvals SET status=? WHERE id=?", (status, body.approval_id))
            storage.audit(request_id, approval["kind"], "confirmed_action", False,
                          (time.perf_counter()-start)*1000, type(exc).__name__)
            raise
        finally:
            final = storage.get_approval(body.approval_id, customer_id)
            if target_cart and final and final["status"] not in ("confirmed", "needs_review"):
                storage.release_cart_action(target_cart, body.approval_id)
    except BackendError as exc:
        raise HTTPException(502, str(exc)) from exc


@api.get("/metrics")
def metrics():
    return storage.metrics()
