# Audit final avant publication GitHub

Date de l’audit — 12 novembre 2026.

**Verdict final NO-GO.** La publication de la version prête à présenter demande le traitement des défauts P1 ci-dessous. Le fonctionnement local observé et les contrôles d’export sont documentés séparément dans les résultats.

## Périmètre et méthode

L’audit porte sur la dernière version du répertoire local `commerceops_ai` et ses personnalisations Medusa appliquées. L’état initial comprend des changements indexés, des modifications supplémentaires et des nouveaux fichiers. Le code applicatif, les tests, les configurations et les documents existants ont été conservés. Les empreintes initiales figurent dans `INITIAL_STATE.json`. Les opérations Git exécutées ont servi à l’inventaire.

Les seuls nouveaux fichiers de travail concernent les preuves d’audit, les helpers éphémères sous `data/runtime`, les fixtures de test et l’archive. Les helpers exercent les points d’entrée existants. Les scénarios sensibles de panne et de changement de catalogue sont reproduits avec des objets de transport simulés. Les échanges réels utilisent les deux comptes de démonstration locaux.

La comparaison finale des 90 fichiers protégés retrouve leurs empreintes initiales. HEAD et l’index Git sont identiques à leur état initial. Le statut Git Medusa est également conservé. Les résultats figurent dans `FINAL_STATE.json`.

## Résultats des vérifications

| Vérification | Résultat réel | Preuve |
|---|---|---|
| Tests locaux sur Python 3.14 | PASS, 116 tests | `pytest-local.log`, `pytest-local.xml` |
| Ruff au profil CI | PASS, code de sortie 0 | `ruff-ci.log`, `local-checks.json` |
| Quality gate historique | PASS | `quality-historical.log` |
| Quality gate RAG de développement | PASS | `quality-development.log` |
| Installation propre Python 3.12 | Installation et cohérence des dépendances réussies | `clean-install.log`, `clean-pip-check.log`, `clean-run.json` |
| Tests sur source propre | FAIL, 111 réussis et 5 échecs | `pytest-clean.log`, `pytest-clean.xml` |
| Dépendances locales cohérentes | PASS selon pip check | `pip-check-local.log`, `pip-list-local.log` |
| Avis de sécurité des dépendances | 15 enregistrements, 9 avis distincts sur 2 paquets | `dependency-summary.json`, `dependency-vulnerabilities.json`, `sca-run.json` |
| Dépendances JavaScript Medusa et storefront | pnpm audit retourne 32 alertes, dont 3 critiques, 14 élevées, 11 modérées et 4 faibles. Lockfile conservé | `medusa-dependency-audit.json`, `medusa-dependency-summary.json` |
| Services API, Streamlit, Medusa, MLflow | HTTP 200 pour les quatre services existants | `runtime-and-docker.json` |
| Configuration Compose | Validation réussie, secrets interpolés sans affichage | `runtime-and-docker.json` |
| PostgreSQL et Redis | Ports liés à 127.0.0.1, respectivement 5433 et 6380 | `runtime-and-docker.json` |
| Persistance MLflow | Trace récupérée, spans retrieval et search_knowledge présents, contrôle des en-têtes confidentiels passé | `mlflow.json` |
| Écritures autorisées réelles | Un panier de démonstration explicitement confirmé et relu | `live-functional.json` |
| Commandes pendant cet audit | Listes des deux comptes de démonstration identiques avant et après | `live-functional.json` |
| Remboursements | Aucune opération demandée par le harnais | `live-functional.json` |
| Contrôle de secrets du source et de l’historique local | Aucun motif ou credential local correspondant détecté dans le périmètre scanné | `security-initial.json`, `source-hygiene.log` |
| Export source | PASS, 437 entrées relues, CRC valides, zéro fuite détectée par les contrôles, octets vérifiés | `EXPORT_GATE.json`, `ARCHIVE_VERIFICATION.json` |

Les gates comparent des rapports et baselines déjà présents. Leur réussite est un contrôle de cohérence de ces résultats. Les tests fonctionnels et la reproduction propre apportent les vérifications supplémentaires du code courant.

## Parcours fonctionnels réels

Le harnais exécute le véritable script Streamlit via AppTest et ses requêtes HTTP vers l’API existante. Le compte est authentifié dans Medusa. Les assertions structurelles contrôlent l’interface.

| Parcours | Résultat |
|---|---|
| Produit demandé puis recherche catalogue | Sweatshirt M retrouvé, stock explicitement non vérifié |
| Réponse « oui » | Approbation créée, bouton désactivé en attente de la case explicite |
| Annulation | Approbation locale passée à cancelled |
| Confirmation suivante | Panier créé et lignes relues, variante et quantité vérifiées |
| Consultation « mon panier » | Outil get_cart observé et contenu métier affiché |
| Deuxième confirmation | Refus HTTP 409 |
| Panier d’un autre client | Session refusée HTTP 404, connecteur propriétaire refusé |
| Commande de la fixture d’un autre client | Connecteur propriétaire refusé |
| Lecture sans authentification | Refus HTTP 401 |
| Résumé en trois étapes | Trois étapes numérotées avec étiquette conditionnelle et modes ABCD |
| Réponse courte et détaillée | Deux formats distincts observés |
| Absence de politique applicable | Abstention, puis suivi indiquant l’absence de procédure précédente |
| Nouvelle conversation | Lien de panier actif effacé, lecture suivante HTTP 404 |
| Présentation client | Zéro élément JSON en mode client dans le harnais |

Les preuves sont regroupées dans `live-functional.json`. L’audit n’a pas produit de contrôle visuel dans un navigateur. Les tests automatisés existants couvrent les timeouts, erreurs HTTP, concurrence de session, reset pendant confirmation et outils en erreur. Les pannes serveur destructives ont été laissées hors exécution réelle.

## Qualité RAG et formulation

Cinq diagnostics publics ont été exécutés avec recherche directe puis réponse de chat. Les sources attendues de développement sont retrouvées pour les quatre cas positifs et le cas négatif s’abstient. Les candidats, scores et nombres de chunks sont consignés dans `rag-quality.json`. Les annotations ont été examinées par l’agent auditeur.

| Sujet | Examen du contenu |
|---|---|
| Erreur de couleur | Achat et niveau d’adhésion, étiquette après acceptation, modes exclusivement attribués à ABCD. L’éligibilité locale reste inconnue. |
| Article manquant | La référence retrouvée décrit surtout un article non reçu et un colis indiqué livré trop tôt. La réponse conserve cette limite et n’ajoute ni photos obligatoires ni remboursement partiel. |
| Identifiant oublié | Le scénario fabrique un identifiant de simulation. La réponse l’indique et conserve les limites de récupération réelle. |
| Carte refusée | Réessai, reconnexion et validité de carte sont appuyés. La collecte bancaire est signalée comme incompatible avec le chat. Aucun moyen de paiement supplémentaire n’est promis. |
| Politique absente | Aucune garantie commerciale inventée. |

Les extraits utilisés sont vérifiés dans les chunks effectivement récupérés. L’examen du sens porte aussi sur les conditions et la portée des affirmations. L’acceptation conditionnelle du retour est conservée et les modes du scénario restent attribués à ABCD. La précaution sur les coordonnées relève de l’application. Le catalogue de faits et la composition française sont contrôlés par le backend, tandis que NVIDIA sélectionne des faits autorisés.

Les liens de source sont encodés et le fichier éditeur a répondu HTTP 200. Le fragment de sous-flux identifie la provenance au sein d’un JSON brut. Son utilisation visuelle comme navigation vers le passage reste à évaluer.

Un des diagnostics a utilisé `verified_fact_fallback`. Son motif exact n’est pas exposé par le code courant. Les autres appels observés prouvent une sélection NVIDIA réelle. Les résultats restent des diagnostics de développement connus. La fidélité sémantique humaine et l’évaluation indépendante demeurent en attente.

## Bugs et incohérences confirmés

| Référence | Gravité | Constat et reproduction | Conséquence |
|---|---|---|---|
| AUD-01 | P1 | Cinq tests dépendent directement de `data/index.json`, absent d’une copie propre. Les tests concernés sont `test_inflected_colour_and_empty_cart_text` et les quatre instances de `test_diagnostic_sources_development_not_holdout` dans `tests/test_global_v2.py`. La CI installe les dépendances puis lance pytest sans construire cet index. | La version locale dépasse les conditions de reproductibilité de la recette CI actuelle. |
| AUD-02 | P1 | Une approbation affiche la variante M. Le catalogue conserve le même ID mais le libellé devient L avant la confirmation. L’API renvoie done et le transport métier simulé reçoit la variante désormais L. La confirmation dans `app/api.py` utilise les arguments persistés sans relecture des détails du catalogue. | L’action exécutée peut diverger du récapitulatif approuvé. Reproduction sur fixture uniquement dans `confirmed-findings.json`. |
| AUD-03 | P1 | ChromaDB 1.5.9 et pip 25.3 correspondent aux avis signalés par pip-audit, soit neuf avis distincts après déduplication. Le lockfile JavaScript produit également 32 alertes dont trois critiques. | Un traitement des versions et de l’applicabilité est nécessaire avant le feu vert sécurité. |
| AUD-04 | P1 | Le PDF universitaire actuel compte dix pages et contient encore 42 tests et 205 passages. Il décrit une version antérieure aux 116 tests et 217 passages actuels. | Le livrable de présentation doit être synchronisé après l’audit. Extraction textuelle dans `pdf-text-audit.json`. |
| AUD-05 | P1 | Des fichiers courants, notamment `app/documentary_format.py`, sont non indexés et plusieurs fichiers ont une version indexée différente de leur version de travail. | Un commit limité à l’index actuel ne représenterait pas l’application auditée. L’archive est construite depuis les fichiers de travail. |
| AUD-06 | P2 | La création de panier et l’ajout de ligne sont deux POST successifs. Une erreur sur la ligne survient après création du panier, sans appel de compensation ni retour du panier partiel au client. | Un panier vide peut rester dans Medusa. La fixture HTTP reproduit la séquence et la remontée d’erreur dans `confirmed-findings.json`. |
| AUD-07 | P2 | Le sélecteur documentaire renvoie un mode de repli mais masque la catégorie d’échec qui l’a déclenché. | Le diagnostic d’une panne fournisseur ou d’une sortie invalide demande une instrumentation supplémentaire. |
| AUD-08 | P2 | Les notes de portée et de sécurité restent longues dans la version courte. Certaines phrases génériques de type « Elle prévoit » persistent dans les autres sous-flux. | La formulation française et la brièveté peuvent encore être améliorées. |

Les contrôles de source et d’historique n’ont pas confirmé de fuite de secret dans le périmètre inspecté. Les défauts P1 fonctionnels et de reproductibilité suffisent au verdict NO-GO.

L’avis Chroma critique vise notamment une API serveur. CommerceOps utilise ici le lecteur lexical et des clients Chroma persistants embarqués dans ses chemins d’indexation. L’exploitabilité du déploiement courant demande donc une analyse d’applicabilité. L’audit n’a exécuté aucun exploit. Les avis consultés et les versions concernées sont fournis par les bases de sécurité. [Avis Chroma CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) [Avis pip CVE-2026-1703](https://github.com/advisories/GHSA-6vgw-5pg2-w6jp)

Le scan pnpm couvre les 1 677 dépendances du monorepo, y compris son storefront optionnel. Ses trois alertes critiques concernent proxy-addr et deux avis Next.js. Les avis Next.js décrivent des préconditions sur l’optimisation d’images SVG et les fonctions `use cache`. L’audit conserve les versions et chemins de dépendances, avec une analyse d’applicabilité en attente. Le storefront Next.js est distinct de l’interface Streamlit exercée ici. [Avis proxy-addr](https://github.com/advisories/GHSA-jqcg-44mw-7w3h) [Avis Next.js images](https://github.com/advisories/GHSA-2464-fhr4-w9xw) [Avis Next.js cache](https://github.com/advisories/GHSA-673q-mjm6-r5xr)

## Sécurité et clé NVIDIA

Le source, les documents et l’historique Git local ont été confrontés aux formats de clés, JWT et clés privées ainsi qu’aux valeurs confidentielles locales connues. Les valeurs sont restées en mémoire du scanner et n’ont pas été écrites dans les preuves. La présence d’une clé active est confirmée par les appels NVIDIA réussis.

La configuration observée utilise `nvidia/nemotron-3.5-lightning-30b-a3b` sur l’endpoint NVIDIA et le backend RAG lexical. Ces champs non sensibles sont consignés dans `runtime-and-docker.json`.

La révocation de l’ancienne clé repose sur la confirmation explicite de l’utilisateur dans cette conversation, « ancienne clé révoquée, nouvelle clé installée ». Le contrôle auprès du portail émetteur reste une vérification indépendante non réalisée. L’audit n’a ni récupéré ni affiché l’ancienne valeur.

L’authentification Medusa, les contrôles de propriété et les transitions d’approbation ont été relus et exercés. Les variantes de JWT absent ou refusé, sessions étrangères et double approbation sont couvertes par les tests et le parcours réel. La détection de données sensibles dans le chat demeure heuristique. Les sessions et références persistées dans les bases sont exclues de l’export.

## Reproductibilité et éléments en attente

L’image Python 3.12 officielle existante a servi à créer un conteneur éphémère. Les seules sources courantes ont été montées en lecture seule. L’installation a utilisé `requirements-dev.txt` sans `.env`, corpus, index, `.git`, `.venv` ou dépendances du poste. Le test propre a reproduit cinq échecs d’index manquant. Les 111 autres tests ont réussi.

Le Compose actuel est valide et ses deux ports de données sont liés à la boucle locale. PostgreSQL et Redis sont démarrés. Le bus et le verrouillage Medusa restent configurés en mémoire dans cette démonstration, conformément aux limites déjà décrites dans la documentation.

Les opérations suivantes restent hors validation de cet audit.

- Revue humaine des 16 scénarios gelés et mesure indépendante, avec protocole et formulaire préparés dans ce dossier.
- Contrôle visuel manuel du navigateur et relecture visuelle du PDF.
- Reconstruction complète de Medusa et de son storefront optionnel dans un second environnement vierge.
- Redémarrage coordonné de tous les services du poste. Les services préexistants ont été contrôlés en fonctionnement.
- Nouvelle mesure réelle des backends dense et hybride et du reranking optionnel. Les diagnostics actuels portent sur le backend lexical configuré.
- Charge, déploiement public et analyse exhaustive d’exploitabilité des avis de dépendances.
- Nouveaux checkout, commandes, retours autorisés et remboursements, conformément au périmètre demandé.

Le jeu final n’a pas été utilisé pour ajuster le système. Son formulaire conserve `approved=false`. Les cas de diagnostic utilisés ici proviennent des demandes publiques de développement.

## Commandes et résultats conservés

Les arguments complets des commandes locales figurent dans `local-checks.json`. Les commandes de conteneurs figurent dans `clean-run.json` et `sca-run.json`. Les paramètres de volume y identifient les sources de travail et les dossiers de preuves.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short --basetemp <dossier-temporaire-unique> -o cache_dir=data/runtime/prepush-cache --junitxml=reports/pre-push/pytest-local.xml
.\.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.\.venv\Scripts\python.exe -m scripts.quality_gate
.\.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
.\.venv\Scripts\python.exe -m scripts.check_secrets
.\.venv\Scripts\python.exe -m pip check
docker compose --env-file .env.docker -f compose.commerceops.yml config --quiet
```

Le conteneur propre a installé les dépendances puis exécuté la suite de tests. Le conteneur d’analyse de dépendances a interrogé les avis à partir des métadonnées installées montées en lecture seule. Les helpers éphémères d’audit ont exercé les parcours réels et les deux reproductions de bugs sans altérer le code du projet.

La commande `pnpm.cmd audit --json` a été exécutée à la racine de `my-medusa-store`. Son code de sortie est 1 et l’empreinte du lockfile est identique avant et après. Les harnais ayant produit les résultats locaux, propres, métier et RAG sont conservés dans l’archive sous `reports/pre-push/harnesses`. Leur relance exige de préparer les services et fixtures de démonstration décrits par le projet. Le harnais métier effectue un ajout au panier explicitement confirmé sur les comptes de démonstration.

## Archive source

Le fichier demandé est `CommerceOps_AI_AUDIT_SOURCE.zip`, à la racine de `commerceops_ai`. Il réunit les fichiers de travail actuels de CommerceOps, les sources Medusa locales et configurations autorisées, les tests, documents et preuves d’audit utiles. Les exemples d’évaluation conservés sont des fixtures synthétiques annotées et leur revue reste en attente.

Les exclusions couvrent `.env`, credentials et jetons, clés privées, identifiants métier réels, données clients, bases, `.git`, `node_modules`, `.venv`, corpus et datasets bruts, caches, sorties de build et anciens logs d’exécution. Les identifiants de démonstration et chemins du poste présents dans les copies de documents ou preuves exportées sont expurgés. Les octets des fichiers applicatifs exportés sont conservés. Le PDF antérieur est exclu de l’archive source, avec son état textuel consigné dans cet audit.

L’export est bloqué si les motifs de secret ou les valeurs confidentielles connues apparaissent dans un candidat. Le contrôle relit ensuite chaque entrée ZIP, vérifie ses octets, les chemins, les empreintes et les CRC. Le manifeste et la preuve finale se trouvent dans `ARCHIVE_MANIFEST.json` et `ARCHIVE_VERIFICATION.json`.

L’archive vérifiée comporte 437 entrées, dont le manifeste. Le scan de tous les membres a retrouvé zéro motif de secret et zéro valeur confidentielle connue. Les chemins interdits sont absents. La preuve finale externe conserve l’empreinte SHA256 de l’archive et sa taille. Les limites du scanner demeurent celles des motifs et valeurs connues décrits ci-dessus.

## Décision

Le projet démontre les parcours locaux documentés, avec 116 tests locaux réussis et des opérations Medusa réellement observées sur les fixtures de démonstration. Les cinq échecs propres, la divergence possible de variante à la confirmation et les points de livraison P1 demandent un traitement avant validation de publication et de présentation à jour. Les sources sont livrées comme état d’audit avec ce verdict NO-GO.
