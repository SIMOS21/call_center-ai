"""Commercial approval snapshots, excluding inventory and customer information."""
import re

from app.interpreter import normalized


COLORS = {
    "bleu": "blue", "bleue": "blue", "bleues": "blue", "bleus": "blue", "blue": "blue",
    "rouge": "red", "rouges": "red", "red": "red", "vert": "green", "verte": "green", "green": "green",
    "noir": "black", "noire": "black", "black": "black", "blanc": "white", "blanche": "white", "white": "white",
    "gris": "grey", "grise": "grey", "gray": "grey", "grey": "grey", "rose": "pink", "pink": "pink",
    "jaune": "yellow", "yellow": "yellow", "orange": "orange", "violet": "purple", "purple": "purple",
    "marron": "brown", "brown": "brown", "marine": "navy", "navy": "navy",
}


class CatalogMismatch(ValueError):
    pass


def public_product(product):
    """Keep only catalogue facts needed for selecting and presenting variants."""
    options = {option["id"]: option.get("title", "") for option in product.get("options", []) if option.get("id")}
    variants = []
    for variant in product.get("variants", []):
        values = [{"title": (option.get("option") or {}).get("title") or options.get(option.get("option_id"), ""),
                   "value": option.get("value")} for option in variant.get("options", [])]
        variants.append({"id": variant.get("id"), "title": variant.get("title"), "options": values,
                         "price": variant_snapshot(product, variant)["price"]})
    return {"id": product.get("id"), "title": product.get("title"), "handle": product.get("handle"), "variants": variants,
            "type": (product.get("type") or {}).get("value"),
            "categories": [category.get("name") for category in product.get("categories", []) if category.get("name")]}


def words(text):
    return [word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word
            for word in re.findall(r"[a-z0-9]+", normalized(text))]


def match_products(text, products):
    """Rank complete titles and their suffixes; ambiguity is preserved."""
    query = " " + " ".join(words(text)) + " "
    ranked = []
    for product in products:
        title = words(product["title"])
        aliases = [title[index:] for index in range(len(title))]
        aliases += [words(value) for value in [product.get("type"), *product.get("categories", [])] if value]
        score = max((len(alias) for alias in aliases if " " + " ".join(alias) + " " in query), default=0)
        if score:
            ranked.append((score, product))
    best = max((score for score, _ in ranked), default=0)
    return [product for score, product in ranked if score == best]


def variant_values(variant, dimension):
    aliases = {"size": {"size", "taille"}, "color": {"color", "colour", "couleur"}}
    values = [normalized(str(option["value"])) for option in variant.get("options", [])
              if normalized(str(option.get("title", ""))) in aliases[dimension] and option.get("value")]
    if not values:
        title = normalized(variant.get("title", ""))
        # Legacy records expose only variant titles. The title itself must
        # contain the requested value before that value can be confirmed.
        pattern = r"\b(?:xxl|xl|xs|s|m|l)\b" if dimension == "size" else r"\b(?:" + "|".join(COLORS) + r")\b"
        values = re.findall(pattern, title)
    return {COLORS.get(value, value) if dimension == "color" else value for value in values}


def requested_color(text, products=()):
    candidates = [(match.start(), COLORS[match.group()]) for match in re.finditer(r"\b(?:" + "|".join(COLORS) + r")\b", text)]
    explicit = list(re.finditer(r"\b(?:couleur|color|colour)\s+([\w-]+)", text))
    candidates += [(match.start(), COLORS.get(match[1], match[1])) for match in explicit]
    for product in products:
        for variant in product["variants"]:
            for value in variant_values(variant, "color"):
                candidates += [(match.start(), value) for match in re.finditer(r"\b" + re.escape(value) + r"\b", text)]
    return sorted(candidates)[-1][1] if candidates else None


def matching_variants(product, size=None, color=None):
    return [variant for variant in product["variants"]
            if (not size or normalized(size) in variant_values(variant, "size"))
            and (not color or COLORS.get(normalized(color), normalized(color)) in variant_values(variant, "color"))]


def variant_snapshot(product, variant):
    option_titles = {option["id"]: option.get("title") for option in product.get("options", []) if option.get("id")}
    options = [{**{key: option.get(key) for key in ("id", "value", "option_id")},
                "title": (option.get("option") or {}).get("title") or option_titles.get(option.get("option_id"))}
               for option in variant.get("options", [])]
    price = variant.get("calculated_price")
    return {
        "product_id": product.get("id"), "product": product.get("title"),
        "handle": product.get("handle"), "variant_id": variant.get("id"),
        "variant": variant.get("title"),
        "attributes": {key: variant.get(key) for key in
                       ("sku", "barcode", "ean", "upc", "height", "weight", "width", "length", "material")},
        "options": sorted(options, key=lambda item: str(item)),
        "price": {key: price.get(key) for key in
                  ("calculated_amount", "original_amount", "currency_code", "is_calculated_price_tax_inclusive")}
        if isinstance(price, dict) else None,
    }


def cart_snapshot(cart):
    return {"cart_id": cart.get("cart_id"),
            "amounts": {key: cart.get(key) for key in
                        ("currency_code", "subtotal", "total", "tax_total", "shipping_total", "completed_at")},
            "items": sorted(cart.get("items", []), key=lambda item: str(item.get("id")))}


def batch_snapshot(gateway, items, token, cart_id=None):
    """Re-read every approved variant and the whole target cart before writes."""
    identities = [item["variant_id"] for item in items]
    if len(identities) != len(set(identities)):
        raise CatalogMismatch("Une variante apparaît plusieurs fois. Regroupez les quantités avant approbation.")
    cart = gateway.get_cart(cart_id, token) if cart_id else None
    if cart and cart.get("status") != "open":
        raise CatalogMismatch("Le panier n'est pas ouvert. Une nouvelle préparation est nécessaire.")
    variants, display = [], []
    for item in items:
        products = gateway.products("", product_id=item["product_id"]).get("products", [])
        matches = [(p, v) for p in products if p.get("id") == item["product_id"]
                   for v in p.get("variants", []) if v.get("id") == item["variant_id"]]
        if len(matches) != 1:
            raise CatalogMismatch("Une variante a disparu ou changé. Demandez une nouvelle approbation.")
        commercial = variant_snapshot(*matches[0])
        variants.append(commercial)
        existing = [line for line in (cart or {}).get("items", []) if line.get("variant_id") == item["variant_id"]]
        if len(existing) > 1:
            raise CatalogMismatch("Plusieurs lignes Medusa correspondent à la même variante. Un conseiller doit vérifier le panier.")
        operation = item.get("operation", "add")
        if operation != "add" and not existing:
            raise CatalogMismatch("La ligne à modifier n'existe pas dans ce panier.")
        before = existing[0]["quantity"] if existing else 0
        target = before + item["quantity"] if operation == "add" else item["quantity"]
        if operation == "remove":
            target = 0
        if not 0 <= target <= 20:
            raise CatalogMismatch("La quantité résultante doit rester comprise entre 1 et 20.")
        display.append({**commercial, "operation": operation, "quantity": item["quantity"], "target_quantity": target})
    return {"schema_version": 2, "variants": variants, "cart": cart_snapshot(cart) if cart else None}, {"items": display, "cart": cart}
