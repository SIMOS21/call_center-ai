"""Real Medusa v2 Store API calls. NEVER use admin keys in customer agents."""
from __future__ import annotations
import httpx
from contextlib import nullcontext
from app.config import env
from app.observability import current_request, sanitized_tool_span

class BackendError(Exception):
    pass


class Medusa:
    def __init__(self, transport=None):
        self.base = env("MEDUSA_URL", "http://localhost:9000").rstrip("/")
        self.key = env("MEDUSA_PUBLISHABLE_KEY")
        self.region = env("MEDUSA_REGION_ID")
        self.transport = transport

    def _request(self, method: str, route: str, token: str = "", **kwargs) -> dict:
        if not self.key:
            raise BackendError("Medusa n'est pas configuré : renseigner MEDUSA_PUBLISHABLE_KEY.")
        headers = {"x-publishable-api-key": self.key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            context = sanitized_tool_span(f"medusa.{method}.{route.split('/')[2]}", current_request.get()) if current_request.get() else nullcontext(None)
            with context as span, httpx.Client(base_url=self.base, timeout=12, transport=self.transport) as client:
                r = client.request(method, route, headers=headers, **kwargs)
                if span is not None:
                    span.set_attributes({"http_status": r.status_code, "success": r.is_success})
                r.raise_for_status()
                payload = r.json()
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object")
                return payload
        except (httpx.HTTPError, ValueError) as exc:
            # Do not leak headers, tokens or full response payloads.
            raise BackendError(f"Erreur Medusa ({type(exc).__name__}); vérifier l'API et les droits.") from None

    def health(self) -> bool:
        try:
            self._request("GET", "/store/regions")
            return True
        except BackendError:
            return False

    def products(self, query: str = "", limit: int = 10) -> dict:
        return self._request("GET", "/store/products", params={"q": query, "limit": min(limit, 20)})

    def customer(self, token: str) -> dict:
        if not token:
            raise BackendError("Connexion client Medusa requise.")
        result = self._request("GET", "/store/customers/me", token=token)
        customer = result.get("customer")
        if not customer or not customer.get("id"):
            raise BackendError("Compte client non trouvé.")
        return customer

    def customer_orders(self, token: str) -> list[dict]:
        customer_id = self.customer(token)["id"]
        orders = self._request("GET", "/store/orders", token=token, params={"limit": 50, "fields": "+customer_id"}).get("orders", [])
        return [o for o in orders if o.get("customer_id") == customer_id]

    def order(self, order_id: str, token: str) -> dict:
        customer_id = self.customer(token)["id"]
        response = self._request("GET", f"/store/orders/{order_id}", token=token,
                                 params={"fields": "+customer_id,+fulfillment_status,+payment_status,+fulfillments"})
        order = response.get("order", {})
        if order.get("customer_id") != customer_id:
            # Ownership check is mandatory, even if API accidentally exposes details.
            raise BackendError("Accès refusé : commande non associée au client connecté.")
        return order

    def create_cart(self, variant_id: str, quantity: int, token: str) -> dict:
        self.customer(token)
        if not self.region:
            raise BackendError("MEDUSA_REGION_ID est requis.")
        if quantity < 1 or quantity > 20:
            raise BackendError("Quantité invalide (1 à 20).")
        result = self._request("POST", "/store/carts", token=token,
                               json={"region_id": self.region})
        cart_id = result["cart"]["id"]
        updated = self._request("POST", f"/store/carts/{cart_id}/line-items", token=token,
                                json={"variant_id": variant_id, "quantity": quantity})
        return {"cart_id": cart_id, "cart": updated.get("cart"), "checkout_status": "shipping_payment_required"}

    def complete_cart(self, cart_id: str, token: str) -> dict:
        self.owned_cart(cart_id, token)
        # Checkout only succeeds when shipping/billing/payment are configured in Medusa.
        response = self._request("POST", f"/store/carts/{cart_id}/complete", token=token)
        if response.get("type") != "order":
            raise BackendError("Checkout non finalisé : compléter livraison et paiement dans la boutique.")
        order = response.get("order", {})
        if not order.get("id"):
            raise BackendError("Réponse checkout invalide : commande absente.")
        return {"order_id": order.get("id"), "status": order.get("status"), "type": "order"}

    def owned_cart(self, cart_id: str, token: str) -> dict:
        customer_id = self.customer(token)["id"]
        cart = self._request("GET", f"/store/carts/{cart_id}", token=token,
                             params={"fields": "+customer_id"}).get("cart", {})
        if cart.get("customer_id") != customer_id:
            raise BackendError("Accès refusé : panier non associé au client connecté.")
        return cart

    def validate_return(self, order_id: str, items: list[dict], token: str) -> dict:
        order = self.order(order_id, token)
        # Local demonstration policy: customer-owned fulfilled orders only; no refund.
        # Enabling requires the merchant to explicitly configure this local policy.
        if env("STORE_RETURNS_ENABLED", "false").lower() != "true":
            raise BackendError("Retours non activés par la boutique : validation humaine requise.")
        if order.get("status") == "canceled" or order.get("fulfillment_status") not in ("fulfilled", "shipped", "delivered"):
            raise BackendError("Commande non éligible : expédition requise.")
        available = {x["id"]: int(x.get("quantity", 0)) - int(x.get("detail", {}).get("return_requested_quantity", 0))
                     - int(x.get("detail", {}).get("return_received_quantity", 0)) for x in order.get("items", [])}
        ids = [x.get("id") for x in items]
        if not items or len(ids) != len(set(ids)) or any(
            type(x.get("quantity")) is not int or x["quantity"] < 1
            or x["quantity"] > available.get(x.get("id"), 0) for x in items
        ):
            raise BackendError("Articles ou quantités de retour non autorisés.")
        return order

    def request_return(self, order_id: str, items: list[dict], shipping_option_id: str,
                       location_id: str, token: str) -> dict:
        self.validate_return(order_id, items, token)
        if not items or any(int(x.get("quantity", 0)) < 1 or not x.get("id") for x in items):
            raise BackendError("Articles de retour invalides.")
        payload = {"order_id": order_id, "items": items,
                   "return_shipping": {"option_id": shipping_option_id}, "location_id": location_id}
        data = self._request("POST", "/store/returns", token=token, json=payload)
        return_id = data.get("return", {}).get("id")
        if not return_id:
            raise BackendError("Réponse retour invalide : identifiant absent.")
        return {"return_id": return_id, "status": "requested", "financial_refund": False}
