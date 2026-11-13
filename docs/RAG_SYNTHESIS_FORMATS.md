# Synthèse documentaire et demandes de format — 12 novembre 2026

## Cause reproduite

Les deux réponses avant correction sont réellement identiques. `reports/rag-format/before.json` et `before-after.md` les conservent, avec leurs horodatages et métadonnées. Le fournisseur a répondu en mode `nvidia_verified_fact_selection` : **NVIDIA sélectionnait des IDs de faits, il ne rédigeait pas le texte français**. Le texte provenait des traductions et du renderer backend. Sans fournisseur, le fallback choisissait les trois premiers faits et aboutissait au même problème.

La chaîne vérifiée est la suivante :

1. `rag.documentary_search` retrouve Return Due to Color avec ses six chunks, y compris l'étiquette et les trois modes de retour. Le classement n'est pas la cause ; il est inchangé.
2. `supported_facts` ne reconnaissait que compte, achat et éligibilité pour ce scénario ; les informations opérationnelles n'entraient jamais dans la sélection.
3. `choose_facts` demandait au modèle trois IDs au maximum, sans instruction de composition ou de format.
4. `answer` joignait ces traductions en paragraphes, sans liste numérotée.
5. Dans un suivi, `conversations.respond` remplaçait la phrase utilisateur par « Résume la procédure de recherche [sujet] ». **« En trois étapes » disparaissait avant la sélection et le rendu.**

## Correction ciblée

Le texte utilisateur est conservé intégralement pour la présentation. Le contexte documentaire est transmis séparément : sujet canonique pour la recherche et source/SHA précédemment vérifiés. La référence est relue dans l'index ; un document modifié ou absent ne peut pas être résumé comme s'il était inchangé. Une demande explicite portant sur un autre sujet ne reste pas bloquée sur l'ancienne référence.

Des faits concrets sont reconnus **uniquement si leurs extraits exacts figurent dans les chunks réellement retournés** : suite après acceptation, étiquette à imprimer/adresse complète, modes By Mail / In Store / Drop off Center, branche de refus. Le sélecteur reçoit la demande originale et le format détecté. Les dépendances nécessaires à un plan de retour sont conservées même si le sélecteur ne renvoie que les faits de préparation.

`documentary_format.compose` construit des unités dont chaque affirmation déclare ses faits et extraits. Le format peut être une liste de deux/trois/quatre étapes, un texte court, une phrase ou une explication détaillée. Les variantes courtes et numérotées condensent les mêmes affirmations, sans inventer une procédure différente. Si le plan ne dispose pas d'assez d'unités étayées, il l'indique au lieu d'ajouter des étapes artificielles.

Le système reste volontairement une **sélection NVIDIA + composition française contrôlée**, pas de la prose libre attribuée au LLM. L'API distingue désormais `generation` (sélection/fallback), `composition`, `presentation_format`, `answer_units` et `missing_information`. Les références et avertissements de portée/sécurité restent séparés du corps demandé. Les informations machine ne sont pas ajoutées à l'interface client.

## Audit de sens, étape par étape

L'audit porte sur les réponses réellement enregistrées dans `after.json`, et pas seulement sur la présence d'une URL. Les assertions automatiques et `step-grounding.json` vérifient l'appui des clauses et le maintien des conditions ; la revue du sens ci-dessous est réalisée par l'agent implémenteur, **pas par un évaluateur humain indépendant**.

| Étape réellement affichée | Extraits originaux examinés | Vérification du sens et limites |
|---|---|---|
| Vérifier l'achat et le niveau d'adhésion selon ABCD | `Confirm that their purchase is valid with [Validate Purchase]` ; `Confirm their order can be returned, by checking their membership level.` | L'achat et le niveau d'adhésion sont deux vérifications distinctes, regroupées pour le résumé. La réponse n'affirme pas que le client est éligible dans Medusa et ne transforme pas les règles du scénario en droits commerciaux. |
| **Si le retour est accepté**, préparer l'étiquette à imprimer avec l'adresse complète | `If the customer can return, tell them the good news and go to the next step` ; `Since the customer will print out a shipping label for the return, you need their full address.` | Le « si » est conservé, ainsi que l'impression et l'adresse. Aucun appel de génération d'étiquette n'est prétendu exécuté. Si le passage conditionnel manque, cette étape n'est pas produite comme acquise et la lacune est nommée. |
| Choisir parmi les modes **cités par ABCD** : poste, magasin, centre de dépôt | `Options include: 'By Mail', 'In Store', or 'Drop off Center'` | Traduction des trois options, sans ajout de livraison gratuite, transporteur, disponibilité d'un magasin ou possibilité réelle dans la boutique. La réponse signale que les modes locaux restent non vérifiés. |

Aucun délai ni montant de remboursement n'est ajouté. « Ne communiquez pas votre adresse dans ce chat » est une précaution de l'application, **pas une instruction attribuée au corpus**. L'avertissement ABCD ≠ politiques officielles de la boutique Medusa est conservé dans chaque réponse. Les passages ne permettent pas de conclure sur l'éligibilité réelle du client ni sur les canaux/modes effectivement proposés par la boutique.

## Réponses réelles

Avant, les deux tours disaient : « La procédure commence par identifier le compte concerné. Elle prévoit de vérifier l'achat concerné. Elle examine ensuite l'éligibilité… » sans résumé structuré.

Après, la deuxième réponse contient réellement :

1. **Vérifier l'achat et l'éligibilité** — Faire vérifier l'achat et le niveau d'adhésion selon le scénario ABCD.
2. **Préparer l'étiquette après acceptation** — Si le retour est accepté, préparer l'étiquette à imprimer avec l'adresse complète.
3. **Choisir un mode de retour cité** — Choisir entre les modes cités par ABCD : envoi postal, magasin ou centre de dépôt.

Elle est suivie des limites locales, du rappel de sécurité et de la citation exacte. Les versions courte et détaillée ont également été obtenues réellement : la première condense le corps en un paragraphe ; la seconde sépare les vérifications et décrit aussi le cas d'un refus. Voir les quatre réponses intégrales dans [before-after.md](../reports/rag-format/before-after.md).

## Vérifications

**116 tests passent**, Ruff au profil CI et les deux quality gates existants passent. Le contrôle de secrets passe. Ces gates conservent leurs baselines historiques ; ils ne mesurent pas à eux seuls la fidélité du nouveau rendu. La nouvelle suite vérifie le dialogue signalé, d'autres formulations de deux/trois/quatre étapes, court/détaillé, source incomplète, condition d'acceptation absente, changement de document, changement de sujet, source inexistante et refus interclient.

Le parcours réel est FastAPI → RAG → NVIDIA dans une session de démonstration Medusa authentifiée. Aucun panier, commande ou retour n'a été créé. Aucun nouveau rendu visuel de navigateur n'est revendiqué ; l'interface inchangée affiche le Markdown renvoyé par l'API. Les régressions Streamlit/panier existantes font partie de pytest.

Les SHA des fichiers Medusa, API, UI, présentation métier, stockage et retrieval correspondent à la dernière version validée. Les fonctions de sessions, propriété, confirmation, liaison panier et reset sont identiques par AST à l'index Git précédent. Les modifications portent sur `documentary.py`, le nouveau `documentary_format.py`, le passage interne du contexte documentaire dans `agent.py` et `conversations.py`, les tests et les preuves.

Le jeu final gelé n'a pas été consulté pour cette correction, modifié ou exécuté. Les questions de cette intervention sont publiques et connues de développement. Aucune mesure indépendante ou garantie générale de fidélité n'est annoncée ; les traductions et règles de composition restent bornées aux faits reconnus. Sans session authentifiée, le mode documentaire reste stateless comme auparavant.

Pour reproduire le dialogue réel :

```powershell
# Les noms before.json / after.json sont protégés contre l'écrasement.
# Archiver les preuves existantes avant une nouvelle collecte, ne pas les remplacer.
.\.venv\Scripts\python.exe -m scripts.verify_rag_formats --phase after
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.\.venv\Scripts\python.exe -m scripts.quality_gate
.\.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
```

Le script nécessite les comptes de démonstration et l'API locale ; il envoie uniquement les questions publiques et faits documentaires autorisés au fournisseur. `scripts.evaluate_answers_v2` écrit maintenant ses nouvelles vérifications dans `reports/rag-format/answers-development.json` par défaut, pour préserver le rapport antérieur. Il contrôle les extraits et dépendances d'unités, sans les présenter comme une validation sémantique humaine.
