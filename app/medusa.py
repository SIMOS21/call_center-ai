"""Real Medusa v2 Store API calls. NEVER use admin keys in customer agents."""
from __future__ import annotations
import httpx
from contextlib import nullcontext
from app.config import env
from app.observability import current_request, sanitized_tool_span

class BackendError(Exception):
    pass


class BusinessOutcomeUnknown(BackendError):
    """A write was attempted. Reconcile by reading, never repeat it automatically."""
    def __init__(self, stage, cart_id=None):
        super().__init__("État métier à vérifier auprès de la boutique. Ne renouvelez pas cette écriture.")
        self.result = {"status": "needs_review", "stage": stage, "cart_creation_confirmed": bool(cart_id)}
        if cart_id:
            self.result["cart_id"] = cart_id


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

    def products(self, query: str = "", limit: int = 20, product_id: str | None = None, offset: int = 0) -> dict:
        params = {"q": query, "limit": min(limit, 20), "offset": offset, "fields": "*variants,*variants.options,+variants.calculated_price,*type,*categories"}
        if self.region:
            params["region_id"] = self.region
        if product_id:
            params["id"] = product_id
        return self._request("GET", "/store/products", params=params)

    def catalogue(self):
        products, identities = [], set()
        while True:
            response = self.products("", offset=len(products)) if products else self.products("")
            batch = response.get("products", [])
            if not isinstance(batch, list) or any(not isinstance(product, dict) or not product.get("id") for product in batch):
                raise BackendError("Réponse catalogue invalide.")
            incoming = {product["id"] for product in batch}
            if len(incoming) != len(batch) or identities.intersection(incoming):
                raise BackendError("La pagination du catalogue a changé. Réessayez sa consultation.")
            products.extend(batch)
            identities.update(incoming)
            if len(batch) < 20 or (type(response.get("count")) is int and len(products) >= response["count"]):
                return {"products": products}

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
        try:
            result = self._request("POST", "/store/carts", token=token,
                                   json={"region_id": self.region})
            cart_id = result["cart"]["id"]
        except (BackendError, KeyError, TypeError):
            raise BusinessOutcomeUnknown("cart_creation") from None
        try:
            updated = self._request("POST", f"/store/carts/{cart_id}/line-items", token=token,
                                    json={"variant_id": variant_id, "quantity": quantity})
            cart = updated.get("cart") or {}
            if cart.get("id") != cart_id or not any(i.get("variant_id") == variant_id and i.get("quantity") == quantity for i in cart.get("items", [])):
                raise BackendError("Ajout d'article non confirmé par la réponse métier.")
        except BackendError:
            # A lost response may hide a successful insertion. Only read to reconcile.
            try:
                cart = self.owned_cart(cart_id, token)
                items = cart.get("items", [])
                if len(items) == 1 and items[0].get("variant_id") == variant_id and items[0].get("quantity") == quantity:
                    return {"cart_id": cart_id, "cart": cart, "checkout_status": "shipping_payment_required", "reconciled_by_read": True}
            except BackendError:
                pass
            raise BusinessOutcomeUnknown("line_item", cart_id) from None
        return {"cart_id": cart_id, "cart": updated.get("cart"), "checkout_status": "shipping_payment_required"}

    def apply_cart_items(self, items, token, cart_id=None):
        """Execute an approved batch once; reconcile lost replies by reads only."""
        self.customer(token)
        if not items or len(items) > 20 or any(type(item.get("quantity")) is not int
                or not 1 <= item["quantity"] <= 20 or item.get("operation", "add") not in ("add", "set", "remove") for item in items):
            raise BackendError("Articles ou quantités de panier invalides.")
        variants = [item["variant_id"] for item in items]
        if len(variants) != len(set(variants)):
            raise BackendError("Regroupez les variantes identiques avant confirmation.")
        created_cart = not cart_id
        if not cart_id:
            if not self.region or any(item.get("operation", "add") != "add" for item in items):
                raise BackendError("Une région et des ajouts sont requis pour créer un panier.")
            try:
                created = self._request("POST", "/store/carts", token=token, json={"region_id": self.region})
                cart_id = created["cart"]["id"]
            except (BackendError, KeyError, TypeError):
                raise BusinessOutcomeUnknown("cart_creation") from None
        try:
            cart = self.get_cart(cart_id, token)
            expected = self._cart_quantities(cart)
            for index, item in enumerate(items):
                variant_id = item["variant_id"]
                operation = item.get("operation", "add")
                existing = next((line for line in cart["items"] if line.get("variant_id") == variant_id), None)
                before = expected.get(variant_id, 0)
                target = before + item["quantity"] if operation == "add" else item["quantity"]
                if operation == "remove":
                    target = 0
                if not 0 <= target <= 20 or (operation != "add" and not existing):
                    raise BackendError("Ligne ou quantité résultante non autorisée.")
                expected[variant_id] = target
                if target == 0:
                    expected.pop(variant_id)
                route = f"/store/carts/{cart_id}/line-items"
                method, body = "POST", {"variant_id": variant_id, "quantity": target}
                if existing:
                    if not existing.get("id"):
                        raise BackendError("Référence de ligne non confirmée.")
                    route += "/" + existing["id"]
                    body = {"quantity": target}
                if operation == "remove":
                    method, body = "DELETE", None
                try:
                    self._request(method, route, token=token, **({"json": body} if body else {}))
                except BackendError:
                    # The server may have committed the write. Do not issue it again.
                    pass
                cart = self.get_cart(cart_id, token)
                if self._cart_quantities(cart) != expected:
                    raise BusinessOutcomeUnknown("line_item_" + str(index + 1), cart_id)
            return {"cart_id": cart_id, "cart": cart, "checkout_status": "shipping_payment_required", "cart_created": created_cart}
        except BusinessOutcomeUnknown:
            raise
        except BackendError:
            raise BusinessOutcomeUnknown("cart_items", cart_id) from None

    @staticmethod
    def _cart_quantities(cart):
        items = cart.get("items", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) or type(item.get("quantity")) is not int or item["quantity"] < 1 for item in items):
            raise BackendError("Réponse panier invalide. Vérification humaine requise.")
        identities = [item.get("variant_id") for item in items]
        if len(set(identities)) != len(identities) or any(not identity for identity in identities):
            raise BackendError("Lignes de panier ambiguës. Vérification humaine requise.")
        return {item["variant_id"]: item["quantity"] for item in items}

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

    def get_cart(self, cart_id: str, token: str) -> dict:
        """Read-only, owner checked; no contact data or metadata leaves the gateway."""
        cart = self.owned_cart(cart_id, token)
        if not cart.get("id"):
            raise BackendError("Panier absent ou inaccessible.")
        result = {k: cart[k] for k in ("id", "currency_code", "subtotal", "total", "tax_total", "shipping_total", "completed_at") if k in cart}
        result["cart_id"] = cart["id"]
        result["status"] = ("completed" if cart["completed_at"] else "open") if "completed_at" in cart else "unknown"
        result["items"] = [{k: item[k] for k in ("id", "product_title", "title", "variant_title", "variant_id", "quantity", "unit_price", "subtotal", "total") if k in item} for item in cart.get("items", [])]
        result["availability"] = "not_checked"
        return result

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
