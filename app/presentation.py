"""Customer wording from verified structured API fields, not model claims."""
from decimal import Decimal, InvalidOperation
import re


def money(amount, currency):
    try:
        if amount is None or not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency):
            return None
        value = Decimal(str(amount))
        if not value.is_finite():
            return None
        # Medusa v2 amounts are MAJOR currency units. Never divide by 100.
        return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " " + currency.upper()
    except (InvalidOperation, ValueError):
        return None


def cart_text(cart):
    if not cart.get("items"):
        return "Votre panier est vide. Vous pouvez choisir un produit pour préparer un nouveau panier."
    lines = []
    for item in cart["items"]:
        title = item.get("product_title") or item.get("title") or "Article"
        variant = item.get("variant_title") or "variante non précisée"
        quantity = item.get("quantity")
        lines.append(f"{title} — {variant} — quantité {quantity if quantity is not None else 'non confirmée'}")
    result = "Votre panier contient :\n\n" + "\n\n".join(lines)
    total = money(cart.get("total"), cart.get("currency_code"))
    result += "\n\n" + (f"Total actuel : {total}." if total else "Le montant total n'est pas confirmé.")
    labels = {"completed": "Ce panier a été finalisé.", "open": "Ce panier est ouvert ; aucune commande n'est passée par cette consultation."}
    result += "\n\n" + labels.get(cart.get("status"), "Le statut de finalisation du panier n'a pas été fourni ; cette consultation ne passe aucune commande.")
    return result


def action_text(kind, result):
    if kind == "prepare_cart" and result.get("cart_id"):
        return "Votre panier a été créé. Consultez son contenu pour vérifier les articles et les montants actuels."
    if kind == "prepare_cart_items" and result.get("cart_id") and result.get("cart"):
        return ("Votre panier a été créé." if result.get("cart_created") else "Votre panier a été mis à jour.") + " Consultez les lignes et les montants retournés par la boutique."
    if kind == "complete_cart" and result.get("order_id"):
        return "Votre commande a été enregistrée. Statut : " + status_text(result.get("status")) + "."
    if kind == "request_return" and result.get("return_id"):
        return "Votre demande de retour a été enregistrée. Statut : " + status_text(result.get("status")) + ". Aucun remboursement financier n'a été effectué par l'assistant."
    if result.get("ticket_id"):
        return "Votre ticket d'assistance a été créé."
    return "Le résultat de cette opération n'est pas confirmé. Réessayez la consultation ou contactez un conseiller."


def customer_text(text):
    # Defense in depth: operational IDs and canonical memory never reach client prose.
    if "Mémoire serveur uniquement" in text or "Contexte validé :" in text:
        return "Précisez ce que vous souhaitez consulter ; je vérifierai les informations disponibles."
    return re.sub(r"\b(?:appr_|variant_|var_|cart_|order_|return_|prod_|tic_|sess_)[A-Za-z0-9_-]+", "[référence disponible dans les détails développeur]", str(text))


def status_text(status):
    return {"open": "Ouvert", "pending": "En attente", "completed": "Terminé", "canceled": "Annulé", "requested": "Demandé", "requires_action": "Action requise", "not_paid": "Non payé", "paid": "Payé", "captured": "Paiement capturé", "not_fulfilled": "Non préparé", "fulfilled": "Préparé", "shipped": "Expédié", "delivered": "Livré"}.get(status, "Non renseigné" if not status else "À vérifier")


def business_text(results):
    text = []
    for result in results:
        if result["kind"] == "get_cart":
            text.append(cart_text(result["cart"]))
        elif result["kind"] == "create_ticket" and result.get("ticket_id"):
            text.append("Votre ticket d'assistance a été créé. État : " + status_text(result.get("status")) + ".")
        elif result["kind"] == "get_order_status":
            text.append("Votre commande : " + status_text(result.get("status")) + ". Livraison : " + status_text(result.get("fulfillment_status")) + ". Paiement : " + status_text(result.get("payment_status")) + ".")
        elif result["kind"] == "list_orders":
            text.append("Aucune commande n'a été trouvée pour votre compte." if not result["orders"] else "Vos commandes : " + ", ".join(status_text(o.get("status")) for o in result["orders"]) + ".")
        elif result["kind"] == "list_tickets":
            text.append("Aucun ticket n'est enregistré pour votre compte." if not result["tickets"] else
                        "Vos tickets d'assistance : " + ", ".join(status_text(ticket.get("status")) for ticket in result["tickets"]) + ".")
    return "\n\n".join(text) or "Le résultat de cette demande n'est pas confirmé."


def debug_view(result):
    """Allowlist: never dump full Medusa carts, addresses or arbitrary metadata."""
    return {k: result[k] for k in ("request_id", "session_id", "used_tools", "tool_calls", "latency_ms", "generation", "intents", "selection_diagnostic", "source_found", "source_relevant", "source_supports_answer", "usage", "pending_actions", "sources", "cart_id", "order_id", "return_id", "status", "kind", "arguments", "details") if k in result}
