import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from app import api as application
from app import conversations, storage
from app.medusa import BackendError

CATALOG = [
    {"id":"prod_sweat", "title":"Medusa Sweatshirt", "variants":[{"id":"var_s", "title":"S"}, {"id":"var_m", "title":"M"}, {"id":"var_l", "title":"L"}]},
    {"id":"prod_tee", "title":"Medusa T-Shirt", "variants":[{"id":"var_tm_black", "title":"M / Black"}, {"id":"var_tm_white", "title":"M / White"}]},
]


@pytest.mark.parametrize("message", [
    "Je veux 2 Medusa Sweatshirts taille L.",
    "Je veux deux Medusa Sweatshirts taille L.",
    "Je veux deux sweatshirts taille L.",
    "Je veux un Medusa Sweatshirt taille L, quantité 2.",
])
def test_full_product_name_quantity_regression(setup, message):
    client, writes = setup
    result = chat(client, message).json()
    assert result["product_selection"]["variant"] == "L"
    assert result["product_selection"]["quantity"] == 2
    assert not result["pending_actions"] and not writes


@pytest.mark.parametrize("title,message,quantity", [
    ("Medusa Sweatshirt", "Je veux 2 Medusa Sweatshirt taille L.", 2),
    ("Medusa Sweatshirt", "Je veux deux Medusa Sweatshirt taille L.", 2),
    ("Medusa Cotton Sweatshirt", "Je veux deux Medusa Cotton Sweatshirts taille L.", 2),
    ("Medusa Cotton Sweatshirt", "Je veux 2 Medusa Cotton Sweatshirt taille L.", 2),
    ("Atelier Paris Sweatshirt", "Je veux deux Atelier Paris Sweatshirts taille L.", 2),
    ("Medusa 2 Sweatshirt", "Je veux un Medusa 2 Sweatshirt taille L.", 1),
    ("Medusa 2 Sweatshirt", "Je veux Medusa 2 Sweatshirt taille L.", 1),
    ("Medusa 2 Sweatshirt", "Je veux trois Medusa 2 Sweatshirts taille L.", 3),
])
def test_catalogue_titles_are_quantity_phrases(setup, monkeypatch, title, message, quantity):
    client, writes = setup
    catalog = [{"id": "prod_named", "title": title, "variants": [{"id": "var_l", "title": "L"}]}]
    monkeypatch.setattr(application.medusa, "products", lambda *a, **kw: {"products": catalog})
    result = chat(client, message).json()
    assert result["product_selection"]["title"] == title
    assert result["product_selection"]["quantity"] == quantity
    assert not result["pending_actions"] and not writes


@pytest.mark.parametrize("message,quantity", [
    ("Je veux un Medusa Sweatshirt taille L, quantité 2.", 2),
    ("Quantité 2, pour un Medusa Sweatshirt taille L.", 2),
    ("Je veux 4 Medusa Sweatshirts taille L, quantité 2.", 2),
    ("Quantité 2 pour trois Medusa Sweatshirts taille L.", 2),
    ("Je veux 2 Medusa Sweatshirts taille L, finalement prends-en trois.", 3),
    ("Je veux un Medusa Sweatshirt taille L, quantité 2, finalement prends-en trois.", 3),
])
def test_explicit_quantity_and_latest_correction_take_precedence(setup, message, quantity):
    client, writes = setup
    result = chat(client, message).json()
    assert result["product_selection"]["quantity"] == quantity
    assert not result["pending_actions"] and not writes


@pytest.mark.parametrize("message", [
    "Medusa Sweatshirt taille L à 20 euros",
    "20,50 Medusa Sweatshirts taille L",
    "2.5 Medusa Sweatshirts taille L",
    "prix 2 Medusa Sweatshirts taille L",
    "€2 Medusa Sweatshirts taille L",
    "€ 2 Medusa Sweatshirts taille L",
    "commande 2 Medusa Sweatshirts taille L",
    "commande n° 2 Medusa Sweatshirts taille L",
    "order_2 Medusa Sweatshirts taille L",
    "référence 2 Medusa Sweatshirts taille L",
    "id 2 Medusa Sweatshirts taille L",
    "sku-2 Medusa Sweatshirts taille L",
    "taille 2 Medusa Sweatshirts",
    "taille deux Medusa Sweatshirts",
    "quantité 2.5",
    "quantité 2/3",
])
def test_non_quantity_numbers_are_not_product_counts(message):
    assert conversations.shopping_preferences(conversations.normalized(message), CATALOG)[1] is None


def test_branded_quantity_correction_invalidates_previous_approval(setup):
    client, writes = setup
    session = chat(client, "Je veux 2 Medusa Sweatshirts taille L.").json()["session_id"]
    old = chat(client, "oui", session).json()["pending_actions"][0]
    assert old["arguments"]["quantity"] == 2
    changed = chat(client, "Je veux trois Medusa Sweatshirts taille M.", session).json()
    assert changed["product_selection"]["quantity"] == 3
    assert changed["product_selection"]["variant"] == "M"
    assert storage.get_approval(old["approval_id"], "customer_A")["status"] == "cancelled"
    latest = chat(client, "Finalement, prends-en deux.", session).json()
    assert latest["product_selection"]["quantity"] == 2
    new = chat(client, "oui", session).json()["pending_actions"][0]
    assert new["arguments"] == {"variant_id": "var_m", "quantity": 2}
    assert new["approval_id"] != old["approval_id"] and not writes
    body = {"session_id": session, "approval_id": old["approval_id"], "confirm": True}
    assert client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"}).status_code == 409


@pytest.mark.parametrize("quantity", ["0", "-3", "21", "10000", "vingt et un"])
def test_branded_quantity_limits_invalidate_previous_approval(setup, quantity):
    client, writes = setup
    session = chat(client, "Medusa Sweatshirt taille L").json()["session_id"]
    old = chat(client, "oui", session).json()["pending_actions"][0]
    result = chat(client, f"Je veux {quantity} Medusa Sweatshirts taille L.", session).json()
    assert "comprise entre 1 et 20" in result["answer"]
    assert not result["product_selection"] and not result["pending_actions"]
    assert storage.get_approval(old["approval_id"], "customer_A")["status"] == "cancelled"
    assert not chat(client, "oui", session).json()["pending_actions"] and not writes


@pytest.mark.parametrize("quantity", ["deux", "2"])
def test_last_size_and_quantity_in_same_message(setup, quantity):
    client, writes = setup
    result = chat(client, f"Je veux {quantity} sweatshirts taille M. Finalement, je préfère la taille L.").json()
    assert result["product_selection"]["variant"] == "L"
    assert result["product_selection"]["quantity"] == 2
    action = chat(client, "oui", result["session_id"]).json()["pending_actions"][0]
    assert action["arguments"] == {"variant_id": "var_l", "quantity": 2}
    assert not writes


def test_corrections_replace_pending_and_keep_quantity(setup):
    client, writes = setup
    first = chat(client, "Je veux trois sweatshirts taille M.").json()
    session = first["session_id"]
    old = chat(client, "oui", session).json()["pending_actions"][0]
    changed = chat(client, "Non, plutôt la taille L.", session).json()
    assert changed["product_selection"]["quantity"] == 3
    assert changed["product_selection"]["variant"] == "L"
    assert storage.get_approval(old["approval_id"], "customer_A")["status"] == "cancelled"
    final = chat(client, "Finalement, prends-en deux.", session).json()
    assert final["product_selection"]["quantity"] == 2
    action = chat(client, "oui", session).json()["pending_actions"][0]
    assert action["arguments"] == {"variant_id": "var_l", "quantity": 2}
    assert action["approval_id"] != old["approval_id"]
    body = {"session_id": session, "approval_id": old["approval_id"], "confirm": True}
    assert client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"}).status_code == 409
    assert not writes


@pytest.mark.parametrize("wording,quantity", [("quantité vingt", 20), ("dix-sept sweatshirts taille M", 17), ("prends en deux", 2), ("trois sweatshirts, finalement prends-en deux", 2)])
def test_french_quantities_are_explicit(setup, wording, quantity):
    client, _ = setup
    session = chat(client, "Medusa Sweatshirt taille M").json()["session_id"]
    result = chat(client, wording, session).json()
    assert result["product_selection"]["quantity"] == quantity


@pytest.mark.parametrize("quantity", ["zéro", "0", "21", "-3", "vingt et un"])
def test_out_of_range_quantity_cannot_reuse_old_approval(setup, quantity):
    client, writes = setup
    session = chat(client, "Medusa Sweatshirt taille M").json()["session_id"]
    old = chat(client, "oui", session).json()["pending_actions"][0]
    result = chat(client, "quantité " + quantity, session).json()
    assert "comprise entre 1 et 20" in result["answer"]
    assert not result["pending_actions"] and not result["product_selection"]
    assert storage.get_approval(old["approval_id"], "customer_A")["status"] == "cancelled"
    assert not chat(client, "oui", session).json()["pending_actions"] and not writes


def test_missing_corrected_size_never_invents_variant(setup, monkeypatch):
    client, writes = setup
    catalog = [{"id": "prod_sweat", "title": "Medusa Sweatshirt", "variants": [{"id": "var_m", "title": "M"}]}]
    monkeypatch.setattr(application.medusa, "products", lambda *a, **kw: {"products": catalog})
    first = chat(client, "Je veux deux sweatshirts taille M. Finalement je préfère la taille L.").json()
    assert not first["product_selection"] and "précisez" in first["answer"]
    assert not chat(client, "oui", first["session_id"]).json()["pending_actions"] and not writes


@pytest.mark.parametrize("message", ["Je ne veux plus ajouter cet article. Annule la préparation du panier.", "Annule ma dernière demande.", "Je ne veux plus continuer."])
def test_natural_cancellation_is_owned_and_terminal(setup, message):
    client, writes = setup
    session = chat(client, "Medusa Sweatshirt taille M").json()["session_id"]
    action = chat(client, "oui", session).json()["pending_actions"][0]
    assert chat(client, message, session, "B").status_code == 404
    assert storage.get_approval(action["approval_id"], "customer_A")["status"] == "pending"
    result = chat(client, message, session).json()
    assert "annulée" in result["answer"] and not result["pending_actions"]
    body = {"session_id": session, "approval_id": action["approval_id"], "confirm": True}
    assert client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"}).status_code == 409
    client.delete("/sessions/" + session, headers={"Authorization": "Bearer A"})
    state = conversations.read(session, "customer_A")["state"]
    assert not state["pending_actions"] and not state["product_id"] and not writes


def test_negative_cancellation_and_size_correction(setup):
    client, _ = setup
    session = chat(client, "Medusa Sweatshirt taille M").json()["session_id"]
    result = chat(client, "Je ne veux plus du M, prends L", session).json()
    assert result["product_selection"]["variant"] == "L"
    assert not conversations.cancellation_requested("n'annule pas ma demande")


def test_cancellation_after_creation_preserves_cart_reference(setup):
    client, writes = setup
    session = chat(client, "Medusa Sweatshirt taille M").json()["session_id"]
    action = chat(client, "oui", session).json()["pending_actions"][0]
    body = {"session_id": session, "approval_id": action["approval_id"], "confirm": True}
    assert client.post("/actions/confirm", json=body, headers={"Authorization": "Bearer A"}).json()["status"] == "done"
    result = chat(client, "Annule ma dernière demande", session).json()
    assert "n'a pas modifié" in result["answer"]
    assert conversations.active_cart(session, "customer_A") == "cart_verified" and len(writes) == 1


def test_cancellation_during_confirm_reports_actual_inflight_state(setup, monkeypatch):
    from threading import Event
    client, writes = setup
    session = chat(client, "Medusa Sweatshirt taille M").json()["session_id"]
    action = chat(client, "oui", session).json()["pending_actions"][0]
    started, release = Event(), Event()
    def create(*args):
        writes.append(args)
        started.set()
        assert release.wait(5)
        return {"cart_id": "cart_verified"}
    monkeypatch.setattr(application.medusa, "create_cart", create)
    body = {"session_id": session, "approval_id": action["approval_id"], "confirm": True}
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.post, "/actions/confirm", json=body, headers={"Authorization": "Bearer A"})
        assert started.wait(5)
        result = chat(client, "Annule ma dernière demande", session).json()
        assert "déjà en cours" in result["answer"] and "n'est pas confirmée" in result["answer"]
        release.set()
        assert future.result().json()["status"] == "done"
    assert len(writes) == 1 and conversations.active_cart(session, "customer_A") == "cart_verified"


@pytest.mark.parametrize("provider", ["irrelevant", "unavailable"])
@pytest.mark.parametrize("question", ["Votre boutique garantit-elle officiellement tous les appareils électroniques pendant 36 mois ?", "Garantissez-vous officiellement les appareils trois ans ?", "Quelles garanties propose votre boutique ?"])
def test_commercial_policy_cannot_use_provider_identity(setup, monkeypatch, provider, question):
    from app import rag
    from app.agent import Agent, needs_reference
    import httpx
    _, writes = setup
    monkeypatch.setenv("LLM_API_KEY", "offline-fixture")
    calls = []
    monkeypatch.setattr(rag, "search", lambda q: calls.append(q) or [{"id": "abcd", "title": "ABCD: Return Due to Color", "source": "urn:public-fixture", "content": "Action: Validate Purchase"}])
    def post(*a, **kw):
        if provider == "unavailable":
            raise httpx.ConnectError("private")
        return httpx.Response(200, json={"choices": [{"message": {"content": "Je suis un modèle NVIDIA"}}]})
    monkeypatch.setattr(httpx.Client, "post", post)
    assert needs_reference(question)
    result = Agent(application.medusa).respond(question)
    assert result["abstained"] and result["used_tools"] == ["search_knowledge"] and calls
    assert "source pertinente" in result["answer"] and "NVIDIA" not in result["answer"]
    assert not result["pending_actions"] and not writes


@pytest.fixture
def setup(monkeypatch,tmp_path):
    monkeypatch.setenv("DB_FILE", str(tmp_path/"sessions.sqlite3"))
    monkeypatch.setattr("app.agent.sanitized_tool_span", lambda *a:nullcontext(None))
    def customer(token):
        if token not in ("A", "B"):
            raise BackendError("Invalid account")
        return {"id":"customer_"+token}
    monkeypatch.setattr(application.medusa,"customer",customer)
    monkeypatch.setattr(application.medusa,"products",lambda *a,**kw:{"products":CATALOG})
    writes=[]
    monkeypatch.setattr(application.medusa,"create_cart",lambda *a:writes.append(a) or {"cart_id":"cart_verified","checkout_status":"shipping_payment_required","cart":{"address":"PRIVATE NEVER IN MEMORY"}})
    return TestClient(application.api),writes


def chat(client,message,session=None,owner="A"):
    body={"message":message}
    if session:
        body["session_id"]=session
    return client.post("/chat",json=body,headers={"Authorization":"Bearer "+owner})


def test_sweatshirt_m_yes_preserves_selection_and_never_executes(setup):
    client,writes=setup
    first=chat(client,"Je souhaite un Medusa Sweatshirt taille M").json()
    assert first["session_id"].startswith("sess_") and not first["pending_actions"]
    assert "Stock réel non vérifié" in first["answer"] and not writes
    second=chat(client,"Oui",first["session_id"]).json()
    action=second["pending_actions"][0]
    assert "prepare_cart" in second["used_tools"] and action["arguments"]=={"variant_id":"var_m","quantity":1}
    assert action["details"]["product"]=="Medusa Sweatshirt"
    assert not writes
    repeated=chat(client,"oui",first["session_id"]).json()
    assert repeated["pending_actions"][0]["approval_id"]==action["approval_id"]
    body={"approval_id":action["approval_id"],"session_id":first["session_id"],"confirm":True}
    assert client.post("/actions/confirm",json=body,headers={"Authorization":"Bearer A"}).json()["status"]=="done"
    assert len(writes)==1
    assert client.post("/actions/confirm",json=body,headers={"Authorization":"Bearer A"}).status_code==409
    assert "API" in chat(client,"Oui",first["session_id"]).json()["answer"]
    assert len(writes)==1
    snapshot=client.get("/sessions/"+first["session_id"],headers={"Authorization":"Bearer A"}).json()
    assert snapshot["state"]["last_action"]["cart_id"]=="cart_verified"
    assert "PRIVATE NEVER IN MEMORY" not in json.dumps(snapshot)


def test_context_size_pronoun_quantity_and_change_product(setup):
    client,_=setup
    session=chat(client,"Je veux un Medusa Sweatshirt").json()["session_id"]
    assert not chat(client,"Oui",session).json()["pending_actions"]
    assert chat(client,"taille M",session).status_code==200
    chat(client,"quantité 2",session)
    action=chat(client,"celui-là",session).json()["pending_actions"][0]
    assert action["arguments"]=={"variant_id":"var_m","quantity":2}
    changed=chat(client,"Plutôt un Medusa T-Shirt taille M",session).json()
    assert not changed["pending_actions"] and "couleur" in changed["answer"]
    assert storage.get_approval(action["approval_id"],"customer_A")["status"]=="cancelled"
    chat(client,"noir",session)
    new=chat(client,"oui",session).json()["pending_actions"][0]
    assert new["arguments"]=={"variant_id":"var_tm_black","quantity":1}


def test_cross_customer_and_cross_session_access(setup):
    client,_=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    action=chat(client,"Oui",session).json()["pending_actions"][0]
    for method,path,body in [("get","/sessions/"+session,None),("delete","/sessions/"+session,None),("post","/chat",{"session_id":session,"message":"oui"})]:
        response=client.request(method,path,json=body,headers={"Authorization":"Bearer B"})
        assert response.status_code==404
    assert client.get("/actions/"+action["approval_id"],headers={"Authorization":"Bearer B"}).status_code==404
    second=chat(client,"Medusa Sweatshirt taille L").json()["session_id"]
    assert second!=session
    body={"approval_id":action["approval_id"],"confirm":True,"session_id":second}
    assert client.post("/actions/confirm",json=body,headers={"Authorization":"Bearer A"}).status_code==404
    body.pop("session_id")
    assert client.post("/actions/confirm",json=body,headers={"Authorization":"Bearer A"}).status_code==404
    assert client.post("/chat",json={"session_id":session,"message":"oui"}).status_code==401
    assert chat(client,"bonjour",owner="invalid").status_code==403
    own=client.get("/sessions/"+session,headers={"Authorization":"Bearer A"}).json()
    other=client.get("/sessions/"+second,headers={"Authorization":"Bearer A"}).json()
    assert own["state"]["variant_id"]=="var_m" and other["state"]["variant_id"]=="var_l"


def test_no_and_reset_cancel_pending_and_clear_history(setup):
    client,_=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    action=chat(client,"Oui",session).json()["pending_actions"][0]
    assert not chat(client,"non",session).json()["pending_actions"]
    assert storage.get_approval(action["approval_id"],"customer_A")["status"]=="cancelled"
    assert not chat(client,"oui",session).json()["pending_actions"]
    result=client.delete("/sessions/"+session,headers={"Authorization":"Bearer A"})
    assert result.status_code==200
    state=client.get("/sessions/"+session,headers={"Authorization":"Bearer A"}).json()
    assert not state["history"] and not state["state"]["product_id"]
    assert not chat(client,"celui-là",session).json()["pending_actions"]


def test_sensitive_text_never_in_model_history(setup,monkeypatch):
    client,_=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    content="Bearer very-private-token alice@example.test 12 rue Privée"
    result=chat(client,content,session)
    assert result.status_code==200 and result.json()["tool_calls"]==0
    stored=conversations.read(session,"customer_A")
    assert "very-private" not in json.dumps(stored) and "alice@" not in json.dumps(stored)
    captured=[]
    def respond(message, token, **kwargs):
        captured.extend(kwargs["history"])
        return {"answer":"Clarification", "pending_actions":[], "request_id":"r", "used_tools":[], "tool_calls":0}
    monkeypatch.setattr(application.agent,"respond",respond)
    chat(client,"merci beaucoup",session)
    assert "Medusa Sweatshirt" in json.dumps(captured) and content not in json.dumps(captured)


def test_yes_cannot_complete_checkout_or_return(setup):
    client,writes=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    approval=storage.create_approval("customer_A","complete_cart",{"cart_id":"cart_someone"})
    with conversations.turn(session,"customer_A") as snapshot:
        snapshot["state"]["pending_actions"]=[approval]
        snapshot["state"]["intent"]="request_checkout"
        snapshot["state"]["awaiting_prepare"]=False
    with conversations.connection() as cx:
        cx.execute("INSERT INTO chat_approvals VALUES (?,?,?)",(approval["approval_id"],session,"{}"))
    result=chat(client,"Oui",session).json()
    assert result["pending_actions"][0]["kind"]=="complete_cart" and not result["tool_calls"]
    assert not writes and storage.get_approval(approval["approval_id"],"customer_A")["status"]=="pending"


def test_catalog_error_cancels_old_choice_without_false_success(setup,monkeypatch):
    client,writes=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    def error(*a,**kw):
        raise BackendError("timeout")
    monkeypatch.setattr(application.medusa,"products",error)
    result=chat(client,"oui",session).json()
    assert not result["pending_actions"] and "pas pu être revérifiée" in result["answer"]
    assert not writes


def test_removed_variant_is_not_prepared(setup, monkeypatch):
    client,writes=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    monkeypatch.setattr(application.medusa,"products",lambda *a:{"products":[]})
    result=chat(client,"oui",session).json()
    assert not result["pending_actions"] and not writes
    assert conversations.read(session,"customer_A")["state"]["variant_id"] is None


def test_changed_variant_details_require_new_choice(setup,monkeypatch):
    client,writes=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    changed=json.loads(json.dumps(CATALOG))
    changed[0]["variants"][1]["title"]="L"
    monkeypatch.setattr(application.medusa,"products",lambda *a:{"products":changed})
    assert not chat(client,"oui",session).json()["pending_actions"] and not writes


def test_unknown_new_product_does_not_reuse_previous_variant(setup):
    client,writes=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    chat(client,"Plutôt un produit introuvable taille L",session)
    assert not chat(client,"oui",session).json()["pending_actions"] and not writes
    assert conversations.read(session,"customer_A")["state"]["product_id"] is None


def test_history_bounded_and_current_confirmed_cart_reaches_model(setup,monkeypatch):
    client,_=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    action=chat(client,"oui",session).json()["pending_actions"][0]
    client.post("/actions/confirm",json={"approval_id":action["approval_id"],"confirm":True,"session_id":session},headers={"Authorization":"Bearer A"})
    captured=[]
    def respond(message,token,**kwargs):
        captured.extend(kwargs["history"])
        return {"answer":"Le panier vérifié", "pending_actions":[], "request_id":"r", "used_tools":[], "tool_calls":0}
    monkeypatch.setattr(application.agent,"respond",respond)
    chat(client,"Et ensuite ?",session)
    assert "cart_verified" in json.dumps(captured) and "var_m" in json.dumps(captured)
    for _ in range(25):
        chat(client,"non",session)
    snapshot=conversations.read(session,"customer_A")
    assert len(snapshot["history"])==40


def test_failed_business_action_is_not_claimed_created_or_retried(setup,monkeypatch):
    client,writes=setup
    session=chat(client,"Medusa Sweatshirt taille M").json()["session_id"]
    action=chat(client,"oui",session).json()["pending_actions"][0]
    def unavailable(*a):
        raise BackendError("Stock insuffisant")
    monkeypatch.setattr(application.medusa,"create_cart",unavailable)
    body={"approval_id":action["approval_id"],"confirm":True,"session_id":session}
    response=client.post("/actions/confirm",json=body,headers={"Authorization":"Bearer A"})
    assert response.status_code==502
    assert storage.get_approval(action["approval_id"],"customer_A")["status"]=="needs_review"
    assert client.post("/actions/confirm",json=body,headers={"Authorization":"Bearer A"}).status_code==409
    assert not chat(client,"oui",session).json()["pending_actions"] and not writes


def test_session_claim_serializes_turns_and_blocks_reset(setup):
    _,_=setup
    session=conversations.create("customer_A")
    with conversations.turn(session,"customer_A"):
        with pytest.raises(conversations.SessionBusy):
            conversations.reset(session,"customer_A")
        with ThreadPoolExecutor(max_workers=1) as executor:
            result=executor.submit(chat_claim,session)
            assert result.result()=="busy"


def chat_claim(session):
    try:
        with conversations.turn(session,"customer_A"):
            return "claimed"
    except conversations.SessionBusy:
        return "busy"
