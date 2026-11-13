"""Catalogue-backed draft lines, separate from approvals and persisted carts."""
import re
import secrets

from app.catalog import match_products, matching_variants, requested_color, variant_values
from app.interpreter import normalized, shopping_preferences
from app.presentation import money


def migrate(state):
    if "draft_items" not in state:
        state["draft_items"] = []
        state["selected_line"] = None
        product = next((p for p in state["products"] if p["id"] == state["product_id"]), None)
        variant = next((v for v in product["variants"] if v["id"] == state["variant_id"]), None) if product else None
        if product and state.get("awaiting_prepare"):
            state["draft_items"].append({"line_id": "draft_legacy", "product_id": product["id"],
                "product": product["title"], "variant_id": variant["id"] if variant else None,
                "variant": variant["title"] if variant else None, "size": state.get("size"),
                "color": state.get("color"), "quantity": state.get("quantity", 1), "operation": "add"})
            state["selected_line"] = "draft_legacy"
    state["schema_version"] = 2
    return state


def selected_line(state):
    return next((line for line in state["draft_items"] if line["line_id"] == state["selected_line"]), None)


def reference_index(text):
    names = {"premier": 0, "premiere": 0, "deuxieme": 1, "second": 1, "seconde": 1, "troisieme": 2}
    match = re.search(r"\b(" + "|".join(names) + r")\b", text)
    if match:
        return names[match[1]]
    match = re.search(r"\b(?:article|ligne)\s+(\d{1,2})\b", text)
    return int(match[1]) - 1 if match else None


def sync_selection(state, line):
    state.update(product_id=line.get("product_id"), variant_id=line.get("variant_id"),
                 size=line.get("size"), color=line.get("color"), quantity=line["quantity"],
                 selected_line=line["line_id"], intent="choose_product")
    state["discussion"] = {key: line.get(key) for key in ("product_id", "variant_id", "size", "color")}
    state["awaiting_prepare"] = bool(state["draft_items"] and all(
        item.get("variant_id") and 1 <= item["quantity"] <= 20 for item in state["draft_items"]))


def public_draft(state):
    return [{"product": item.get("product") or "Produit à préciser", "variant": item.get("variant"),
             "quantity": item["quantity"], "operation": item.get("operation", "add"),
             "resolved": bool(item.get("variant_id"))} for item in state.get("draft_items", [])]


def edit_cart_draft(state, message, cart, products, plan):
    """Stage a change to an owned persisted line; no commerce write occurs."""
    text = normalized(message)
    size, quantity = shopping_preferences(text, products)
    color = requested_color(text, products)
    index = reference_index(text)
    candidates = list(cart.get("items", []))
    if index is not None:
        candidates = candidates[index:index + 1] if index >= 0 else []
    named = match_products(text, products)
    allowed_products = named or products
    allowed_variants = {variant["id"]: (product, variant) for product in allowed_products
                        for variant in matching_variants(product, size, color)}
    candidates = [line for line in candidates if line.get("variant_id") in allowed_variants]
    if len(candidates) > 1 and index is None and not named and not size and not color:
        candidates = [line for line in candidates if line.get("variant_id") == state.get("variant_id")]
    if len(candidates) != 1 or (plan.operation == "set" and quantity is None):
        state["awaiting_prepare"] = False
        return "Précisez la ligne du panier, sa variante et la quantité souhaitée. La préparation n'a modifié aucun article enregistré."
    actual = candidates[0]
    product, variant = allowed_variants[actual["variant_id"]]
    quantity = actual["quantity"] if plan.operation == "remove" else quantity
    if not 1 <= quantity <= 20:
        state["awaiting_prepare"] = False
        return "La quantité doit être comprise entre 1 et 20. Aucune approbation créée."
    state["draft_items"] = [line for line in state["draft_items"] if line.get("variant_id") != actual["variant_id"]]
    line = {"line_id": "draft_" + secrets.token_hex(12), "cart_line_id": actual.get("id"),
            "product_id": product["id"], "product": product["title"], "variant_id": variant["id"],
            "variant": variant["title"], "size": size, "color": color, "quantity": quantity, "operation": plan.operation}
    state["draft_items"].append(line)
    sync_selection(state, line)
    return "La modification de cette ligne est préparée dans le brouillon. Vérifiez la variante et la quantité, puis demandez une approbation à confirmer explicitement. Le contenu réel du panier reste à consulter auprès de Medusa."


def update_selection(state, message, products, plan):
    """Apply one requested draft transition using live catalogue records only."""
    migrate(state)
    text = normalized(message)
    size, quantity = shopping_preferences(text, products)
    if size is None:
        match = re.search(r"\b(?:taille|size)\s+(xxl|xl|xs|s|m|l|\d{1,3})\b|^(?:et\s+)?en\s+(\d{1,3})\b", text)
        size = next(group.upper() for group in match.groups() if group) if match else None
    color = requested_color(text, products)
    current = selected_line(state)
    discussion = state.get("discussion") or {key: state.get(key) for key in ("product_id", "variant_id", "size", "color")}
    index = reference_index(text)
    if index is not None:
        if not 0 <= index < len(state["draft_items"]):
            state["awaiting_prepare"] = False
            return "Cette ligne n'existe pas dans le brouillon. Précisez l'article concerné."
        current = state["draft_items"][index]
        state["selected_line"] = current["line_id"]
    if plan.operation == "remove":
        if not current:
            return "Précisez l'article du brouillon à retirer. Une annulation de préparation ne modifie aucun panier déjà enregistré."
        state["draft_items"].remove(current)
        state["selected_line"] = None
        state["product_id"] = state["variant_id"] = None
        state["awaiting_prepare"] = bool(state["draft_items"] and all(item.get("variant_id") for item in state["draft_items"]))
        return "Cet article est retiré du brouillon. Les autres lignes sont conservées. Le panier déjà enregistré reste à consulter auprès de la boutique."

    matches = match_products(text, products)
    contextual = bool(size or color or quantity is not None or index is not None or re.search(
        r"celui|celle|ce produit|cet article|le meme|la meme|combien|prix|couleur|taille", text))
    explicit_new = bool(re.search(r"je veux|voudrais|souhaite|ajout|un autre|une autre|(?:prefere|plutot)\s+(?:un|une)\b|(?:un|une)\s+(?:produit|article)\b", text)) and not re.search(r"\ben\b|celui|celle|ce produit|cet article", text)
    append = bool(re.search(r"\baussi\b|en plus|un autre|une autre|egalement", text))
    if len(matches) > 1:
        state["awaiting_prepare"] = False
        state["variant_id"] = None
        return "Plusieurs produits correspondent. Précisez le produit souhaité parmi : " + ", ".join(p["title"] for p in matches) + "."
    product = matches[0] if matches else None
    if not product and contextual and not explicit_new:
        focus = discussion.get("product_id") if state["intent"] == "catalogue" else (current or {}).get("product_id", state["product_id"])
        product = next((p for p in products if p["id"] == focus), None)
    if not product and re.search(r"\bcatalogue\b|quels produits", text):
        return "Catalogue consulté, stock non vérifié : " + ", ".join(p["title"] for p in products) + ". Précisez le produit et ses options."

    if plan.has("price") and product and not re.search(r"ajout|quantite|prends|prefere|finalement", text):
        previous = discussion if discussion.get("product_id") == product["id"] else {}
        variants = matching_variants(product, size or previous.get("size"), color or previous.get("color"))
        prices = [variant["title"] + " : " + (money((variant.get("price") or {}).get("calculated_amount"),
                  (variant.get("price") or {}).get("currency_code")) or "prix non fourni") for variant in variants]
        return "Prix unitaires lus dans le catalogue pour " + product["title"] + "\n\n" + "\n\n".join(prices) + "\n\nLe total du panier sera fourni par Medusa. Stock réel non vérifié."

    if plan.has("catalogue") and not plan.has("selection"):
        previous = discussion if product and discussion.get("product_id") == product["id"] else {}
        size, color = size or previous.get("size"), color or previous.get("color")
        variants = matching_variants(product, size, color) if product else []
        state.update(intent="catalogue", awaiting_prepare=False, catalogue_proposal=None,
                     discussion={"product_id": product["id"] if product else None, "size": size, "color": color})
        if not product:
            return "Je n'ai pas trouvé ce produit dans le catalogue consulté. Précisez une référence parmi : " + ", ".join(p["title"] for p in products) + "."
        if not variants:
            return "La taille ou la couleur demandée ne peut pas être confirmée pour " + product["title"] + ". Options du catalogue : " + ", ".join(v["title"] for v in product["variants"]) + "."
        if len(variants) == 1:
            state["catalogue_proposal"] = {"line_id": "draft_" + secrets.token_hex(12), "product_id": product["id"],
                "product": product["title"], "variant_id": variants[0]["id"], "variant": variants[0]["title"],
                "size": size, "color": color, "quantity": quantity or 1, "operation": "add"}
        return "Produit trouvé au catalogue : " + product["title"] + ". Variantes correspondant aux critères : " + ", ".join(v["title"] for v in variants) + ". Stock réel non vérifié. Précisez si vous souhaitez sélectionner un article pour le brouillon."

    state.pop("catalogue_proposal", None)
    append = append or (plan.operation == "add" and not re.search(r"\bajoute[- ]en\b", text))
    new_product = not current or not product or current.get("product_id") != product["id"]
    if append or not current:
        current = {"line_id": "draft_" + secrets.token_hex(12)}
        state["draft_items"].append(current)
        new_product = True
    if new_product:
        current.update(product_id=product["id"] if product else None, product=product["title"] if product else None,
                       variant_id=None, variant=None, size=None, color=None, quantity=1, operation="add")
    if size:
        current["size"] = size
    if color:
        current["color"] = color
    if quantity is not None:
        current["quantity"] = quantity
    current["variant_id"] = current["variant"] = None
    if not 1 <= current["quantity"] <= 20:
        sync_selection(state, current)
        return "La quantité doit être comprise entre 1 et 20. Aucune approbation créée."
    if not product:
        sync_selection(state, current)
        return "Je n'ai pas trouvé ce produit dans le catalogue consulté. Quel produit souhaitez-vous ? Choisissez une référence du catalogue : " + ", ".join(p["title"] for p in products) + "."
    variants = matching_variants(product, current["size"], current["color"])
    if len(variants) != 1:
        sync_selection(state, current)
        detail = " La couleur demandée ne peut pas être confirmée par les variantes du catalogue." if current["color"] and not variants else ""
        return f"Pour {product['title']}, précisez la taille/couleur parmi : " + ", ".join(v["title"] for v in product["variants"]) + "." + detail + " Stock non vérifié."
    current.update(variant_id=variants[0]["id"], variant=variants[0]["title"])
    for dimension in ("size", "color"):
        values = variant_values(variants[0], dimension)
        if not current[dimension] and len(values) == 1:
            value = next(iter(values))
            current[dimension] = value.upper() if dimension == "size" else value
    duplicate = next((line for line in state["draft_items"] if line is not current and line.get("variant_id") == current["variant_id"]
                      and line.get("operation") == current["operation"]), None)
    if duplicate:
        current["quantity"] += duplicate["quantity"]
        state["draft_items"].remove(duplicate)
        if current["quantity"] > 20:
            current["variant_id"] = current["variant"] = None
            sync_selection(state, current)
            return "La quantité cumulée de cette variante dépasse 20. Corrigez le brouillon avant toute approbation."
    sync_selection(state, current)
    return f"Variante trouvée au catalogue : {product['title']}, {current['variant']}, quantité {current['quantity']}. Stock réel non vérifié. Le brouillon contient {len(state['draft_items'])} article(s). Voulez-vous préparer une demande de panier ? Un « oui » créera seulement une approbation à confirmer séparément."
