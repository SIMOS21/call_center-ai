"""Customer UI: verified business cards, explicit approvals, optional diagnostics."""
import hashlib
import json
from urllib.parse import urlparse

import requests
import streamlit as st

from app.config import env, path_env
from app.conversations import sensitive
from app.presentation import customer_text, debug_view, money, status_text

st.set_page_config(page_title="CommerceOps · Votre assistant", page_icon="🛍️", layout="centered")
st.title("Votre assistant boutique")
st.caption("Produits, panier et aide · Boutique de démonstration · Aucun paiement financier réel")
base = env("COMMERCEOPS_API_URL", "http://127.0.0.1:8001").rstrip("/")
medusa_url = env("MEDUSA_URL", "http://localhost:9000").rstrip("/")
show_debug = st.sidebar.toggle("Mode développeur", value=False)
st.sidebar.header("Mon compte")
with st.sidebar.form("login", clear_on_submit=True):
    email = st.text_input("Adresse e-mail")
    password = st.text_input("Mot de passe", type="password")
    login = st.form_submit_button("Se connecter")
if login:
    try:
        response = requests.post(f"{medusa_url}/auth/customer/emailpass", json={"email": email, "password": password}, timeout=20)
        response.raise_for_status()
        st.session_state.customer_jwt = response.json()["token"]
        st.sidebar.success("Vous êtes connecté.")
    except (requests.RequestException, KeyError, ValueError):
        st.sidebar.error("Connexion impossible. Vérifiez vos identifiants et réessayez.")
credentials_path = path_env("DEMO_CREDENTIALS", "data/demo-credentials.json")
if urlparse(medusa_url).hostname in ("localhost", "127.0.0.1") and credentials_path.is_file():
    with st.sidebar.expander("Essayer avec un compte de démonstration"):
        account = st.selectbox("Compte de test", ["Client A", "Client B"])
        if st.button("Connexion au compte de test"):
            try:
                credentials = json.loads(credentials_path.read_text(encoding="utf-8"))[0 if account == "Client A" else 1]
                response = requests.post(f"{medusa_url}/auth/customer/emailpass", json=credentials, timeout=20)
                response.raise_for_status()
                st.session_state.customer_jwt = response.json()["token"]
                st.sidebar.success("Compte de démonstration connecté.")
            except (requests.RequestException, ValueError, KeyError):
                st.sidebar.error("Le compte de démonstration est indisponible.")
if st.sidebar.button("Se déconnecter"):
    st.session_state.customer_jwt = ""
token = st.session_state.get("customer_jwt", "")
fingerprint = hashlib.sha256(token.encode()).hexdigest() if token else "visitor"
if st.session_state.get("identity_fingerprint") != fingerprint:
    st.session_state.update(identity_fingerprint=fingerprint, session_id=None, history=[], pending_actions=[], action_feedback=None, action_warning=None, cart_view=None, debug_data={}, action_signature="", confirm_action=False)
headers = {"Authorization": "Bearer " + token} if token else {}
st.sidebar.caption("Compte connecté" if token else "Connectez-vous pour consulter vos paniers et conserver le contexte de vos demandes.")
if st.sidebar.button("Nouvelle conversation"):
    try:
        if st.session_state.session_id:
            response = requests.delete(f"{base}/sessions/{st.session_state.session_id}", headers=headers, timeout=20)
            response.raise_for_status()
        st.session_state.update(history=[], pending_actions=[], action_feedback=None, action_warning=None, cart_view=None, debug_data={}, action_signature="", confirm_action=False)
        st.sidebar.success("Conversation réinitialisée. Les demandes en attente sont annulées.")
    except requests.RequestException:
        st.sidebar.error("La conversation est occupée ou inaccessible. Réessayez dans un instant.")


def render_product(product):
    if not product:
        return
    with st.container(border=True):
        st.markdown("**" + customer_text(product["title"]) + "**")
        st.write(f"Variante : {product.get('variant') or 'à préciser'} · Quantité : {product['quantity']}")
        price = product.get("price") or {}
        unit = money(price.get("calculated_amount"), price.get("currency_code"))
        st.caption("Prix unitaire du catalogue · " + unit if unit else "Prix non fourni par le catalogue")
        st.caption("Sélection au catalogue · Stock réel non vérifié")


def render_draft(items):
    if not items or (len(items) == 1 and items[0].get("operation") == "add"):
        return
    with st.container(border=True):
        st.subheader("Votre brouillon d'articles")
        for index, item in enumerate(items, 1):
            verb = {"add": "Ajouter", "set": "Modifier", "remove": "Retirer"}.get(item.get("operation"), "Vérifier")
            st.write(f"Article {index} · {verb} · {customer_text(item['product'])} · {item.get('variant') or 'options à préciser'} · Quantité {item['quantity']}")
            if not item["resolved"]:
                st.caption("Cette ligne nécessite une précision avant approbation.")
        st.caption("Sélection en préparation. Le contenu réel du panier est fourni par la boutique après confirmation.")


def render_cart(cart):
    with st.container(border=True):
        st.subheader("Votre panier actuel")
        if not cart.get("items"):
            st.info("Votre panier est vide.")
        for item in cart.get("items", []):
            st.markdown("**" + customer_text(item.get("product_title") or item.get("title") or "Article") + "**")
            st.write(f"Variante : {item.get('variant_title') or 'non précisée'} · Quantité : {item.get('quantity', 'non confirmée')}")
            unit = money(item.get("unit_price"), cart.get("currency_code"))
            st.caption("Prix unitaire : " + unit if unit else "Prix unitaire non confirmé")
        total = money(cart.get("total"), cart.get("currency_code"))
        st.write("Total actuel : " + total if total else "Montant total non confirmé")
        st.caption({"completed": "Panier finalisé", "open": "Panier ouvert · Aucune commande passée par cette consultation"}.get(cart.get("status"), "Statut de finalisation non renseigné"))
        st.caption("Dernière consultation auprès de la boutique. Stock non vérifié ; consultez de nouveau pour actualiser les montants.")


for item in st.session_state.history:
    with st.chat_message(item["role"]):
        st.markdown(customer_text(item["content"]))
        render_product(item.get("product_selection"))
        render_draft(item.get("draft_selection", []))
        for business in item.get("business_results", []):
            if business["kind"] == "get_order_status":
                with st.container(border=True):
                    st.subheader("Votre commande")
                    st.write("Statut : " + status_text(business.get("status")))
                    st.write("Livraison : " + status_text(business.get("fulfillment_status")))
                    st.write("Paiement : " + status_text(business.get("payment_status")))
            elif business["kind"] == "create_ticket" and business.get("ticket_id"):
                st.info("Ticket d'assistance · " + status_text(business.get("status")))
if message := st.chat_input("Comment pouvons-nous vous aider ?"):
    st.session_state.action_feedback = None
    displayed = "[Saisie sensible masquée]" if sensitive(message) else message
    st.session_state.history.append({"role": "user", "content": displayed})
    with st.chat_message("user"):
        st.write(displayed)
    with st.chat_message("assistant"):
        try:
            body = {"message": message}
            if st.session_state.session_id:
                body["session_id"] = st.session_state.session_id
            response = requests.post(f"{base}/chat", json=body, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
            st.session_state.session_id = data.get("session_id", st.session_state.session_id)
            text = customer_text(data["answer"])
            st.markdown(text)
            st.session_state.history.append({"role": "assistant", "content": text, "product_selection": data.get("product_selection"), "draft_selection": data.get("draft_selection", []), "business_results": data.get("business_results", [])})
            render_product(data.get("product_selection"))
            render_draft(data.get("draft_selection", []))
            st.session_state.pending_actions = data.get("pending_actions", [])
            if st.session_state.pending_actions:
                st.session_state.action_feedback = None
            st.session_state.debug_data = debug_view(data)
            if "cart" in data:
                st.session_state.cart_view = data["cart"]
            elif "get_cart" in data.get("used_tools", []):
                st.session_state.cart_view = None
        except (requests.RequestException, ValueError, KeyError):
            st.error("Je n'ai pas pu vérifier votre demande. Réessayez ou reconnectez-vous. Aucune réussite n'est confirmée.")

if st.session_state.action_feedback:
    st.success(st.session_state.action_feedback)
if st.session_state.get("action_warning"):
    st.warning(st.session_state.action_warning)

pending = st.session_state.pending_actions
if pending:
    action = pending[0]
    try:
        response = requests.get(f"{base}/actions/{action['approval_id']}", headers=headers, timeout=20)
        response.raise_for_status()
        action = response.json()
    except (requests.RequestException, ValueError):
        action = None
        st.warning("Cette demande n'est pas accessible. Reconnectez-vous ou demandez un nouveau récapitulatif.")
    if action and action["status"] == "pending":
        signature = json.dumps(action, sort_keys=True)
        if st.session_state.action_signature != signature:
            st.session_state.action_signature = signature
            st.session_state.confirm_action = False
        with st.container(border=True):
            labels = {"prepare_cart": "Préparer votre panier", "prepare_cart_items": "Confirmer les articles du panier", "complete_cart": "Finaliser votre commande", "request_return": "Enregistrer votre demande de retour"}
            st.subheader(labels.get(action["kind"], "Vérifier votre demande"))
            details, arguments = action.get("details", {}), action["arguments"]
            if action["kind"] == "prepare_cart":
                st.markdown("**" + details.get("product", "Produit sélectionné") + "**")
                st.write(f"Variante : {details.get('variant', 'non précisée')} · Quantité : {arguments.get('quantity', 'non confirmée')}")
                if details.get("options"):
                    st.caption("Options du catalogue · " + ", ".join((str(option.get("title") or "Option") + " " + str(option.get("value", ""))) for option in details["options"]))
                price = details.get("price") or {}
                amount = money(price.get("calculated_amount"), price.get("currency_code"))
                st.caption("Prix unitaire vérifié au catalogue · " + amount if amount else "Prix non fourni par le catalogue. Le montant sera affiché après lecture du panier.")
                st.caption("Stock non vérifié. Tout changement des caractéristiques ou du prix fourni impose une nouvelle approbation.")
            elif action["kind"] == "prepare_cart_items":
                st.write("Panier existant" if details.get("cart") else "Nouveau panier de démonstration")
                verbs = {"add": "Ajouter", "set": "Fixer la quantité", "remove": "Retirer"}
                for item in details.get("items", []):
                    st.markdown("**" + customer_text(item.get("product", "Produit à vérifier")) + "**")
                    st.write(f"{verbs.get(item['operation'], 'Vérifier')} · {item.get('variant', 'variante à vérifier')} · Quantité demandée {item['quantity']} · Quantité après action {item['target_quantity']}")
                    if item.get("options"):
                        st.caption("Options du catalogue · " + ", ".join((str(option.get("title") or "Option") + " " + str(option.get("value", ""))) for option in item["options"]))
                    price = item.get("price") or {}
                    unit = money(price.get("calculated_amount"), price.get("currency_code"))
                    st.caption("Prix unitaire vérifié au catalogue · " + unit if unit else "Prix non fourni par le catalogue")
                st.caption("Stock non vérifié. Le montant total sera lu auprès de Medusa. Tout changement commercial exige une nouvelle approbation.")
            elif action["kind"] == "request_return":
                st.write("Vérifiez les articles et les quantités de votre demande. Cette action ne rembourse pas d'argent.")
                for n, item in enumerate(details.get("items") or arguments.get("items", []), 1):
                    st.write(f"{item.get('title') or f'Article {n}'} · Quantité demandée : {item['quantity']}")
            else:
                st.write("Cette demande concerne le panier sélectionné. Elle reste soumise aux vérifications de la boutique.")
                if details.get("cart"):
                    render_cart(details["cart"])
            st.info("En attente de votre accord. Aucune opération n'a encore été exécutée.")
            checked = st.checkbox("J'approuve cette action et le récapitulatif affiché", key="confirm_action")
            left, right = st.columns(2)
            confirm = left.button("Confirmer", disabled=not (checked and token), type="primary")
            cancel = right.button("Annuler")
            if confirm or cancel:
                try:
                    body = {"approval_id": action["approval_id"], "session_id": st.session_state.session_id, "confirm": bool(confirm)}
                    route = "confirm" if confirm else "cancel"
                    response = requests.post(f"{base}/actions/{route}", json=body, headers=headers, timeout=45)
                    response.raise_for_status()
                    outcome = response.json()
                    if outcome.get("status") == "needs_review":
                        st.session_state.action_warning = outcome["customer_message"]
                        st.session_state.action_feedback = None
                        st.session_state.pending_actions = []
                        st.rerun()
                    elif confirm and outcome.get("status") != "done":
                        st.warning("La boutique n'a pas confirmé la réussite. Consultez de nouveau votre demande.")
                    else:
                        st.session_state.action_feedback = outcome.get("customer_message") if confirm else "Demande annulée. Aucun panier ni aucune commande n'a été créé par cette annulation."
                        st.session_state.pending_actions = []
                        st.session_state.debug_data = {"kind": action["kind"], "status": outcome["status"], **debug_view(outcome.get("result", {}))}
                        if confirm and action["kind"] in ("prepare_cart", "prepare_cart_items"):
                            read = requests.get(f"{base}/sessions/{st.session_state.session_id}/cart", headers=headers, timeout=25)
                            if read.ok:
                                st.session_state.cart_view = read.json()["cart"]
                        st.rerun()
                except (requests.RequestException, KeyError, ValueError):
                    st.error("La demande a été refusée, est déjà traitée ou le service est indisponible. Vérifiez son État avant de poursuivre.")
    elif action:
        status = {"done": "Déjà effectuée", "failed": "À vérifier auprès d'un conseiller", "needs_review": "État métier incertain. Consultez le panier ou un conseiller avant toute nouvelle création", "invalidated": "Le catalogue ou le panier a changé. Demandez une nouvelle approbation", "cancelled": "Annulée", "confirmed": "En cours de traitement"}.get(action["status"], "À vérifier")
        st.info("État de la demande : " + status)

if token and st.session_state.session_id:
    if st.button("Consulter mon panier"):
        try:
            response = requests.get(f"{base}/sessions/{st.session_state.session_id}/cart", headers=headers, timeout=25)
            response.raise_for_status()
            data = response.json()
            st.session_state.cart_view = data["cart"]
            st.session_state.debug_data = {"cart_id": data["cart"]["cart_id"], "status": data["cart"]["status"]}
        except (requests.RequestException, ValueError, KeyError):
            st.session_state.cart_view = None
            st.warning("Aucun panier accessible dans cette conversation. Préparez un panier ou vérifiez votre connexion.")
if st.session_state.cart_view is not None:
    render_cart(st.session_state.cart_view)
if show_debug:
    with st.expander("Détails techniques (développeur)", expanded=False):
        st.json(st.session_state.debug_data)
