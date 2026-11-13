"""Customer-bound durable conversations; only canonical, allowlisted memory.

Raw user/assistant/tool payloads and bearer tokens are never persisted here.
Chat consent can prepare an approval, but never executes a commerce mutation.
"""
import json
import re
import secrets
import time
from contextlib import contextmanager

from app import storage, shopping
from app.interpreter import AFFIRMATIVES, normalized, shopping_preferences, interpret, split_requests

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, state_json TEXT NOT NULL,
 history_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
 busy_until REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_approvals (
 approval_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, details_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_action_results (
 approval_id TEXT PRIMARY KEY, references_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_session_carts (
 session_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, cart_id TEXT NOT NULL,
 approval_id TEXT NOT NULL);
"""


class SessionMissing(Exception):
    pass


class SessionBusy(Exception):
    pass


def connection():
    return storage.conn()


def initialize(cx):
    cx.executescript(SCHEMA)


def empty_state():
    return {"products": [], "product_id": None, "variant_id": None,
            "size": None, "color": None, "quantity": 1, "intent": "browse",
            "awaiting_prepare": False, "pending_actions": [], "schema_version": 2,
            "draft_items": [], "selected_line": None}


def create(customer_id):
    session_id = "sess_" + secrets.token_urlsafe(32)
    with connection() as cx:
        initialize(cx)
        cx.execute("INSERT INTO chat_sessions (id,customer_id,state_json,history_json,created_at) VALUES (?,?,?,?,?)",
                   (session_id, customer_id, json.dumps(empty_state()), "[]", storage.now()))
    return session_id


def read(session_id, customer_id):
    with connection() as cx:
        initialize(cx)
        row = cx.execute("SELECT * FROM chat_sessions WHERE id=? AND customer_id=?", (session_id, customer_id)).fetchone()
    if not row:
        raise SessionMissing()
    return {"session_id": row["id"], "state": shopping.migrate(json.loads(row["state_json"])),
            "history": json.loads(row["history_json"]), "version": row["version"]}


@contextmanager
def turn(session_id, customer_id):
    with connection() as cx:
        initialize(cx)
        update = cx.execute("UPDATE chat_sessions SET busy_until=?,version=version+1 WHERE id=? AND customer_id=? AND busy_until<?",
                            (time.time()+900, session_id, customer_id, time.time()))
        if update.rowcount != 1:
            exists = cx.execute("SELECT 1 FROM chat_sessions WHERE id=? AND customer_id=?", (session_id, customer_id)).fetchone()
            if not exists:
                raise SessionMissing()
            raise SessionBusy()
        row = cx.execute("SELECT * FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
    snapshot = {"state": json.loads(row["state_json"]), "history": json.loads(row["history_json"])}
    try:
        yield snapshot
        with connection() as cx:
            updated = cx.execute("UPDATE chat_sessions SET state_json=?,history_json=?,busy_until=0 WHERE id=? AND customer_id=? AND version=?",
                                 (json.dumps(snapshot["state"], ensure_ascii=False), json.dumps(snapshot["history"][-40:], ensure_ascii=False), session_id, customer_id, row["version"]))
            if updated.rowcount != 1:
                raise SessionBusy()
    finally:
        with connection() as cx:
            cx.execute("UPDATE chat_sessions SET busy_until=0 WHERE id=? AND customer_id=? AND version=?", (session_id, customer_id, row["version"]))


def cancel_pending(state, customer_id):
    survivors = []
    with connection() as cx:
        for action in state["pending_actions"]:
            cx.execute("UPDATE approvals SET status='cancelled' WHERE id=? AND customer_id=? AND status='pending'", (action["approval_id"], customer_id))
            row = cx.execute("SELECT status FROM approvals WHERE id=? AND customer_id=?", (action["approval_id"], customer_id)).fetchone()
            if row and row[0] in ("confirmed", "needs_review"):
                survivors.append(action)
    state["pending_actions"] = survivors
    state["awaiting_prepare"] = False
    return not survivors


def reset(session_id, customer_id):
    with turn(session_id, customer_id) as snapshot:
        cancel_pending(snapshot["state"], customer_id)
        snapshot["state"] = empty_state()
        snapshot["history"] = []
    with connection() as cx:
        cx.execute("DELETE FROM chat_session_carts WHERE session_id=? AND customer_id=?", (session_id, customer_id))


def action_details(approval_id, customer_id, session_id=None):
    approval = storage.get_approval(approval_id, customer_id)
    if not approval:
        raise SessionMissing()
    with connection() as cx:
        initialize(cx)
        row = cx.execute("SELECT * FROM chat_approvals WHERE approval_id=?", (approval_id,)).fetchone()
    if session_id:
        read(session_id, customer_id)
        if not row or row["session_id"] != session_id:
            raise SessionMissing()
    return {"approval_id": approval_id, "kind": approval["kind"], "status": approval["status"],
            "arguments": json.loads(approval["arguments_json"]),
            "details": json.loads(row["details_json"]) if row else (storage.approval_snapshot(approval_id) or {})}


def require_action_session(approval_id, customer_id, session_id):
    # Legacy approvals retain their API contract; chat approvals require context.
    from fastapi import HTTPException
    with connection() as cx:
        initialize(cx)
        linked = cx.execute("SELECT session_id FROM chat_approvals WHERE approval_id=?", (approval_id,)).fetchone()
    if linked:
        try:
            if not session_id or linked[0] != session_id:
                raise SessionMissing()
            read(session_id, customer_id)
        except SessionMissing:
            raise HTTPException(404, "Approbation étrangère à cette session") from None


def record_result(approval_id, result):
    # Explicit reference allowlist: never persist a full cart/customer/address.
    references = {key: result[key] for key in ("cart_id", "order_id", "return_id", "status") if isinstance(result.get(key), str)}
    with connection() as cx:
        initialize(cx)
        cx.execute("INSERT OR REPLACE INTO chat_action_results VALUES (?,?)", (approval_id, json.dumps(references)))
        link = cx.execute("SELECT s.id,s.customer_id,s.state_json FROM chat_sessions s JOIN chat_approvals a ON a.session_id=s.id JOIN approvals p ON p.id=a.approval_id AND p.customer_id=s.customer_id WHERE a.approval_id=? AND p.kind IN ('prepare_cart','prepare_cart_items') AND p.status IN ('done','needs_review')", (approval_id,)).fetchone()
        if link and result.get("cart_id") and any(a["approval_id"] == approval_id for a in json.loads(link["state_json"]).get("pending_actions", [])):
            cx.execute("INSERT OR REPLACE INTO chat_session_carts VALUES (?,?,?,?)", (link["id"], link["customer_id"], result["cart_id"], approval_id))


def active_cart(session_id, customer_id):
    read(session_id, customer_id)
    with connection() as cx:
        row = cx.execute("SELECT cart_id FROM chat_session_carts WHERE session_id=? AND customer_id=?", (session_id, customer_id)).fetchone()
    return row[0] if row else None


def cancel_action(approval_id, session_id, customer_id):
    require_action_session(approval_id, customer_id, session_id)
    action_details(approval_id, customer_id, session_id)
    with turn(session_id, customer_id) as snapshot:
        with connection() as cx:
            changed = cx.execute("UPDATE approvals SET status='cancelled' WHERE id=? AND customer_id=? AND status='pending'", (approval_id, customer_id))
            if changed.rowcount != 1:
                raise SessionBusy()
        snapshot["state"]["pending_actions"] = [a for a in snapshot["state"]["pending_actions"] if a["approval_id"] != approval_id]
        snapshot["state"]["awaiting_prepare"] = False


def cancellation_requested(text):
    if re.search(r"n[' ]?annul\w*\s+pas|ne veux pas annuler|sans annuler", text):
        return False
    if re.search(r"finalement|plutot|prefere|prends", text) and not re.search(r"\bannul(?:e|ez)\b", text):
        size, quantity = shopping_preferences(text)
        if size or quantity is not None:
            return False
    return text in ("non", "no", "non merci", "laisse tomber", "annule", "j'ai change d'avis") or bool(re.search(
        r"\bannul(?:e|ez)\b|\bje ne veux plus\b|\bje veux arreter\b|\barrete(?:z)?\s+(?:la preparation|la demande)", text))


def cancel_preparation(state, customer_id, session_id):
    survivors = []
    statuses = []
    for action in state["pending_actions"]:
        action_details(action["approval_id"], customer_id, session_id)
    with connection() as cx:
        for action in state["pending_actions"]:
            cx.execute("UPDATE approvals SET status='cancelled' WHERE id=? AND customer_id=? AND status='pending'", (action["approval_id"], customer_id))
            row = cx.execute("SELECT status FROM approvals WHERE id=? AND customer_id=?", (action["approval_id"], customer_id)).fetchone()
            statuses.append(row[0])
            if row[0] != "cancelled":
                survivors.append(action)
    state.update(pending_actions=survivors, awaiting_prepare=False, intent="browse")
    if "confirmed" in statuses:
        return "La demande est déjà en cours de traitement. Son annulation n'est pas confirmée. Consultez son état ou demandez l'aide d'un conseiller."
    if "needs_review" in statuses:
        return "Une opération précédente reste à vérifier auprès de la boutique. Consultez le panier ou un conseiller avant toute nouvelle création."
    state.update(draft_items=[], selected_line=None)
    if active_cart(session_id, customer_id):
        return "Le panier déjà confirmé reste associé à cette conversation. Cette demande n'a pas modifié son contenu. Vous pouvez le consulter. Les préparations encore en attente sont annulées."
    if "done" in statuses:
        return "L'opération a déjà été confirmée par la boutique. Cette demande n'a pas exécuté son annulation. Consultez son état ou contactez un conseiller."
    if "cancelled" in statuses:
        return "La préparation de votre panier est annulée. L'approbation annulée ne peut plus être confirmée."
    return "La proposition de panier est abandonnée. Aucune approbation n'est en attente dans cette conversation."


def sensitive(text):
    return bool(re.search(r"nvapi-|gsk_|\bBearer\s|\beyJ[\w-]+\.[\w-]+\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:password|mot de passe|api.key|secret)\s*[:=]|\b[A-Z]{2}\d{2}[A-Z0-9]{12,}|\b\d{12,19}\b|\b\d+\s+(?:rue|avenue|street|boulevard)\b", text, re.I))


def label(text):
    return str(text)[:120] if isinstance(text, str) and not sensitive(text) else "libellé masqué"


def safe_products(products):
    result = []
    for product in products:
        if not re.fullmatch(r"[\w-]{3,100}", str(product.get("id", ""))):
            continue
        variants = [{"id": v["id"], "title": label(v.get("title", "")),
                     "options": [{"title": label(o.get("title", "")), "value": label(o.get("value", ""))} for o in v.get("options", [])],
                     "price": v.get("price")} for v in product.get("variants", [])
                    if re.fullmatch(r"[\w-]{3,100}", str(v.get("id", "")))]
        result.append({"id": product["id"], "title": label(product.get("title", "")), "variants": variants,
                       "type": label(product["type"]) if product.get("type") else None,
                       "categories": [label(value) for value in product.get("categories", [])]})
    return result


def selection(state):
    product = next((p for p in state["products"] if p["id"] == state["product_id"]), None)
    variant = next((v for v in product["variants"] if v["id"] == state["variant_id"]), None) if product else None
    return product, variant


def memory_messages(state):
    product, variant = selection(state)
    # Both messages are canonical facts generated by the server, not raw chat text.
    memory = {"intent": state["intent"], "product": product["title"] if product else None,
              "product_id": product["id"] if product else None,
              "variant": variant["title"] if variant else None, "quantity": state["quantity"],
              "variant_id": variant["id"] if variant else None,
              "last_action": state.get("last_action"),
              "draft_items": [{key: item.get(key) for key in ("product", "product_id", "variant", "variant_id", "quantity", "operation")}
                              for item in state.get("draft_items", [])],
              "last_order": state.get("last_order"),
              "pending_actions": [{"approval_id": a["approval_id"], "kind": a["kind"]} for a in state["pending_actions"]]}
    return [{"role": "user", "content": "Contexte validé : " + json.dumps(memory, ensure_ascii=False)},
            {"role": "assistant", "content": "Mémoire serveur uniquement ; aucune exécution déduite du consentement conversationnel."}]


def remember(snapshot):
    snapshot["history"].extend(memory_messages(snapshot["state"]))


def respond(agent, message, token, customer_id, session_id, request_id):
    start = time.perf_counter()
    if normalized(message) in ("reset", "recommencer", "nouvelle conversation"):
        reset(session_id, customer_id)
        return {"session_id": session_id, "request_id": request_id, "answer": "Conversation réinitialisée ; les approbations en attente sont annulées.", "tool_calls": 0, "used_tools": [], "latency_ms": 0, "pending_actions": []}
    with turn(session_id, customer_id) as snapshot:
        state = shopping.migrate(snapshot["state"])
        text = normalized(message)
        plan = interpret(message, bool(state["product_id"] or state.get("discussion")), state.get("intent"))
        documentary_context = None
        used = []
        for action in state["pending_actions"]:
            approved = storage.get_approval(action["approval_id"], customer_id)
            if approved and approved["status"] == "done":
                with connection() as cx:
                    row = cx.execute("SELECT references_json FROM chat_action_results WHERE approval_id=?", (action["approval_id"],)).fetchone()
                state["last_action"] = {"kind": action["kind"], "status": "done", **(json.loads(row[0]) if row else {})}
                if state.get("last_applied_draft") != action["approval_id"]:
                    state.update(draft_items=[], selected_line=None, awaiting_prepare=False,
                                 last_applied_draft=action["approval_id"])

        def remember_documentary(output):
            if "source_supports_answer" in output:
                state["last_documentary_question"] = output["documentary_topic"]
                state["last_verified_sources"] = output.get("sources", [])
                state["last_search_outcome"] = {key: output[key] for key in ("source_found", "source_relevant", "source_supports_answer")}
                state["last_search_outcome"]["retrieval_available"] = output.get("retrieval_available", True)
                state.update(intent="documentary", awaiting_prepare=False)

        def finish(answer, actions=None):
            remember(snapshot)
            product, variant = selection(state)
            if plan.mixed_scope:
                from app.interpreter import SCOPE_MESSAGE
                answer += "\n\n" + SCOPE_MESSAGE
            return {"session_id": session_id, "request_id": request_id, "answer": answer,
                    "tool_calls": len(used), "used_tools": used, "latency_ms": round((time.perf_counter()-start)*1000),
                    "pending_actions": actions or [], "source_checked": False, "generation": "conversation_state",
                    "intents": list(plan.intents), "draft_selection": shopping.public_draft(state),
                    "product_selection": {"title": product["title"], "variant": variant["title"] if variant else None,
                                          "quantity": state["quantity"], "availability": "not_checked",
                                          "price": variant.get("price") if variant else None} if product and state["awaiting_prepare"] else None}

        if sensitive(message):
            return finish("Ne partagez pas de secret, mot de passe, adresse ou coordonnées personnelles dans le chat. Ce contenu n'a pas été conservé ni transmis au modèle.")
        from app.agent import needs_reference
        if plan.has("unauthorized", "financial_refund", "out_of_scope"):
            from app.interpreter import ACCESS_MESSAGE, REFUND_MESSAGE, SCOPE_MESSAGE
            answers = {"unauthorized": ACCESS_MESSAGE, "financial_refund": REFUND_MESSAGE, "out_of_scope": SCOPE_MESSAGE}
            return finish(answers[plan.intents[0]])
        clauses = split_requests(message)
        if plan.has("documentary") and len(clauses) > 1:
            answers, extra, business_results = [], {}, []
            for clause in clauses:
                subplan = interpret(clause, bool(state["product_id"]), state.get("intent"))
                if subplan.has("out_of_scope"):
                    continue
                if subplan.has("catalogue", "selection", "price") and not subplan.has("documentary", "orders", "support"):
                    if not cancel_pending(state, customer_id):
                        answers.append("Une opération est en cours ou incertaine. Le brouillon commercial attend sa vérification.")
                        continue
                    output = agent._observed_tool("search_products", {"query": ""}, token, request_id)
                    used.append("search_products")
                    if "error" in output:
                        state["awaiting_prepare"] = False
                        answers.append("Le catalogue est indisponible. Aucune sélection ne peut être confirmée.")
                    else:
                        state["products"] = safe_products(output.get("products", []))
                        answers.append(shopping.update_selection(state, clause, state["products"], subplan))
                elif cancellation_requested(normalized(clause)):
                    answers.append(cancel_preparation(state, customer_id, session_id))
                else:
                    output = agent.respond(clause, token, request_id=request_id)
                    used.extend(output.get("used_tools", []))
                    business_results.extend(output.get("business_results", []))
                    answers.append(output["answer"])
                    remember_documentary(output)
                    if "source_supports_answer" in output:
                        extra = {key: value for key, value in output.items() if key not in ("answer", "request_id", "latency_ms", "used_tools", "tool_calls", "pending_actions")}
            result = finish("\n\n".join(answers))
            result.update(extra)
            result["business_results"] = business_results
            result["intents"] = list(plan.intents)
            return result
        if cancellation_requested(text) and plan.operation != "remove" and not plan.has("orders"):
            return finish(cancel_preparation(state, customer_id, session_id))
        if plan.has("cart") and plan.operation in ("set", "remove"):
            cart_id = active_cart(session_id, customer_id)
            if not cart_id:
                return finish("Aucun panier confirmé n'est associé à cette conversation. Précisez une sélection pour préparer un panier.")
            if storage.cart_action_locked(cart_id):
                return finish("Ce panier fait l'objet d'une opération en cours ou incertaine. Consultez son état auprès d'un conseiller avant de préparer une modification.")
            cart_result = agent._observed_tool("get_cart", {"cart_id": cart_id}, token, request_id)
            used.append("get_cart")
            products_result = agent._observed_tool("search_products", {"query": ""}, token, request_id)
            used.append("search_products")
            if "error" in cart_result or "error" in products_result:
                return finish("La ligne du panier ne peut pas être vérifiée pour le moment. Réessayez la consultation auprès de la boutique.")
            if not cancel_pending(state, customer_id):
                return finish("Une opération est en cours ou incertaine. Attendez sa vérification avant de modifier le brouillon.")
            state["products"] = safe_products(products_result.get("products", []))
            return finish(shopping.edit_cart_draft(state, message, cart_result["cart"], state["products"], plan))
        if not plan.has("support") and not needs_reference(message) and re.search(r"\bpanier\b", text) and not re.search(r"ajout|prepar|creer|finalis|payer|annul|vider|valider|confirmer", text):
            cart_id = active_cart(session_id, customer_id)
            if not cart_id:
                return finish("Je n'ai pas de panier confirmé associé à cette conversation. Choisissez un produit pour en préparer un, ou vérifiez que vous êtes connecté au bon compte.")
            output = agent._observed_tool("get_cart", {"cart_id": cart_id}, token, request_id)
            used.append("get_cart")
            if "error" in output:
                return finish("Ce panier n'est pas accessible pour le moment. Réessayez la consultation ou demandez l'aide d'un conseiller.")
            from app.presentation import cart_text
            result = finish(cart_text(output["cart"]))
            result["cart"] = output["cart"]
            return result
        from app.documentary_format import is_format_followup
        from app.documentary import relevant_source
        if is_format_followup(message) and not plan.has("orders", "cart", "price") and "last_search_outcome" in state and relevant_source(message, {"title": state["last_documentary_question"]}):
            if not state["last_search_outcome"].get("source_supports_answer"):
                if not state["last_search_outcome"].get("retrieval_available", True):
                    return finish("La recherche précédente était indisponible. Je ne peux pas résumer une procédure dont les sources n'ont pas été consultées. Réessayez la recherche ou contactez un conseiller.")
                return finish("Aucune procédure pertinente n'a été trouvée lors de votre demande précédente. Je n'ai donc aucune procédure vérifiée à résumer. Pouvez-vous préciser une autre référence ?")
            documentary_context = {"topic": state["last_documentary_question"], "sources": state["last_verified_sources"]}
        if text in AFFIRMATIVES or plan.has("prepare"):
            for pending in state["pending_actions"]:
                action = action_details(pending["approval_id"], customer_id, session_id)
                if action["status"] == "pending":
                    return finish("Cette demande attend votre confirmation explicite par le bouton. Aucun panier, checkout, retour ou paiement n'est exécuté par ce « oui ».", [action])
                if action["status"] == "done":
                    state["awaiting_prepare"] = False
                    return finish("L'API métier a déjà confirmé cette action. Je ne la relance pas. Précisez votre prochaine demande.")
                if action["status"] in ("confirmed", "needs_review"):
                    return finish("Cette opération est en cours ou reste à vérifier auprès de la boutique. Consultez son état avant toute nouvelle préparation.")
            proposal = state.get("catalogue_proposal")
            if proposal and not state["awaiting_prepare"] and (text in AFFIRMATIVES or not state["draft_items"]):
                if state["draft_items"]:
                    return finish("Souhaitez-vous ajouter ce produit au brouillon ou remplacer un article ? Précisez l'action et l'article concerné.")
                state["draft_items"] = [proposal]
                shopping.sync_selection(state, proposal)
                state.pop("catalogue_proposal", None)
            lines = state["draft_items"]
            if text not in AFFIRMATIVES and plan.has("prepare") and lines:
                state["awaiting_prepare"] = all(line.get("variant_id") and 1 <= line["quantity"] <= 20 for line in lines)
            if lines and state["awaiting_prepare"]:
                shopping.sync_selection(state, shopping.selected_line(state) or lines[-1])
            product, variant = selection(state)
            if not state["awaiting_prepare"] or not product or not variant:
                return finish("Pouvez-vous préciser le produit, sa variante et l'action souhaitée ? Ce « oui » n'autorise aucune opération.")
            # Re-fetch public catalog before preparing an approval; no guessed IDs.
            output = agent._observed_tool("search_products", {"query": ""}, token, request_id)
            used.append("search_products")
            verified = safe_products(output.get("products", []))
            from app.catalog import matching_variants
            for line in lines:
                fresh = next((p for p in verified if p["id"] == line["product_id"]), None)
                variants = matching_variants(fresh, line.get("size"), line.get("color")) if fresh else []
                fresh_variant = next((v for v in variants if v["id"] == line["variant_id"]), None)
                if not fresh or fresh["title"] != line["product"] or not fresh_variant or fresh_variant["title"] != line["variant"]:
                    state["awaiting_prepare"] = False
                    state["variant_id"] = None
                    line["variant_id"] = None
                    return finish("La variante n'a pas pu être revérifiée dans Medusa. Aucun panier créé ; choisissez de nouveau le produit.")
            state["products"] = verified
            cart_id = active_cart(session_id, customer_id)
            tool = "prepare_cart_items" if len(lines) > 1 or cart_id else "prepare_cart"
            args = {"variant_id": variant["id"], "quantity": state["quantity"]}
            if tool == "prepare_cart_items":
                args = {"cart_id": cart_id, "items": [{key: line[key] for key in ("product_id", "variant_id", "quantity", "operation")} for line in lines]}
            result = agent._observed_tool(tool, args, token, request_id)
            used.append(tool)
            if not result.get("approval_id"):
                return finish("La préparation de l'approbation a échoué. Aucun panier n'est confirmé comme créé.")
            details = {**result.get("display", {}), "availability": "not_checked"}
            if tool == "prepare_cart":
                details.update(args)
            with connection() as cx:
                cx.execute("INSERT INTO chat_approvals VALUES (?,?,?)", (result["approval_id"], session_id, json.dumps(details)))
            action = {**result, "arguments": args, "details": details}
            state["pending_actions"] = [action]
            state["intent"] = tool
            state["awaiting_prepare"] = False
            if tool == "prepare_cart_items":
                return finish("Le récapitulatif des articles est prêt. Vérifiez chaque ligne puis confirmez explicitement. La préparation seule n'a effectué aucune écriture dans Medusa.", [action])
            return finish(f"Je vais préparer votre panier : {product['title']}, variante {variant['title']}, quantité {state['quantity']}. Stock non vérifié. Vérifiez le récapitulatif puis confirmez explicitement. Aucun panier n'est encore créé.", [action])

        if not needs_reference(message) and not plan.has("orders", "support") and plan.has("catalogue", "selection", "price"):
            for pending in state["pending_actions"]:
                approval = storage.get_approval(pending["approval_id"], customer_id)
                if approval and approval["status"] in ("confirmed", "needs_review"):
                    return finish("Une opération précédente est en cours ou reste à vérifier. Consultez le panier ou un conseiller avant toute nouvelle préparation.")
            price_read = plan.has("price") and not re.search(r"ajout|quantite|prends|prefere|finalement", text)
            if not price_read and not cancel_pending(state, customer_id):
                return finish("Une opération est en cours ou incertaine. Attendez sa vérification avant de modifier le brouillon.")
            output = agent._observed_tool("search_products", {"query": ""}, token, request_id)
            used.append("search_products")
            if "error" in output:
                state["awaiting_prepare"] = False
                return finish("Le catalogue Medusa est indisponible. Aucun stock ni panier ne peut être confirmé.")
            products = safe_products(output.get("products", []))
            state["products"] = products
            answer = ""
            for clause in clauses:
                subplan = interpret(clause, bool(state["product_id"]), state.get("intent"))
                if subplan.has("out_of_scope", "greeting"):
                    continue
                answer = shopping.update_selection(state, clause, products, subplan)
            return finish(answer, state["pending_actions"] if price_read else None)

        def observe(name, arguments, output):
            if name == "search_products":
                state["products"] = safe_products(output.get("products", []))
            if name == "get_order_status":
                state["last_order"] = {key: output.get(key) for key in ("order_id", "status", "fulfillment_status", "payment_status")}
                state["intent"] = "orders"
            if name == "create_ticket":
                state["last_ticket"] = {key: output.get(key) for key in ("ticket_id", "status", "category")}
                state["intent"] = "support"
            if output.get("approval_id"):
                if not cancel_pending(state, customer_id):
                    with connection() as cx:
                        cx.execute("UPDATE approvals SET status='cancelled' WHERE id=? AND customer_id=? AND status='pending'", (output["approval_id"], customer_id))
                    from app.medusa import BackendError
                    raise BackendError("Une opération est déjà en cours ou incertaine. Demandez sa vérification avant une nouvelle approbation.")
                details = {"kind": name, "arguments": arguments, **output.get("display", {})}
                # Only validated action schemas contain these IDs/counts, never prompts.
                with connection() as cx:
                    cx.execute("INSERT OR IGNORE INTO chat_approvals VALUES (?,?,?)", (output["approval_id"], session_id, json.dumps(details)))
                state["pending_actions"] = [{**output, "arguments": arguments, "details": details}]
                state["intent"] = name
                state["awaiting_prepare"] = False
        state["awaiting_prepare"] = False
        result = agent.respond(message, token, request_id=request_id, history=snapshot["history"] + memory_messages(state), tool_observer=observe, documentary_context=documentary_context,
                               order_context=(state.get("last_order") or {}).get("order_id"))
        remember_documentary(result)
        result["intents"] = ["documentary"] if "source_supports_answer" in result else list(plan.intents)
        remember(snapshot)
        result["session_id"] = session_id
        result["pending_actions"] = [action_details(a["approval_id"], customer_id, session_id) for a in state["pending_actions"] if storage.get_approval(a["approval_id"], customer_id)["status"] == "pending"]
        return result
