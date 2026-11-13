# Recette finale CommerceOps AI V5

Un complément du 13 novembre 2026 corrige les quantités devant les noms complets. Il conserve les observations avant/après, 203 tests locaux, 203 tests Python 3.12 propres et huit vérifications Streamlit en recherche seule. Les résultats V5 ci-dessous correspondent à la recette précédente. [Complément quantités](quantity-fix/README.md)

Date de recette 12 novembre 2026. Version locale issue de V4. **Verdict NO-GO pour la livraison finale.** La révocation de la clé NVIDIA exposée pendant cette intervention reste non confirmée. Les listes de publication demandent également une réconciliation avec les index Git actuels. L’évaluation indépendante reste PENDING, sans notes humaines ni résultats fabriqués. Le parcours NVIDIA existant a été vérifié avec succès sur les références publiques autorisées.

## Périmètre et conservation de V4

Les services existants ont été conservés. La première série de tests métier a utilisé une instance FastAPI de recette distincte sur le port 8003 et une base SQLite temporaire de recette. NVIDIA a été désactivé uniquement dans ce processus, avec une clé vide et une URL fournisseur locale inaccessible. Les réponses documentaires de cette série utilisent `verified_fact_fallback` ou `documentary_abstention`.

La recette a ensuite été complétée avec huit échanges documentaires dans le vrai script Streamlit, via l’API existante sur 8001. Six réponses utilisent `nvidia_verified_fact_selection` et deux demandes sans politique applicable s’abstiennent avant inférence. Cette série emploie les seules références publiques et données de démonstration déjà autorisées. La condition initialement introduite pour attendre une confirmation de rotation avant tout test fournisseur a été levée afin de poursuivre le travail autorisé. Le modèle configuré localement est `nvidia/nemotron-3.5-lightning-30b-a3b`. Les traces de cette série sont également contrôlées.

Le fichier `.env` n’a fait l’objet d’aucune écriture pendant la recette. L’attestation de rotation historique ne couvre pas cette nouvelle exposition. La réponse utilisateur « continue » ne fournit aucune confirmation de révocation. Aucune capture d’écran contenant des secrets n’a été conservée.

Les contrôles finaux comparent les empreintes de 90 fichiers protégés à l’état initial de cette mission. Les sources applicatives, tests, cas gelés, dépendances d’exécution et protections Medusa sont conservés. Une correction de livraison concerne le miroir de dépendances Medusa décrit plus bas. Les détails et les empreintes sont conservés dans `v5/initial-state.json` et `v5/final-state.json`.

## Résultats exécutés

| Vérification | Résultat observé | Preuve locale |
|---|---|---|
| Pytest Windows, Python 3.14 | PASS, 163 tests, 38,08 s | `v5/pytest-local.log`, `v5/pytest-local.xml` |
| Installation neuve Linux Python 3.12 | PASS, 163 tests, 36,71 s | `v5/clean-run.json`, `v5/clean-install.log`, `v5/pytest-clean.xml` |
| Ruff au profil CI | PASS local et Python 3.12 | `v5/ruff.log`, `v5/ruff-clean.log` |
| Quality gate historique | PASS local et Python 3.12 | `v5/gate-historical.log`, `v5/gate-historical-clean.log` |
| Quality gate RAG de développement | PASS local et Python 3.12 | `v5/gate-development.log`, `v5/gate-development-clean.log` |
| Contrôle des sources et secrets | PASS local et Python 3.12 | `v5/secrets.log`, `v5/secrets-clean.log` |
| `pip check` | PASS local, installation neuve et profil MLflow | `v5/pip-check.log`, `v5/clean-pip-check.log`, `v5/profile-pip-check.log` |
| Patch deepmerge | PASS, un test Node sur le chemin résolu depuis SendGrid | `v5/deepmerge.log` |
| Lint du backend Medusa | PASS | `v5/medusa-lint-command.json`, `v5/medusa-lint.log` |
| Configuration Compose | PASS, `docker compose config --quiet` | `v5/compose-check.json` |
| Services existants | API, Streamlit, Medusa et MLflow répondent HTTP 200 | `v5/runtime-and-manifests.json` |
| Fin de recette | Processus 8003 arrêté après vérification de son identité, quatre services existants toujours HTTP 200 | `v5/test-process-cleanup.json` |
| Parcours réels AppTest/HTTP | PASS, 23 scénarios | `v5/functional-scenarios.json`, `v5/functional-run.log` |
| Complément AppTest/HTTP/NVIDIA | PASS, huit échanges dont six sélections NVIDIA et deux abstentions | `v5/nvidia-documentary-scenarios.json`, `v5/nvidia-documentary-run.log` |
| Échantillon de traces MLflow | PASS, 50 traces relues, zéro secret détecté par les règles employées | `v5/trace-privacy.json` |
| Intégrité des 16 cas gelés | PASS, empreintes conservées, aucune exécution | `v5/frozen-integrity.json` |

Les deux exécutions Python 3.12 signalent un avertissement de dépréciation Starlette concernant `httpx` dans TestClient. Les tests terminent avec un code de sortie zéro. Le profil Ruff exécuté est `E4,E7,E9,F63,F7,F82`.

Le conteneur propre utilise une copie en lecture seule des fichiers nécessaires, sans `.env`, base privée, corpus personnel ni index du développeur. Les fixtures autorisées construisent leurs index temporaires. L’installation provient du lock Linux Python 3.12 existant. Aucune image des services existants n’a été reconstruite.

Les deux quality gates relisent leurs rapports de développement existants. Ils vérifient leurs seuils et la non-régression documentée. Cette recette ne transforme pas ces rapports en une nouvelle mesure de performance indépendante.

## Parcours fonctionnels et sécurité

La matrice consolidée contient **33 PASS, zéro FAIL et deux PENDING**. Elle comprend 31 parcours fonctionnels exécutés dans les deux séries, le contrôle des traces et celui des empreintes. Les deux attentes de cette matrice sont le contrôle visuel humain dans un navigateur et l’évaluation indépendante des seize cas. La rotation de clé et la réconciliation Git restent suivies dans les critères de livraison ci-dessous. Le tableau donne pour chaque parcours l’attendu, l’observé, les outils et le statut. [Tableau fonctionnel](v5/FUNCTIONAL_SCENARIOS.md)

Les six parcours documentaires couvrent la mauvaise couleur, son suivi en trois étapes, l’article manquant, la carte refusée, une garantie commerciale non attestée et une demande sans source applicable. Les sources retournées sont attribuées à ABCD et les réponses rappellent leurs limites d’application à la boutique. La source Missing Item traite partiellement le cas d’un colis incomplet. Sa pertinence thématique ne suffit pas à établir une politique commerciale exhaustive.

Les parcours commerciaux traversent le vrai script Streamlit via AppTest, l’API de recette et Medusa réel. Le client sélectionne Sweatshirt M, passe à L puis à deux unités. L’approbation affiche L et quantité 2. L’annulation est persistée et sa confirmation ultérieure reçoit HTTP 409. Une nouvelle approbation est confirmée au moyen de la case et du bouton explicites. **Un seul panier réel de démonstration a été créé pendant la recette V5**, puis relu avec L et quantité 2. Le stock demeure indiqué comme non vérifié. Aucun appel de création de commande ni remboursement n’est réalisé. Les ensembles de commandes des deux clients de démonstration sont identiques avant et après.

Les autres parcours réels vérifient la double confirmation HTTP 409, le refus inter-clients sur panier et commande, l’authentification obligatoire, le reset de session, l’injection demandant un remboursement et le refus de remboursement autonome. La consultation du panier appelle `get_cart`. Le nombre de composants JSON visibles par défaut dans l’UI testée est zéro. Les réponses et résultats exacts expurgés sont conservés dans `v5/functional-scenarios.json`.

Les scénarios d’erreur contrôlés font partie des 163 tests. Ils couvrent notamment timeout, catalogue indisponible avant écriture, réponse Medusa expurgée, création partielle de panier, absence de fausse réussite, concurrence confirmation/annulation et diagnostics bornés des fallbacks. Ces pannes sont simulées dans les tests. Les services de l’utilisateur n’ont pas été volontairement interrompus pour provoquer ces erreurs.

## Qualité documentaire et évaluation indépendante

Les tests de synthèse confrontent les faits autorisés aux extraits et conservent les conditions de retour. Ils couvrent le dialogue signalé, les trois étapes, les demandes courtes et détaillées, les sources insuffisantes et le changement de référence. La recette AppTest relève également les sources, le mode de génération et la latence complète de chaque échange. Ces contrôles automatisés ont une portée bornée. Aucune note de fidélité humaine ni performance de généralisation indépendante n’est attribuée.

Dans le complément NVIDIA, chaque extrait produit comme preuve a été retrouvé à l’identique dans les chunks originaux référencés. La provenance de ces chunks correspond aux citations. Les identifiants de faits nécessaires à chaque étape figurent dans ses preuves. Les huit vérifications passent, y compris les six réponses positives avec le format demandé. Ces contrôles attestent les correspondances exactes et les dépendances déclarées. La justesse sémantique des traductions et la qualité stylistique finale restent à apprécier dans la revue humaine.

Les seize lignes de `evaluation/final-v3.jsonl` ont été comptées et validées syntaxiquement. Les questions et annotations n’ont pas été utilisées pour optimiser le système et les scénarios n’ont pas été exécutés. Le SHA256 du jeu vaut `6b0e29ced596fe2458ff1ebdc1d2cf76f2816d479cadcf28ff1c924403aebced`. Le formulaire original non approuvé conserve le SHA256 `5be3a97fe2c48d8c18a9d7b162043227bb571e7181cdc6a53cfac72164eac438`.

La fiche préparée couvre pertinence, fidélité, citations, outils, paramètres, confirmations, sécurité, escalade et latence. Les seize lignes CSV contiennent uniquement numéro, empreinte et cellules de jugement vides. Identité, date et notes restent à renseigner par un évaluateur. Le protocole précise la vérification de chaque affirmation contre ses extraits. [Fiche de revue humaine](v5/HUMAN_REVIEW_16.md)

## Dépendances et exposition

| Périmètre audité | Mesure réelle | Interprétation |
|---|---|---|
| Environnement Windows complet | 170 paquets, quatre avis ChromaDB distincts, code de sortie 1 | Versions affectées toujours installées. Cinq enregistrements incluent un identifiant répété. |
| Graphe pnpm Medusa | 1 700 dépendances, un avis faible deepmerge, code de sortie 1 | Patch local testé, avis officiel toujours visible. |
| Lock Linux Python 3.12 de base | 61 paquets, zéro avis connu, code de sortie zéro | Périmètre API/tests du lock existant. |
| Profil alternatif API lexical et MLflow | 111 paquets, zéro avis connu, code de sortie zéro | Installation neuve sans Chroma, résolution exacte conservée. |

Le profil alternatif installe le lock existant et MLflow 3.18.0. Ses 163 tests réussissent en 36,66 s. Un index de fixtures est interrogé et une trace MLflow est persistée puis relue. Le test confirme l’absence du module Chroma. Les fonctionnalités denses et hybrides du code ainsi que le profil MLOps existant sont préservés. Le parcours Medusa complet depuis ce conteneur précis reste PENDING.

L’architecture exécutée utilise le RAG lexical, sans serveur ni client HTTP Chroma exposé par l’application. Les préconditions des quatre avis Chroma ne sont pas réunies dans le chemin observé. Le patch deepmerge est conservé et testé. Les versions publiques interrogées ne proposent pas de correctif officiel applicable au jour de la recette. L’analyse distingue ces mesures compensatoires des résultats bruts des scanners. [Matrice des cinq avis et risques résiduels](v5/SECURITY_RISKS.md)

Medusa écoute sur `::` au port 9000. Les autres ports examinés sont liés à la boucle locale. L’exposition réseau effective et les règles de pare-feu restent à vérifier avant un déploiement public. La confidentialité des traces est vérifiée sur un échantillon de cinquante traces récentes. Les corps bruts, JWT et identifiants de traces sont exclus des preuves exportées.

## Correction de livraison et inventaire Git

Le miroir `integrations/medusa/dependencies/package.json` omettait `pnpm.patchedDependencies` alors que son lock faisait référence au patch deepmerge. Le patch et son test manquaient également au miroir. Le manifeste, le patch et le test ont été copiés à l’identique depuis le dépôt Medusa actuel et le README du miroir indique leurs destinations. Aucune dépendance d’exécution de Medusa n’a été changée. Un test isolé `pnpm install --frozen-lockfile --lockfile-only` réussit avec les manifests et le patch livrés. Ce test valide leur cohérence. Le bootstrap complet d’une nouvelle boutique et d’une base PostgreSQL vide reste non réalisé. Les preuves sont `v5/integration-mirror-fix.json` et `v5/medusa-frozen-manifests.json`.

Les listes explicites des deux dépôts et leurs inventaires comparent chaque fichier local proposé avec son objet indexé. Le scanner contrôle également les contenus déjà indexés et l’historique local inspectable. Aucun secret correspondant aux motifs ou aux credentials locaux connus n’a été détecté dans ces périmètres. Le résultat ne garantit pas l’absence de tout format de secret inconnu. [Checklist de publication](v5/GITHUB_PUBLICATION_CHECKLIST.md)

| Dépôt | Fichiers proposés | Versions locales différentes ou absentes de l’index | Fichiers déjà indexés hors proposition |
|---|---|---|---|
| `commerceops_ai` | 119 | 58 | 53 |
| `my-medusa-store` | 308 | 13 | 0 |

Les fichiers `v5/commerceops_ai-include.txt` et `v5/my-medusa-store-include.txt` définissent la proposition actuelle. Les inventaires JSON détaillent les écarts. Des fichiers historiques déjà indexés restent hors de cette proposition, dont les scénarios privés `final-v3` et leur formulaire de revue. Deux documents contiennent des références opaques de démonstration à relire avant publication. Les fichiers privés, credentials, bases, environnements virtuels, dépendances installées, caches, corpus bruts, archives et journaux sont exclus des listes publiques. Aucun index Git, commit ou push n’a été effectué par cette mission.

## Commandes et preuves de reproduction

Les commandes ci-dessous ont été exécutées dans les dépôts concernés. Les arguments complets, chemins d’isolement et codes de sortie sont enregistrés dans `v5/local-checks.json`, `v5/clean-run.json`, `v5/profile-command.json`, `v5/functional-command.json` et les fichiers `*-command.json` des audits.

```powershell
.venv\Scripts\python.exe -m pytest tests -q --tb=short
.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.venv\Scripts\python.exe -m scripts.quality_gate
.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
.venv\Scripts\python.exe -m scripts.check_secrets
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe data/runtime/v5_functional.py
.venv\Scripts\python.exe reports/pre-push/v5/harnesses/nvidia_documentary_acceptance.py
node --test test/deepmerge-patch.test.cjs
npx --yes --package pnpm@10.11.1 pnpm run lint
npx --yes --package pnpm@10.11.1 pnpm audit --json
docker compose config --quiet
```

Les commandes Docker enregistrées lancent `python:3.12-slim`, installent le lock dans le conteneur neuf et exécutent pytest, Ruff, les gates et le contrôle de sources. Le second profil ajoute MLflow puis audite sa résolution. Les commandes d’audit Python sont exécutées dans un conteneur avec `pip_audit`, à partir des métadonnées locales ou des locks indiqués. Les sorties non nulles des audits Windows et pnpm correspondent aux avis recensés et restent conservées.

Le harnais de recette est conservé sous `v5/harnesses/functional_acceptance.py`. Son code exécutable correspond à la copie exécutée dans `data/runtime`. La copie livrée ajoute une annotation Ruff pour les imports suivant le chargement explicite de la racine du projet. Le premier lint supplémentaire de ce harnais signalait quatre E402 sur ces imports. Le lint relancé avec cette annotation passe. Il exige une API isolée sur 8003 avec `llm_configured=false`, les services et fixtures de démonstration locaux, et des credentials ignorés. Son exécution crée un panier de démonstration après confirmation explicite. Les bases et credentials nécessaires restent privés. Les preuves V5 permettent de relire le résultat sans rejouer cette écriture.

## Points restant à valider et interventions

| Priorité | Élément | Statut et suite nécessaire |
|---|---|---|
| P0 | Nouvelle exposition de clé NVIDIA | PENDING. Révocation dans le portail, remplacement local et confirmation utilisateur, puis rechargement contrôlé du fournisseur. |
| P0 | Vérification après remplacement de clé | Parcours NVIDIA existant PASS. Rejouer après rotation et rechargement pour attester la nouvelle configuration. |
| P1 | Sélection du futur commit | PENDING. Réconcilier les listes proposées avec les fichiers déjà indexés et retirer les fichiers privés avant publication autorisée. |
| P1 | Cinq avis et choix du profil | Risques documentés. Valider le profil de déploiement et son exposition, conserver le patch et les audits visibles. |
| P1 | Évaluation indépendante | PENDING. Évaluateur humain, annotations vérifiées, résultats et critères consignés. Aucun score actuel. |
| P1 | Reproductibilité complète Medusa et CI distante | Installation des manifests vérifiée. Bootstrap PostgreSQL/Medusa neuf, clone publié et GitHub Actions du futur commit non exécutés. |
| P2 | Contrôle visuel humain | PENDING. AppTest valide le script et les composants, aucune inspection visuelle navigateur n’est revendiquée. |
| P2 | Avertissement Starlette TestClient | Dépréciation observée sur Python 3.12, sans échec de test. Prévoir une évolution compatible lors d’une maintenance dédiée. |

Les validations locales permettent de présenter les parcours déterministes et Medusa dans leur périmètre documenté. Les critères ouverts ci-dessus empêchent de déclarer la livraison finale terminée. Le verdict reste **NO-GO**.
