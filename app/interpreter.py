"""Central request scope, intentions and catalogue criteria interpretation."""
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Interpretation:
    intents: tuple[str, ...]
    operation: str = "discuss"
    mixed_scope: bool = False

    def has(self, *intents):
        return any(intent in self.intents for intent in intents)


SCOPE_MESSAGE = "Je peux vous aider avec les produits, votre panier, vos commandes et le service client de cette boutique. Quelle est votre demande concernant la boutique ?"
ACCESS_MESSAGE = "Je ne peux pas afficher les commandes, paniers ou données d'autres clients. Je peux consulter uniquement les informations du compte connecté."
REFUND_MESSAGE = "Je ne peux pas exécuter de remboursement financier. Un conseiller habilité doit examiner cette demande. Je peux vous aider à consulter votre commande ou à ouvrir un ticket d'assistance."
AFFIRMATIVES = {"oui", "yes", "ok", "d'accord", "vas y", "celui-la", "celui la", "celui-ci", "celui ci", "celle-ci", "celle ci", "ce produit", "cet article"}


def split_requests(message):
    starter = r"(?:comment|quelle?s?|quels?|je\s+(?:veux|voudrais|souhaite)|ajoute|montre|consulte|ouvre|cree|peux.tu|pourquoi)\b"
    fragments = [part.strip() for part in re.split(r"\s+(?:et|puis|and)\s+(?=" + starter + r")|[.;]\s+(?=" + starter + r")", message, flags=re.I) if part.strip()]
    requests = []
    for fragment in fragments:
        # A problem description followed by its question is one request.
        # Keeping that context prevents losing the colour/parcel/account facts
        # that make the retrieved procedure applicable.
        if requests and not re.match(starter, requests[-1], re.I):
            requests[-1] += ". " + fragment
        else:
            requests.append(fragment)
    return requests


def ticket_action_requested(message):
    text = normalized(message)
    if re.search(r"^comment\b|comment.{0,20}\b(ouvrir|creer|ouvre)\b", text):
        return False
    return bool(re.search(r"\b(ouvre|cree|enregistre)\b|^creer\b|(?:je veux|je voudrais|j.aimerais|peux.tu|pouvez.vous|veuillez|merci de).{0,20}\b(ouvrir|creer)\b", text))


def interpret(message, has_selection=False, last_intent=None):
    """Classify permitted operations before choosing sources or executing tools.

    Scope and authorization are backend decisions. Provider text never widens
    this plan. Catalogue entities are resolved separately against live records.
    """
    text = normalized(message)
    if text in AFFIRMATIVES:
        return Interpretation(("prepare" if has_selection else "ambiguous",), "prepare")
    if re.search(r"autres? clients?|d.autrui|autre compte|client [bc]|another customer|other customers?", text):
        return Interpretation(("unauthorized",))
    if re.search(r"\b(rembourse|remboursez|vire|verse|refund me)\b", text) or (
        re.search(r"execute|declenche|effectue|immediat|sans.{0,20}(accord|confirmation)", text)
        and re.search(r"rembours|financial refund|transfer", text)
    ):
        return Interpretation(("financial_refund",))
    clauses = split_requests(message)
    if len(clauses) > 1:
        plans = [interpret(clause, has_selection, last_intent) for clause in clauses]
        intents = tuple(dict.fromkeys(intent for plan in plans for intent in plan.intents if intent != "out_of_scope"))
        operation = next((plan.operation for plan in reversed(plans) if plan.operation != "discuss"), "discuss")
        return Interpretation(intents or ("out_of_scope",), operation,
                              bool(intents and any(plan.has("out_of_scope") for plan in plans)))
    off_topic = bool(re.search(r"\b(president|roi|ministre|politique generale|football|match|sport|python|javascript|programme|programmation|capitale|encyclopedie|astronomie)\b", text))
    if not off_topic and not re.search(r"\b(comment|pas|sans)\b", text) and re.search(r"\bprepar(?:e|er|ons|ez)\b.{0,35}\b(brouillon|selection|panier)\b", text):
        return Interpretation(("prepare",), "prepare")
    cart = bool(re.search(r"\b(panier|basket|cart)\b", text))
    orders = bool(re.search(r"\b(commandes?|orders?|tracking|suivi)\b", text))
    support = bool(re.search(r"\b(tickets?|conseiller|assistance|support client|reclamation)\b", text))
    size, count = shopping_preferences(text)
    preferences = bool(size or count is not None or re.search(r"\b(couleur|color|bleu\w*|rouge\w*|noir\w*|blanc\w*|vert\w*|jaune\w*|rose|gris\w*|orange|violet\w*)\b", text))
    commerce = bool(re.search(r"\b(vend\w*|vends|avez|propos\w*|commercialis\w*|cherche\w*|recherch\w*|trouve\w*|disponib\w*|stock|prix|tarifs?|cout\w*|coute|produits?|articles?|catalogue|variantes?|acheter|achat|ajout\w*|voudrais|souhaite|je veux|enlever|supprim\w*)\b", text))
    price = bool(re.search(r"\b(prix|tarifs?|cout\w*|coute|combien)\b", text))
    reference = needs_reference(message)
    if support and ticket_action_requested(text) and len(split_requests(message)) == 1:
        return Interpretation(("support",))
    if reference and (not off_topic or re.search(r"boutique|magasin|garant|retour|rembours", text)):
        # A product/delivery problem needs documentary evidence. A stock or
        # price question remains a catalogue read even when asking for colour.
        intents = ["documentary"]
        if price:
            intents.append("price")
        if orders and re.search(r"statut|suivi|order_", text):
            intents.append("orders")
        if support:
            intents.append("support")
        return Interpretation(tuple(intents), mixed_scope=off_topic)
    intents = []
    if support:
        intents.append("support")
    if cart:
        intents.append("cart")
    if orders:
        intents.append("orders")
    if price and (has_selection or commerce):
        intents.append("price")
    if commerce or preferences or (has_selection and re.search(r"celui|celle|le meme|la meme|deuxieme|premier|troisieme|aussi|en [a-z]+|combien", text)):
        modifies = bool(re.search(r"je veux|voudrais|souhaite|ajout|prends|prefere|plutot|finalement|quantite", text))
        inquiry = bool(re.search(r"est.ce|avez|vend\w*|prix|tarif|combien|quelles? options|disponib", text)) or last_intent == "catalogue"
        intents.append("selection" if modifies or (preferences and not inquiry) else "catalogue")
    operation = "discuss"
    if re.search(r"\baussi\b|en plus|un autre|une autre|egalement|ajoute", text):
        operation = "add"
    if re.search(r"enleve|supprime|retire|annule seulement", text):
        operation = "remove"
    if cart and count is not None and re.search(r"modifi|change|mets|fixe|passe", text):
        operation = "set"
    if operation in ("set", "remove") and "selection" not in intents:
        intents.append("selection")
    if re.fullmatch(r"bonjour|salut|bonsoir|coucou|hello|merci(?: beaucoup)?|salutations|bon apres.midi", text):
        intents.append("greeting")
    if not intents:
        if last_intent in ("catalogue", "choose_product") and not off_topic and len(text.split()) <= 5:
            intents.append("catalogue")
        else:
            intents.append("out_of_scope" if off_topic else "ambiguous")
    return Interpretation(tuple(dict.fromkeys(intents)), operation, off_topic and any(i != "out_of_scope" for i in intents))


def needs_reference(message: str) -> bool:
    text = "".join(c for c in unicodedata.normalize("NFKD", message.lower()) if not unicodedata.combining(c))
    explicit_reference = re.search(r"\b(politique|policy|policies|conditions?|regles?|rules?|documentation|documentaire|references?|sources?|procedure|guidelines?|warrant(?:y|ies)|garant\w*|officiel\w*|contractuel\w*|eligibilite|eligibility)\b", text)
    if not explicit_reference and re.search(r"\b(order_[a-z0-9_-]+|ma commande|my order)\b", text) and re.search(r"\b(statut|status|suivi|tracking|livraison|delivery|shipping|paiement|payment|arrive|arriver)\b", text):
        return False
    if re.search(r"\b(retours?|remboursements?|livraison|delivery|refund|return|identifiant|username|recuperer|carte|bancaire|payer|colis|manquant|manque)\b", text):
        return True
    return bool(explicit_reference or re.search(
        r"\b(quel|quelle|quels|quelles|combien|what|how many)\b.{0,45}\b(delai|jours|days|return window)\b"
        r"|\b(comment|puis.je|peut.on|je peux|can i|how (can|do) i)\b.{0,45}\b(retourner|renvoyer|rembourser|return|refund)\b"
        r"|\b(how long do i have|combien de temps)\b.{0,45}\b(return|retour|renvoyer|send.{0,15}back)\b", text))


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)).strip(" .!?…")


def shopping_preferences(text, products=()):
    """Resolve explicit corrections in mention order, without guessing variants."""
    sizes = list(re.finditer(r"\b(?:taille|size)\s*(xxl|xl|xs|s|m|l|\d{1,3})\b|\b(?:prends|choisis|prefere|plutot|finalement)\s+(?:la\s+)?(xxl|xl|xs|s|m|l)\b|\ben\s+(xxl|xl|xs|s|m|l)\b", text))
    size = None
    if sizes:
        size = next(g.upper() for g in sizes[-1].groups() if g)
    if re.fullmatch(r"xxl|xl|xs|s|m|l", text):
        size = text.upper()
    # Match complete catalogue titles before quantity parsing, including brands.
    # Masking also keeps numbers inside a product name out of quantity matches.
    for product in sorted(products, key=lambda p: len(p["title"]), reverse=True):
        title = r"\s+".join(re.escape(word) for word in normalized(product["title"]).split())
        text = re.sub(r"\b" + title + r"s?\b", "produit", text)
    numbers = {word: n for n, word in enumerate(("zero", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf", "vingt"))}
    numbers["une"] = 1
    numbers["vingt et un"] = 21
    token = r"(?:vingt et un|dix[- ]sept|dix[- ]huit|dix[- ]neuf|" + "|".join(numbers) + r"|\d+)"
    patterns = {
        "product": r"(?<![\w.,/#-])(-?" + token + r")\s+(?:unites?|articles?|exemplaires?|pieces?|sweatshirts?|sweats?|t-shirts?|produits?)\b",
        "explicit": r"\b(?:quantite|quantity|j'en veux|prends(?:[- ]en)?|prenez(?:[- ]en)?|mets(?:[- ]en)?|ajoute(?:[- ]en)?|x)\s+(-?" + token + r")(?!\w|[.,/]\d)",
        "standalone": r"^(-?" + token + r")$",
    }
    non_quantity = r"(?:(?<!je )\b(?:prix|price|budget|commande|order|reference|ref|identifiant|id|sku|taille|size|version)\s*(?:(?:n[°o.]?|numero|number)\s*)?[:#]?\s*|[$€£]\s*)$"
    mentions = {}
    for name, pattern in patterns.items():
        mentions[name] = [(m.start(), m.group(1)) for m in re.finditer(pattern, text)
                          if not re.search(non_quantity, text[:m.start()])]
    # Explicit counts override articles such as "un" in the product phrase.
    # The latest explicit correction in this turn takes precedence.
    quantities = sorted(mentions["explicit"] + mentions["standalone"]) or sorted(mentions["product"])
    quantity = None
    if quantities:
        value = quantities[-1][1]
        quantity = int(value) if re.fullmatch(r"-?\d+", value) else numbers.get(value.replace("dix ", "dix-"))
    return size, quantity


