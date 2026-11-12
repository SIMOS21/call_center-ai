"""Real local Medusa sandbox smoke; credentials remain in ignored data/."""
import json
import secrets
from pathlib import Path
import httpx
from app.config import env
from app.medusa import Medusa, BackendError
from app.agent import Agent
from app import storage


def main():
    base = env("MEDUSA_URL", "http://localhost:9000")
    headers = {"x-publishable-api-key": env("MEDUSA_PUBLISHABLE_KEY")}
    client = httpx.Client(base_url=base, headers=headers, timeout=60)
    def call(method, route, token="", **kwargs):
        response = client.request(method, route, headers={"Authorization": "Bearer " + token} if token else {}, **kwargs)
        if response.is_error:
            # Local error response is only shown for debugging, no auth payload logged.
            raise RuntimeError(f"{method} {route}: HTTP {response.status_code} {response.text[:400]}")
        return response.json()
    credentials_path = Path("data/demo-credentials.json")
    if credentials_path.exists():
        credentials = json.loads(credentials_path.read_text())
    else:
        suffix = secrets.token_hex(4)
        credentials = [{"email": f"commerceops-{suffix}-{name}@example.test", "password": secrets.token_urlsafe(24)} for name in ("a", "b")]
        credentials_path.write_text(json.dumps(credentials), encoding="utf-8")
    tokens = []
    for credentials_item in credentials:
        registered = client.post("/auth/customer/emailpass/register", json=credentials_item)
        if registered.status_code == 200:
            registration_token = registered.json()["token"]
            call("POST", "/store/customers", registration_token, json={"email": credentials_item["email"], "first_name": "Demo"})
        token = call("POST", "/auth/customer/emailpass", json=credentials_item)["token"]
        tokens.append(token)
    medusa = Medusa()
    customers = [medusa.customer(token)["id"] for token in tokens]
    products = medusa.products()["products"]
    assert products
    agent = Agent(medusa)
    approval = agent._observed_tool("prepare_cart", {"variant_id": products[0]["variants"][0]["id"], "quantity": 1}, tokens[0], "integration-demo")
    assert approval.get("status") == "pending_confirmation", approval
    assert storage.get_approval(approval["approval_id"], customers[1]) is None
    assert storage.mark_approval(approval["approval_id"], customers[0])
    assert not storage.mark_approval(approval["approval_id"], customers[0])
    cart = medusa.create_cart(products[0]["variants"][0]["id"], 1, tokens[0])
    cart_id = cart["cart_id"]
    medusa.owned_cart(cart_id, tokens[0])
    try:
        medusa.complete_cart(cart_id, tokens[1])
        raise AssertionError("Foreign checkout was accepted")
    except BackendError:
        pass
    address = {"first_name": "Demo", "last_name": "Customer", "address_1": "1 Test Street", "city": "Paris", "country_code": "fr", "postal_code": "75001"}
    call("POST", f"/store/carts/{cart_id}", tokens[0], json={"email": credentials[0]["email"], "shipping_address": address, "billing_address": address})
    options = call("GET", "/store/shipping-options", tokens[0], params={"cart_id": cart_id})["shipping_options"]
    assert options
    call("POST", f"/store/carts/{cart_id}/shipping-methods", tokens[0], json={"option_id": options[0]["id"]})
    collection = call("POST", "/store/payment-collections", tokens[0], json={"cart_id": cart_id})["payment_collection"]
    call("POST", f"/store/payment-collections/{collection['id']}/payment-sessions", tokens[0], json={"provider_id": "pp_system_default"})
    result = medusa.complete_cart(cart_id, tokens[0])
    order_id = result["order_id"]
    order = medusa.order(order_id, tokens[0])
    try:
        medusa.order(order_id, tokens[1])
        raise AssertionError("Foreign order was accepted")
    except BackendError:
        pass
    return_body = {"order_id": order_id, "items": [{"id": order["items"][0]["id"], "quantity": 1}], "return_shipping": {"option_id": options[0]["id"]}}
    denied = []
    for token in ("", tokens[1]):
        response = client.post("/store/returns", headers={"Authorization": "Bearer " + token} if token else {}, json=return_body)
        assert response.status_code in (401, 403), (response.status_code, response.text[:100])
        denied.append(response.status_code)
    response = client.post(f"/store/carts/{cart_id}/complete", headers={"Authorization": "Bearer " + tokens[1]}, json={})
    assert response.status_code in (401, 403)
    ticket = agent._observed_tool("create_ticket", {"category": "delivery", "description": "Local integration demonstration ticket", "order_id": order_id}, tokens[0], "integration-demo")
    assert ticket.get("ticket_id"), ticket
    report = {"status": "PASS", "backend": "Medusa 2.22.6 real local", "products": len(products), "customers": customers, "cart_id": cart_id, "order_id": order_id, "order_status": order["status"], "payment_provider": "pp_system_default", "financial_payment": False, "direct_return_denials": denied, "foreign_checkout_status": response.status_code, "approval_once": True, "ticket_id": ticket["ticket_id"]}
    Path("reports/medusa-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
