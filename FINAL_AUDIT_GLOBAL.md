# Audit fonctionnel global CommerceOps AI

Recette du 13 novembre 2026 sur la dernière version locale. **Verdict de publication NO-GO.** Les corrections et les parcours locaux décrits ici passent. La dernière exposition de clé NVIDIA n'a pas d'attestation de révocation/remplacement, l'index Git contient encore une sélection ancienne, et la revue indépendante des seize cas reste en attente. Aucun commit ni push n'a été réalisé.

## Résultats vérifiés

| Vérification | Résultat réel | Preuve |
|---|---|---|
| Pytest complet local, Python 3.14 | 267 réussis, 0 échec, 0 ignoré | `reports/pre-push/global/pytest-local.log`, `.xml`, `pytest-local-command.json` |
| Installation Linux Python 3.12 propre | 267 réussis, 0 échec, un avertissement de dépréciation Starlette/httpx | `pytest-clean.log`, `.xml`, `clean-run.json`, `python312.lock.txt` dans le même dossier |
| Nouvelles régressions globales | 64 cas, dont 61 captures de dialogues et états persistants | `unit-cases.jsonl`, `tests/test_global_acceptance.py` |
| Ruff CI | PASS, code retour 0 | `ruff.log`, `ruff-command.json` |
| Deux quality gates | PASS en local et environnement propre | `gate-historical*.log`, `gate-development*.log` |
| Source/secrets et pip check | PASS local et propre | `secrets*.log`, `pip-check.log`, `clean-pip-check.log` |
| Middleware Medusa et patch deepmerge | 5 tests Node réussis, 0 échec | `medusa-security.log`, `medusa-security-command.json` |
| Lint officiel Medusa | PASS | `medusa-lint.log`, `medusa-lint-command.json` |
| Streamlit AppTest → FastAPI → Medusa/NVIDIA | 25 scénarios PASS | `live-scenarios.json`, `live-prepare.log`, `live-finish.log` |
| Fidélité structurelle des réponses observées | 20 unités rendues confrontées aux citations originales et à leur provenance | `documentary-grounding.json` |
| MLflow persisté | 50 traces récentes inspectées, aucune correspondance de secrets détectée, deux confirmations HTTP corrélées | `trace-privacy.json` |
| Services disponibles | FastAPI, Streamlit, Medusa, MLflow HTTP accessibles, PostgreSQL/Redis TCP accessibles | `services-health.json` |
| Cas finaux gelés | Empreintes inchangées, aucune exécution | `frozen-integrity.json` |
| Git | HEAD et index des deux dépôts inchangés | `changes.json`, deux inventaires de publication |

Ces nombres ne sont pas additionnés entre environnements. Les tests synthétiques utilisent un transport HTTP simulé et des bases temporaires. Les 25 scénarios réels utilisent les services locaux et les seuls comptes de démonstration autorisés. Aucun ordre de paiement, remboursement, retour exécuté ou nouvelle commande n'a été créé. Les pannes et courses concurrentes sont injectées en tests, sans provoquer volontairement une panne de la boutique réelle.

Les gates relisent les artefacts de développement existants et leurs baselines. Leur succès ne constitue pas une nouvelle mesure indépendante de Recall@5, de fidélité humaine ou de réussite agentique. Aucune amélioration statistique de retrieval n'est revendiquée.

## Causes et corrections

La [matrice des causes](ROOT_CAUSE_ANALYSIS.md) précède les changements structurels pour RC-01 à RC-12 et précise la chronologie des constats suivants. Le routage était partagé entre plusieurs couches, le fournisseur pouvait produire de la prose hors périmètre, et le contexte commercial ne conservait qu'une sélection unique. Les projections retiraient les options/prix et limitaient les premiers produits ou variantes. Cela explique les pertes de contexte, substitutions, erreurs de couleur et remplacements de lignes.

`interpreter.py` centralise les intentions et les critères. Les titres, catégories, tailles, couleurs et prix viennent du catalogue complet. Une donnée manquante ou ambiguë appelle une clarification. Les produits inconnus ne reprennent pas silencieusement la variante précédente. La priorité des quantités explicites, corrections et limites 1 à 20 est conservée. Stock réel toujours annoncé non vérifié.

`shopping.py` distingue discussion, brouillon multiligne, approbation et panier réel. Une action `prepare_cart_items` photographie chaque ligne et le panier cible. Avant confirmation, l'API relit le catalogue et le panier, compare les caractéristiques exactes, options et prix, puis réclame l'approbation à usage unique et réserve le panier. Un simple « oui » ne fait qu'exposer l'approbation. La case et le bouton Streamlit déclenchent `/actions/confirm`.

Le connecteur applique les opérations approuvées au même panier, avec lecture après chaque écriture. Une réponse perdue mène à une réconciliation en lecture, sans répétition de la requête d'écriture. Un état partiel ou non confirmé conserve `needs_review` et bloque les modifications concurrentes. La procédure opérateur est dans [MEDUSA_UNCERTAIN_WRITES.md](docs/MEDUSA_UNCERTAIN_WRITES.md). Les écritures Medusa ne sont pas atomiques entre plusieurs endpoints.

Une fuite d'autorisation supplémentaire a été confirmée directement dans la Store API Medusa. Avant correction, un panier client était lisible par son propriétaire, un autre client et un visiteur, tous HTTP 200. Le middleware vérifie désormais la propriété des paniers rattachés à un client pour lectures et mutations de lignes. Les mêmes lectures donnent 200/403/403. Un ajout direct étranger est refusé 403, sans changement du panier. Le parcours des paniers anonymes reste autorisé et testé au niveau du middleware. Finalisation et retour gardent leurs contrôles stricts. Les copies d'intégration sont synchronisées avec le backend réellement testé.

La migration SQLite est additive. Les sessions antérieures sont adaptées au schéma JSON 2 lors de leur lecture et conservent leur sélection. Les paniers terminés restent lisibles. Une ancienne approbation en attente dont la photographie ne comportait pas les libellés d'options est invalidée et doit être renouvelée. Les confirmations `confirmed` interrompues et les états `needs_review` ne sont jamais déverrouillés sur un simple délai.

## Preuve du panier réel

Le scénario cible a été réalisé via AppTest, sans mock HTTP. Les tailles S puis M ont été sélectionnées, puis la quantité de M corrigée à deux. Le brouillon contient S × 1 et M × 2. « Oui » prépare une approbation multiligne, avec le bouton désactivé tant que la case n'est pas cochée.

FastAPI a été arrêté puis relancé avec la même base. La même approbation et ses arguments ont été relus. Après confirmation explicite dans Streamlit, Medusa retourne deux lignes S × 1 et M × 2 dans un seul nouveau panier client de démonstration. La consultation suivante appelle uniquement `get_cart`. Un T-shirt M noir × 1 a ensuite été approuvé et ajouté au même panier, en conservant les deux premières lignes. Le total affiché provient de Medusa.

Une répétition de confirmation retourne 409. Le client B reçoit 404 pour session, panier de session et approbation, puis 403 pour lecture et ajout directs dans Medusa. L'état du panier propriétaire reste inchangé. Une proposition supplémentaire a été annulée dans Streamlit, sa confirmation retourne 409. Après reset, le lien de session disparaît et le panier reste conservé chez Medusa. Les identités des commandes du client sont identiques avant/après.

Les identifiants de démonstration sont remplacés dans la preuve publique. Le checkpoint privé ignoré permet de relire les références sur ce poste. Une relance du script terminé n'effectue aucune écriture. Les tableaux détaillés et les attentes sont dans [FUNCTIONAL_TEST_MATRIX.md](FUNCTIONAL_TEST_MATRIX.md).

## Avant et après réellement capturés

| Demande ou contexte | Avant | Après |
|---|---|---|
| Question politique hors périmètre | Affirmation politique erronée produite par le fournisseur | Redirection explicite vers l'assistance boutique, aucun outil |
| « Est-ce que vous vendez du café ? » | « Non, je suis un modèle de langage développé par des chercheurs de NVIDIA. » | Lecture `search_products`, produit non confirmé au catalogue, aucune déclaration d'identité NVIDIA |
| Injection demandant les commandes d'autres clients | Abstention documentaire générique après `search_knowledge` | Refus explicite d'accès aux données d'autres clients, aucun outil |
| Sweatshirt S avec couleur bleue non fournie par le catalogue | Sélection S malgré la couleur non vérifiée | Limite couleur explicitée, pas de sélection résolue ni d'approbation |
| Produit « cappuchon » après sweatshirt connu | Réutilisation du sweatshirt précédent | Clarification de produit absent, aucune substitution |
| S puis ajouter M puis M × 2 | État unique remplacé par M × 2 | Brouillon et panier réel S × 1, M × 2 |

Les formulations intégrales, outils et sélections sont conservés dans `reports/pre-push/global/before-after.json`. L'affirmation politique initiale y est une preuve d'erreur, pas un fait présenté comme vrai.

## RAG et NVIDIA

Le modèle configuré pendant la recette est `nvidia/nemotron-3.5-lightning-30b-a3b`. Le backend actif est lexical et l'index existant `data/rag-v2/index.json`. Aucun fine-tuning, remplacement du retrieval ou ajustement sur les seize cas gelés.

Les quatre formats successifs de la procédure couleur passent par le sélecteur de faits NVIDIA réel, puis un rendu français borné aux faits validés. Le résumé réel donne trois étapes distinctes, vérification d'achat et d'adhésion, préparation conditionnelle de l'étiquette après acceptation, choix entre les modes cités par ABCD. Les conditions, la réserve sur l'éligibilité locale, la protection de l'adresse et la citation sont conservées. Les procédures ABCD ne sont jamais présentées comme les politiques officielles de la boutique Medusa.

La vérification associe chaque unité rendue à ses extraits anglais originaux et à la provenance citée. Elle contrôle par exemple que l'étiquette reste conditionnée par l'acceptation et que les trois modes sont attribués au scénario ABCD. La présence d'une citation seule n'est pas utilisée comme preuve de fidélité. La validité de toute la reformulation française n'a pas de note humaine indépendante. La garantie officielle non confirmée et la politique de livraison sur Mars produisent une abstention.

Les outils indisponibles, retrieval en panne, réponse fournisseur libre erronée, JSON mal formé, timeout et métadonnées d'usage mal formées sont couverts en tests. Une panne de retrieval est distinguée d'une recherche terminée sans source. Le pipeline borne ses traductions/faits et peut refuser prudemment une procédure nouvelle non prise en charge.

## Dépendances et sécurité résiduelle

Audit Python de 170 distributions, quatre avis Chroma uniques. La sortie contient deux entrées pour le même `PYSEC-2026-311`, comptées une seule fois. Audit JavaScript de 1 700 dépendances, un avis faible deepmerge. Les deux audits retournent 1 en raison des avis, sans suppression artificielle. Les fichiers de dépendances et lockfiles n'ont pas été remplacés massivement.

| Avis | Applicabilité examinée | Réduction du risque et statut |
|---|---|---|
| [GHSA-f4j7-r4q5-qw2c](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c), Chroma 1.5.9, critique | Chargement distant de modèle avec `trust_remote_code` dans un serveur Chroma | Aucun serveur Chroma exposé ni client HTTP Chroma dans le parcours inspecté. Lexical actif. Pas de version corrigée publiée selon le registre et l'avis consultés. Reste signalé. |
| [GHSA-36p7-vc44-83pf](https://github.com/advisories/GHSA-36p7-vc44-83pf), critique | Mise à jour de collection et code distant sous permissions serveur | Même réduction d'exposition. L'option dense embarquée reste facultative, ne pas la transformer en serveur public sans réaudit. Reste signalé. |
| [GHSA-xph7-9rjv-w5fr](https://github.com/advisories/GHSA-xph7-9rjv-w5fr), élevé | Portée SimpleRBAC et collections serveur | Pas de service Chroma multi-utilisateurs dans cette architecture locale. Aucun correctif upstream disponible dans le contrôle exécuté. Reste signalé. |
| [GHSA-2wm9-hf6c-p5cr](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr), élevé | Accès croisé entre tenants authentifiés du serveur | Pas de serveur/tenants Chroma exposés. Ce constat limite l'exposition actuelle, sans corriger la bibliothèque. Reste signalé. |
| [GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4), deepmerge 4.3.1, faible | Le chemin SendGrid de Medusa utilise réellement deepmerge | Patch pnpm existant conservé sur CommonJS/UMD, test du chemin installé PASS. L'avis upstream reste visible. |

Les versions les plus récentes consultées restent Chroma 1.5.9 et deepmerge 4.3.1. Sources, commandes et sorties sont dans `python-audit.json`, `node-audit.json`, `vendor-versions.json`, les fichiers `*-audit-command.json` et `dependency-matrix.json`. Aucun « zéro vulnérabilité » n'est revendiqué pour l'environnement complet. Le profil lexical/MLflow sans Chroma validé historiquement en V5 n'est pas présenté comme une nouvelle recette complète de cette version globale.

Le contrôle des 50 traces récentes recherche JWT, jetons fournisseur, clés privées, bearer et correspondances exactes des secrets locaux/credentials de démonstration, sans exporter leur valeur. Sa portée est bornée, pas une preuve d'absence de tout secret possible. La clé exposée dans le contexte IDE doit être révoquée et remplacée par l'utilisateur, sans la coller dans le chat. Les secrets n'ont pas été modifiés pendant cette mission. Les authentifications de production, infrastructure distribuée et exposition réseau publique n'ont pas été qualifiées.

## Reproduction et commandes

Depuis `commerceops_ai`, commandes effectivement exécutées, avec répertoire temporaire dédié sous Windows lorsque nécessaire.

```powershell
.venv\Scripts\python.exe -m pytest tests -q --tb=short --basetemp data/runtime/<unique> -p no:cacheprovider --junitxml=reports/pre-push/global/pytest-local.xml
.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.venv\Scripts\python.exe -m scripts.quality_gate
.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
.venv\Scripts\python.exe -m scripts.check_secrets
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m scripts.verify_global_acceptance prepare
.venv\Scripts\python.exe -m scripts.verify_global_acceptance finish
.venv\Scripts\python.exe -m scripts.verify_global_evidence
.venv\Scripts\python.exe -m scripts.publication_inventory
```

La phase `prepare` est suivie du redémarrage contrôlé de FastAPI 8001, sans reconstruire de service ni réinitialiser les bases, puis de `finish`. Les scripts de recette réelle sont réservés à des démos locales autorisées. Le checkpoint privé empêche de recréer le panier quand la recette terminée est relancée. Ne pas le supprimer pour contourner un état incertain.

La reproduction propre utilise réellement `docker run --rm` avec `python:3.12-slim`, une copie expurgée en lecture seule et `pip install -r requirements-linux-py312.lock.txt`, puis tests, Ruff, deux gates, secrets et pip check. La commande Docker intégrale et le résultat sont dans `clean-run.json`. Aucun `.env`, credential, index personnel ou base privée n'est nécessaire aux tests. La CI inclut désormais pip check et les deux gates. La CI distante du futur commit reste non exécutée.

Depuis `my-medusa-store/apps/backend`, `node --test test/deepmerge-patch.test.cjs test/cart-ownership.test.cjs` et `npx.cmd --yes --package=pnpm@10.11.1 pnpm run lint` ont réussi. L'audit Python utilise `pip_audit --path /installed --format json` dans Docker sur les distributions réellement installées. L'audit Node utilise `pnpm audit --json`. Les commandes complètes sont conservées.

Les sorties intermédiaires sont gardées, notamment une segmentation documentaire ayant perdu le contexte couleur, corrigée, puis cinq erreurs d'isolation de test dans le premier conteneur Python 3.12, corrigées en ciblant la frontière fournisseur. Un lancement sans `--basetemp` a été refusé par les permissions Temp Windows, résolu par un répertoire unique du projet. Les wrappers PowerShell de la recette UI ont renvoyé 1 à cause des messages stderr AppTest malgré les 25 assertions réussies. Les captures complètes et le checkpoint attestent la fin du parcours. Les contrôles finaux emploient `subprocess.run` pour conserver le vrai code retour, notamment contrôle des preuves 0 et relance sans écriture 0. Ces anomalies de lancement ne sont pas masquées comme des résultats fonctionnels.

La première reprise du script de recette lisait son checkpoint UTF-8 avec le défaut Windows cp1252. Cela a altéré les accents des premières captures reprises, sans modifier les valeurs métier ni les réponses de l'API. Le script lit désormais explicitement UTF-8. Les 125 chaînes concernées ont été récupérées par l'inverse exact de cette conversion, sans régénérer ni réécrire les réponses. La preuve brute et la trace de conversion sont conservées localement dans `live-scenarios-encoding-original.json` et `encoding-recovery.json`. Aucun panier n'a été recréé pour cette correction de preuve. Une vérification documentaire réelle supplémentaire en lecture seule contrôle l'UTF-8 et les trois étapes dans `utf8-readonly-recheck.json`.

## Fichiers et publication

La liste exacte des sources modifiées pour cette mission et leurs empreintes figure dans `reports/pre-push/global/changes.json`. Elle distingue les fichiers applicatifs comparés au snapshot initial et les livrables/documentation. Les inventaires Git complets incluent aussi les changements antérieurs encore locaux, sans les attribuer artificiellement à cette mission.

Dans `commerceops_ai`, changements de code `app/agent.py`, `api.py`, `catalog.py`, `conversations.py`, `documentary.py`, `medusa.py`, `presentation.py`, `storage.py`, `ui.py`, nouveaux `app/interpreter.py` et `app/shopping.py`. Tests `tests/conftest.py`, `test_safety.py`, nouveau `test_global_acceptance.py`. Nouveaux outils `scripts/verify_global_acceptance.py`, `verify_global_evidence.py`, `publication_inventory.py`. CI `.github/workflows/ci.yml`. Documentation et miroir Medusa énumérés dans le manifeste.

Dans `my-medusa-store`, seuls `apps/backend/src/api/commerceops-ownership.ts`, `middlewares.ts`, `apps/backend/package.json` et le nouveau `apps/backend/test/cart-ownership.test.cjs` sont modifiés pour cette mission. Les autres changements locaux préexistants et le patch deepmerge restent conservés. Aucun lockfile ni secret modifié pour la mission globale.

`app/documentary_format.py` fait bien partie de la sélection de publication, avec les nouveaux modules. Les deux listes explicites sont `reports/pre-push/global/commerceops_ai-include.txt` et `my-medusa-store-include.txt`. Les inventaires JSON comparent chaque fichier à son contenu indexé. Leur sélection exclut `.env`, credentials, JWT, bases, datasets bruts, caches, environnements, archives temporaires et journaux sensibles. Aucun `git add .` exécuté.

La [checklist de publication](reports/pre-push/global/PUBLICATION_CHECKLIST.md) détaille les tâches restantes et les sélections. Les 53 fichiers de l'ancien index CommerceOps extérieurs à la première sélection de cette mission ne sont pas automatiquement publiés ou désindexés. Les documents contenant encore des références métier de démonstration exigent une revue avant export public. Les fiches humaines vierges restent dans `reports/pre-push/v5/HUMAN_REVIEW_16.md` et `.csv`, sans note inventée.

## Limites et critères bloquants

- Rotation de la dernière clé exposée non attestée. Confirmation utilisateur nécessaire, suivie d'un contrôle de fonctionnement après remplacement.
- Seize cas finaux non exécutés, revue indépendante et fidélité sémantique humaine PENDING. Aucun ajustement de leurs questions ou annotations.
- Inspection visuelle humaine, vidéo universitaire et validation du PDF pour les nouvelles fonctionnalités non réalisées. Le PDF historique décrit sa propre version, pas cette architecture globale complète.
- CI distante du futur commit et installation intégrée complète sur une seconde machine non réalisées. Le conteneur propre valide le périmètre Python, pas une nouvelle boutique PostgreSQL/Redis reconstruite.
- Paniers anonymes préservés par tests du vrai middleware, sans création supplémentaire de panier réel pour cette sous-vérification. Pas de scénario financier, commande, remboursement ou retour exécuté pendant cette mission.
- Avis de dépendances toujours présents. Ne pas exposer un serveur Chroma ni accepter des modèles distants non fiables. Déploiement public à réauditer.
- Routage et synthèse documentaire bornés, sans preuve de généralisation universelle. La pagination complète privilégie la correction et peut devenir coûteuse avec un grand catalogue. Aucune mesure à grande échelle effectuée.
- Pas d'atomicité inter-endpoints Medusa ni de récupération automatique d'une écriture incertaine après crash. Un opérateur doit vérifier l'état réel et les verrous persistants avant une nouvelle action.

Le fonctionnement local démontré est livré pour revue. L'autorisation de publication reste distincte de ces résultats techniques.
