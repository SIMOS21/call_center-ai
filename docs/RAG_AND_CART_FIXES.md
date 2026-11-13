# Corrections RAG, conversation et panier — V2, 12 novembre 2026

Le système existant est conservé : Streamlit, FastAPI, NVIDIA Nemotron, Medusa, PostgreSQL, SQLite, MLflow et les deux baselines RAG. Les modifications sont locales et préparées pour revue, sans publication GitHub. Le document de mission a été lu intégralement. D01–D06 sont des cas de développement connus, pas un test indépendant.

## Diagnostic et changements

Le diagnostic HTTP avant changement est dans [le tableau détaillé](../reports/rag-diagnostic.md) et `reports/global-v2/diagnostic-before.json`. Les documents ABCD originaux ont été examinés, y compris leurs limites et leurs étapes incompatibles avec le chat.

| Défaut | Cause vérifiée | Correction |
|---|---|---|
| Mauvaise couleur → Manage Cancel | Pont FR/EN insuffisant ; le fragment court contenant les métadonnées prenait trop de poids | Lecture par document/source, corps 65 % + titre 35 %, normalisation et vocabulaire bilingue, formes féminines/plurielles des couleurs. Seuil 0,12 conservé. |
| Article manquant → boucle d'outils | Recherche laissée au modèle ; appels non pertinents à list_orders/create_ticket | Routage documentaire déterministe. Missing Item est cité avec sa **couverture partielle** : le texte traite surtout d'un article non reçu / colis indiqué livré trop tôt. Aucun formulaire, photo ou remboursement partiel inventé. |
| Identifiant oublié → Recover Password | Username absent du pont lexical ; synthèse libre malgré une mauvaise source | Recover Username récupéré ; filtre de pertinence écarte Recover Password. La réponse explique que le scénario fabrique un identifiant fictif, sans l'appliquer au compte réel. |
| Carte refusée → conseils et PayPal non vérifiés | Mauvais classement et absence de contrainte sur les faits générés | Invalid Credit Card ; seulement faits attestés : réessai sur la page de paiement, reconnexion, vérification personnelle de validité. Aucune collecte de numéro/CVV, aucun moyen de paiement supposé. |
| Résumé après garantie absente | Résultat documentaire non mémorisé | `last_documentary_question` conserve un sujet canonique, `last_verified_sources` les références et `last_search_outcome` les trois indicateurs. Après abstention, le suivi explique qu'aucune procédure n'a été trouvée. Aucun texte brut sensible n'est archivé. |
| Panier créé mais illisible | Aucun outil get_cart, association seulement indirecte via ancienne approbation | Association validée par l'approbation effectivement exécutée ; outil get_cart et lecture du panier de la session avec contrôle de propriété à chaque requête. |
| JSON et identifiants affichés | Présentation brute des réponses machine | Cartes produit/panier, récapitulatifs, case d'accord + boutons Confirmer/Annuler, messages métier. Détails techniques expurgés facultatifs. |

La première exécution supplémentaire de développement a détecté les formes « noire/verte » non reconnues. Le résultat initial est conservé dans `development-initial.json` et l'essai d'intégration interrompu dans `integration-first-failure.json`. Cette découverte a été corrigée, puis l'intégration a repassé. Les dix questions sont désormais toutes considérées connues ; aucun résultat n'est présenté comme indépendant.

## Récupération et réponses fidèles

`rag.lexical_search` et la baseline dense conservent leur fonctionnement. Le lecteur actif `documentary_search` regroupe les passages par source et SHA documentaire, en conservant les IDs et textes de chacun. Son cache dépend des octets du manifeste : publication atomique, collections denses immutables et rechargement après import restent en place. Aucun nouveau document, scraping ou index destructif n'a été ajouté. Les sous-flux restent distingués par leurs fragments de provenance. Le lecteur hybride et son reranking optionnel sont conservés, **non activés**, sans gain démontré ici.

Le score de corps, de titre, lexical, dense et fusionné porte un nom distinct. `source_found` signifie qu'un candidat a été récupéré ; `source_relevant` dépend de filtres conservateurs de sujet et de faits reconnus ; `source_supports_answer` signifie que les faits effectivement affichés disposent d'extraits attestés. Ces indicateurs sont des contrôles de développement, **pas des jugements sémantiques humains**.

La synthèse libre a été remplacée par une sélection NVIDIA de faits français autorisés, chacun lié à un extrait exact et à des IDs de chunks. Le modèle ne peut renvoyer que des identifiants de faits ; sa prose libre et ses identifiants inventés sont ignorés. Les traductions sont des annotations de code examinées par l'agent à partir du corpus authentique. Les mises en garde pertinentes sont obligatoires : simulation du username, couverture partielle des colis incomplets, collecte bancaire interdite ici. Un échec fournisseur utilise les mêmes faits vérifiés, sans faux succès. Document inconnu sans faits reconnus : abstention prudente plutôt qu'une paraphrase non vérifiée.

Chaque référence est rendue en Markdown avec titre et URL encodée, y compris les espaces des fragments ABCD. Les procédures ABCD ne sont jamais présentées comme des politiques officielles de Medusa ou de la boutique. Sans source de politique applicable, aucune garantie, condition contractuelle ou droit commercial n'est affirmé. Les statuts de commandes conservent leurs lectures Medusa sans RAG obligatoire.

## Contrat panier et sécurité

- `Medusa.get_cart` réutilise **sans modification** `owned_cart`, puis renvoie uniquement lignes, variantes, quantités, montants et état du panier ; aucune adresse, e-mail ou métadonnée client. Seuls des GET sont nécessaires.
- `chat_session_carts` lie le panier à la session, au client et à l'approbation réellement terminée. Ce lien ne vient jamais d'un `cart_id` fourni par le navigateur. La confirmation conserve sa transition atomique à usage unique et la session d'origine des approbations de chat.
- `GET /sessions/{session_id}/cart` et « mon panier » consultent ce lien, puis revérifient l'identité et la propriété dans Medusa. Session étrangère : 404 ; absence d'authentification : 401. Un autre panier du même client n'est pas sélectionné automatiquement. Sans lien, on demande de préparer un panier. Panier absent/indisponible : message prudent ; panier vide : état vide, sans inventer de lignes.
- Le reset efface le lien actif et les faits de conversation, sans supprimer le panier métier. Un test de concurrence vérifie qu'une confirmation démarrée avant le reset ne rétablit pas le contexte effacé.
- `POST /actions/cancel` annule seulement l'approbation locale pending, liée au propriétaire et à sa session. Aucun appel d'écriture Medusa. Un second traitement est refusé. Un simple « oui » ne finalise ni commande, retour ni paiement.
- Les méthodes protégées `customer`, `order`, `owned_cart`, `create_cart`, `complete_cart`, `validate_return`, `request_return` sont comparées par AST à HEAD : identiques. Le middleware réel correspond à sa copie archivée. Aucun rôle, permission, règle de retour ou remboursement autonome n'a changé.

Le statut « panier ouvert/finalisé » vient de `completed_at` renvoyé par Medusa ; un champ absent devient **inconnu**. Une absence de montant ou de quantité n'est pas remplacée par une valeur inventée. Les montants Medusa v2 sont exprimés en unités majeures, sans division par 100, conformément à la [documentation Medusa](https://docs.medusajs.com/learn/introduction/from-v1-to-v2). Le stock reste explicitement non vérifié.

## Interface client

Connexion par e-mail/mot de passe auprès de Medusa ; comptes de démonstration disponibles uniquement pour l'instance locale. JWT conservé seulement dans la session d'interface pour authentifier les requêtes, jamais affiché ou envoyé au modèle. Changement de compte : contexte affiché effacé. Le client voit la sélection, le récapitulatif exact de son approbation, une case d'accord et deux boutons. Le bouton de confirmation reste désactivé sans accord ; il appelle toujours `/actions/confirm`.

Après réponse serveur `done`, le message dit « panier créé », jamais « commande passée » ; le contenu est relu auprès de Medusa. Checkout, retour et ticket ont des formulations et statuts distincts. Les résultats de lecture des commandes et tickets sont tirés des objets observés, pas des promesses du modèle. Les erreurs ne montrent ni stacktrace ni corps privé. Une lecture en erreur efface la carte de panier affichée ; une carte conservée est étiquetée comme dernière consultation, pas comme vérification permanente.

Le mode développeur est désactivé par défaut. Il donne accès à un volet replié « Détails techniques (développeur) » avec une projection autorisée des IDs, arguments, références, statuts et mesures. Les réponses API structurées sont conservées pour les intégrations ; le volet n'affiche jamais les corps complets privés de Medusa.

## Mesures réelles — développement uniquement

Index lexical/dense inchangé : 55 documents, 217 passages ; empreinte `d2acf55d22f898a0159571020f4d2dc0dcca218dc3b7bcf21664b1d230cfcdcc`. Questions : quatre de diagnostic + six reformulations FR/EN. Labels de source examinés par l'agent, non approuvés humainement. Précision = proportion de sources distinctes pertinentes parmi celles retournées ; Recall@5 = présence du sous-flux attendu dans les cinq premiers résultats.

| Configuration | n | Recall@5 | Source correcte rang 1 | Précision moyenne des sources distinctes | Latence moyenne à chaud |
|---|---:|---:|---:|---:|---:|
| Baseline lexical enrichi par chunks | 10 | 4/10 | 2/10 | 0,20 | 1,28 ms |
| Lecture par documents | 10 | 10/10 | 9/10 | 0,80 | 1,55 ms |
| Baseline dense | 10 | 6/10 | 3/10 | 0,275 | 42,08 ms |
| Hybride existant | 10 | 8/10 | 2/10 | 0,192 | 25,40 ms |

Deux requêtes négatives : abstention retrieval 2/2 pour chaque configuration. La confusion rang 1 restante de la lecture documentaire concerne l'anglais username/password ; le filtre de sujet choisit ensuite Recover Username pour la réponse. Ces chiffres décrivent le jeu connu et cette machine. Ils ne prouvent ni généralisation ni gain de l'hybride. Les latences excluent démarrage, réseau et génération ; les valeurs P95 et candidats complets figurent dans `development.json`. Les anciens rapports/baselines ne sont pas réécrits.

Douze réponses réelles FastAPI → RAG → NVIDIA : 10 positives avec source attendue citée, 34 faits attestés par leurs extraits et traductions figées, abstention 2/2 sur les négatives, latence HTTP moyenne 1 531 ms. Tokens réellement fournis pour les 10 réponses positives ; coût monétaire non disponible. **Exactitude des citations/extraits ≠ fidélité sémantique indépendante** : fidélité humaine NOT_EVALUATED, n=0. Données détaillées dans `answers-development.json`.

## Tests et preuves

104 tests réussis : D01–D06, C01, nouveaux documents/import/rechargement conservés, synonymes et variations linguistiques, absence/source non pertinente/injection, citation encodée, historique et clients isolés, reset concurrent à une confirmation, propriété du panier, panier vide/inaccessible, montants et statuts absents, ticket sans commande, refus de faux succès, cartes Streamlit sans JSON, annulation et confirmation unique.

Ruff au profil CI, contrôle de secrets et deux quality gates existants : PASS. Les gates historiques vérifient leurs rapports/baselines existants ; ils ne sont pas une preuve d'évaluation finale indépendante du nouveau lecteur. Vérifications de retours existantes relancées : 401/403, receive_now 400, retour déjà demandé refusé et retour historique persisté. Aucun nouveau checkout ni nouveau retour autorisé n'a été exécuté pour cette intervention.

Parcours réel Streamlit/AppTest → HTTP FastAPI → Medusa, **sans mocks** : proposition annulée, nouvelle proposition de Sweatshirt M, case + bouton explicites, panier créé et relu, quantité 1 et montant réel 10 EUR, lecture « mon panier », second appel refusé 409, session étrangère 404, lecture directe du panier étranger refusée, reset puis absence de panier associé 404. Aucune nouvelle commande. Quatre questions de recherche dans la même UI ont réellement utilisé NVIDIA. Le premier smoke a créé un panier avant d'échouer sur N01 ; le second a passé, soit deux paniers de démonstration, aucun checkout. Voir `live.json` et `integration-first-failure.json`.

Le harnais AppTest exécute le vrai script Streamlit et ses requêtes, mais **aucun parcours manuel ni contrôle visuel dans un navigateur n'est revendiqué**. Le contrôle de l'affichage est structurel. Les scénarios de panne API sont automatisés avec erreurs simulées ; pas de panne destructive provoquée sur la boutique.

Docker et les services s'étaient arrêtés en cours de session ; redémarrage des conteneurs existants et des services sans seed, migration ni suppression de volume. Pytest a rencontré un refus d'accès au répertoire temporaire Windows dans le contexte effectif ; un répertoire temporaire unique ignoré sous `data/runtime` a permis les 104 tests. Ces incidents ne sont pas présentés comme des réussites initiales.

## Reproduire

Depuis `commerceops_ai`, avec les secrets uniquement dans `.env` ignoré :

```powershell
.\scripts\start.cmd check
$testScratch = 'data/runtime/pytest-v2-' + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp $testScratch -o cache_dir=data/runtime/pytest-v2-cache
.\.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.\.venv\Scripts\python.exe -m scripts.check_secrets
.\.venv\Scripts\python.exe -m scripts.quality_gate
.\.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
.\.venv\Scripts\python.exe -m scripts.evaluate_global_v2
# Appels publics au fournisseur configuré :
.\.venv\Scripts\python.exe -m scripts.evaluate_answers_v2
# Crée un nouveau panier local, explicitement confirmé dans le harnais UI :
.\.venv\Scripts\python.exe -m scripts.verify_global_v2_live --execute-live --documentary
```

`RAG_DOCUMENT_GROUPING=false` rétablit le lecteur de chunks ; `RAG_BACKEND=chroma` ou `hybrid` reste optionnel. Le script de comparaison historique V2 fixe explicitement grouping=false pour ne pas renommer silencieusement sa baseline. `scripts.verify_conversation_live` reste une entrée compatible vers le smoke courant. `reports/source_manifest.json` décrit l'index effectivement actif et les SHA des fichiers applicatifs.

## Limites et opérations non validées

Pas de revue humaine sémantique, pas de test indépendant exécuté. Le jeu final-v3 conserve son SHA initial `6b0e29ced596fe2458ff1ebdc1d2cf76f2816d479cadcf28ff1c924403aebced` ; seul son hash est lu, jamais ses questions pour ces ajustements. Les règles bilingues/de pertinence et les traductions reconnues restent limitées ; une procédure inconnue peut nécessiter une nouvelle annotation et sera refusée prudemment. Aucun score universel ou garantie d'absence de toute erreur n'est annoncé.

Le fichier final gelé a aussi été comparé octet par octet à sa version préparée dans l'index Git. Une règle `.gitattributes` empêche les conversions de fins de ligne de changer son SHA lors d'un checkout. Les correctifs et preuves sont indexés pour revue, avec un message de commit préparé ; aucun commit ni push de cette intervention n'est effectué.

La mémoire demeure canonique, bornée, liée à l'authentification ; la saisie sensible est filtrée par heuristiques, pas par un DLP exhaustif. Visiteurs non authentifiés : recherche stateless, pas de mémoire client persistante. Stock non vérifié, pas de paiement financier réel. SQLite et Medusa mono-instance restent adaptés à la démonstration locale ; aucune validation de charge/production, purge automatique ou nouvelle CI distante n'est revendiquée. Les compétences/MCP Medusa optionnels ne sont pas connectés ; la documentation officielle et les méthodes installées existantes ont servi de référence.
