"""Local Streamlit demo. Customer JWT never persisted to disk."""
import requests
import streamlit as st
import json
from urllib.parse import urlparse
from app.config import env, path_env

st.set_page_config(page_title="CommerceOps AI", page_icon="🛒", layout="centered")
st.title("CommerceOps AI")
st.caption("Agent RAG + vraies API Medusa + suivi des actions. Boutique académique indépendante.")
base = st.sidebar.text_input("URL de l'API", "http://localhost:8001").rstrip("/")
demo_credentials = path_env("DEMO_CREDENTIALS", "data/demo-credentials.json")
medusa_url = env("MEDUSA_URL", "http://localhost:9000")
if urlparse(medusa_url).hostname in ("localhost", "127.0.0.1") and demo_credentials.is_file():
    with st.sidebar.expander("Comptes de démonstration locale"):
        account = st.selectbox("Compte", ["Client A", "Client B"])
        if st.button("Connexion au compte de test"):
            try:
                credentials = json.loads(demo_credentials.read_text(encoding="utf-8"))[0 if account == "Client A" else 1]
                response = requests.post(f"{medusa_url}/auth/customer/emailpass", json=credentials, timeout=20)
                response.raise_for_status()
                st.session_state["customer_jwt"] = response.json()["token"]
                st.success("Compte de test connecté")
            except (requests.RequestException, ValueError, KeyError):
                st.error("Connexion Medusa indisponible")
token = st.sidebar.text_input("Token JWT du compte client Medusa (facultatif pour le RAG)", type="password", key="customer_jwt")
st.sidebar.info("Aucun paiement réel n'est exécuté par l'agent. Un client confirmé peut effectuer des actions sur NOTRE Medusa local.")
headers = {"Authorization": f"Bearer {token}"} if token else {}
with st.expander("Recherche documentaire directe (sans LLM)"):
    query = st.text_input("Question dans les consignes ABCD", "retour mauvaise couleur")
    if st.button("Chercher les sources"):
        try:
            response = requests.post(f"{base}/knowledge/search", json={"question": query}, timeout=30)
            response.raise_for_status()
            rows = response.json()["results"]
            if not rows:
                st.info("Aucune source suffisamment pertinente. Reformulez ou demandez une revue humaine.")
            for row in rows:
                st.markdown(f"[{row['title']}]({row['source']})")
                st.write(row["content"])
            st.caption("Références de recherche ABCD ; elles ne définissent pas la politique de cette boutique.")
        except (requests.RequestException, ValueError):
            st.error("Recherche indisponible.")
if "history" not in st.session_state:
    st.session_state.history = []
for item in st.session_state.history:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])
if message := st.chat_input("Ex. Où est ma commande ? / Je souhaite retourner un produit"):
    st.session_state.history.append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.write(message)
    with st.chat_message("assistant"):
        try:
            r = requests.post(f"{base}/chat", json={"message": message}, headers=headers, timeout=90)
            r.raise_for_status()
            result = r.json()
            st.markdown(result["answer"])
            st.caption(f"Req: {result['request_id'][:8]} | Outils: {result['tool_calls']} | Temps: {result['latency_ms']} ms")
            st.session_state.history.append({"role": "assistant", "content": result["answer"]})
        except requests.RequestException as e:
            st.error(f"API indisponible ou requête échouée : {type(e).__name__}")
st.divider()
st.subheader("Confirmer une action")
approval_id = st.text_input("Identifiant d'approbation fourni par l'agent", placeholder="appr_...")
confirmed = st.checkbox("Je confirme explicitement cette action sur ma boutique Medusa de test")
if st.button("Exécuter l'action confirmée", disabled=not (approval_id and confirmed and token)):
    try:
        response = requests.post(f"{base}/actions/confirm", json={"approval_id": approval_id, "confirm": True},
                                 headers=headers, timeout=45)
        response.raise_for_status()
        st.success(response.json())
    except requests.RequestException as exc:
        st.error(f"Action refusée ou erreur API : {type(exc).__name__}")
