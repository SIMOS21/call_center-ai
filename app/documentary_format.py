"""Format a source-backed claim plan; provider prose is never business evidence."""
import re

from app.rag import normalize_query


def requested_format(question):
    text = normalize_query(question)
    numbers = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8}
    match = re.search(r"\b(\d{1,3}|un|une|deux|trois|quatre|cinq|six|sept|huit)\s+(etapes?|points?)\b", text)
    if match:
        count = numbers.get(match[1], int(match[1]) if match[1].isdigit() else 0)
        return {"mode": "steps", "requested_steps": count}
    if re.search(r"court|courte|bref|breve|concis|une phrase|en une ligne", text):
        return {"mode": "short", "requested_steps": None}
    if re.search(r"detail|developp|approfond|plus precis", text):
        return {"mode": "detailed", "requested_steps": None}
    if "resum" in text:
        return {"mode": "short", "requested_steps": None}
    return {"mode": "standard", "requested_steps": None}


def is_format_followup(message):
    text = normalize_query(message)
    return requested_format(message)["mode"] != "standard" or bool(re.search(r"resum|cette procedure|ces (consignes|etapes)|celle.ci|plus de detail|developpe", text))


def compose(question, facts):
    """Every unit carries its complete claim dependencies and original excerpts."""
    style = requested_format(question)
    by_id = {f["id"]: f for f in facts}
    units = []
    def add(title, text, ids):
        if all(identity in by_id for identity in ids):
            units.append({"title": title, "text": text, "fact_ids": ids,
                          "evidence": [by_id[identity] for identity in ids]})

    operational_return = "return_label" in by_id or "return_modes" in by_id
    if operational_return:
        if style["mode"] == "detailed" or (style["requested_steps"] or 0) >= 4:
            add("Vérifier l'achat", by_id.get("purchase", {}).get("text", ""), ["purchase"])
            add("Examiner l'éligibilité", by_id.get("eligibility", {}).get("text", ""), ["eligibility"])
        else:
            add("Vérifier l'achat et l'éligibilité", "Faire vérifier l'achat et les critères de retour du scénario, notamment le niveau d'adhésion.", ["purchase", "eligibility"])
        add("Préparer l'étiquette après acceptation", "Si le retour est accepté, le scénario prévoit une étiquette de retour à imprimer et l'adresse complète pour la préparer.", ["return_accepted", "return_label"])
        add("Choisir un mode de retour cité", "ABCD cite trois modes : l'envoi postal, le retour en magasin ou le dépôt en centre.", ["return_modes"])
        if style["mode"] == "detailed":
            add("Si le retour est refusé", by_id.get("return_refused", {}).get("text", ""), ["return_refused"])
    else:
        for fact in facts:
            if fact["id"] not in ("simulation", "scope", "bank_safety"):
                titles = {"retry": "Réessayer la saisie", "reconnect": "Se reconnecter", "expiry": "Vérifier la validité de la carte", "account": "Identifier le compte", "purchase": "Vérifier l'achat", "eligibility": "Examiner les critères", "identity": "Vérifier l'identité", "reason": "Préciser le temps d'attente"}
                add(titles.get(fact["id"], "Élément décrit dans la référence"), fact["text"], [fact["id"]])

    # These concise variants retain the same complete evidence dependencies.
    variants = {
        ("purchase", "eligibility"): {"steps": "Faire vérifier l'achat et le niveau d'adhésion selon le scénario ABCD.", "short": "Vérifier l'achat et l'éligibilité décrite dans ABCD."},
        ("return_accepted", "return_label"): {"steps": "Si le retour est accepté, préparer l'étiquette à imprimer avec l'adresse complète.", "short": "Après acceptation, préparer l'étiquette et l'adresse."},
        ("return_modes",): {"steps": "Choisir entre les modes cités par ABCD : envoi postal, magasin ou centre de dépôt.", "short": "Modes ABCD : poste, magasin ou centre de dépôt."},
    }
    for unit in units:
        unit["text"] = variants.get(tuple(unit["fact_ids"]), {}).get(style["mode"], unit["text"])

    available = len(units)
    requested = style["requested_steps"]
    if requested and requested < available:
        groups = []
        for n in range(requested):
            group = units[n*available//requested:(n+1)*available//requested]
            groups.append({"title": " / ".join(u["title"] for u in group),
                           "text": " ".join(u["text"] for u in group),
                           "fact_ids": [i for u in group for i in u["fact_ids"]],
                           "evidence": [e for u in group for e in u["evidence"]]})
        units = groups
    missing = []
    if requested and len(units) < requested:
        missing.append(f"Le plan étayé contient ici seulement {len(units)} étapes distinctes, pas {requested} ; je n'ajoute pas d'étape artificielle.")
    if not operational_return and re.search(r"retour|renvoy|return", normalize_query(question)):
        missing.append("Les passages disponibles ne précisent pas comment préparer l'étiquette ni quels modes de retour utiliser.")
    if operational_return:
        missing.append("Ces extraits ne confirment ni votre éligibilité dans notre boutique, ni les modes de retour qu'elle propose réellement.")
        if "return_label" not in by_id:
            missing.append("Le passage décrivant l'étiquette de retour manque.")
        if "return_modes" not in by_id:
            missing.append("Les modes de retour ne sont pas décrits dans les passages récupérés.")
        if "return_label" in by_id and "return_accepted" not in by_id:
            missing.append("Le passage reliant l'acceptation du retour à la préparation de l'étiquette manque ; je ne peux pas présenter cette suite comme acquise.")

    if style["mode"] == "steps":
        body = "\n\n".join(f"{n}. **{u['title']}** — {u['text']}" for n, u in enumerate(units, 1))
    elif style["mode"] == "short":
        body = " ".join(u["text"] for u in units)
        if "une phrase" in normalize_query(question):
            body = "; ".join(u["text"].rstrip(".") for u in units) + "."
    elif style["mode"] == "detailed":
        body = "\n\n".join(f"**{u['title']}**\n\n{u['text']}" for u in units)
    else:
        body = "\n\n".join("- " + u["text"] for u in units)
    notes = [f["text"] for f in facts if f["id"] in ("simulation", "scope", "bank_safety")]
    if style["mode"] == "short":
        brief = {
            "simulation": "Identifiant fictif dans ABCD. La récupération de votre véritable accès exige une vérification d'identité sécurisée.",
            "scope": "ABCD décrit aussi un colis indiqué livré mais encore en transit. Le colis reçu incomplet et le remboursement partiel ne sont pas établis.",
            "bank_safety": "La collecte bancaire décrite par ABCD ne s'applique pas ici. Ne partagez ni numéro de carte ni CVV. Aucun paiement n'est confirmé.",
        }
        notes = [brief[f["id"]] for f in facts if f["id"] in brief]
        if operational_return:
            missing = [m.replace("Ces extraits ne confirment ni votre éligibilité dans notre boutique, ni les modes de retour qu'elle propose réellement.",
                                 "Éligibilité et modes réellement proposés par la boutique à vérifier.") for m in missing]
    if operational_return:
        notes.append("Ne communiquez pas votre adresse dans ce chat.")
    return {"body": body, "units": units, "notes": notes, "missing": missing,
            "format": {**style, "provided_steps": len(units)}}
