# Audit final V3 — CommerceOps AI

Date de vérification : 12 novembre 2026  
Périmètre : workspace CommerceOps AI et dépôt Medusa séparé `my-medusa-store`. Aucun commit ni push.

## Verdict

**NO-GO pour publier.** Les tests, quality gates, contrôles d’hygiène et vérifications PDF passent. Il reste quatre avis Chroma non corrigés, un avis faible `deepmerge` toujours remonté par npm malgré une mitigation locale, une procédure opérateur nécessaire pour les écritures Medusa incertaines, une revue humaine indépendante non réalisée et un index Git qui ne représente pas encore le contenu vérifié.

Aucun paiement, commande, remboursement ou appel d’écriture métier n’a été déclenché. Le jeu final gelé n’a pas été modifié pendant cette vérification.

## Résultats effectivement vérifiés

| Vérification | Résultat |
|---|---|
| Tests Python locaux, Python 3.14 | **138 passed** (`pytest tests -q`) |
| Environnement propre Python 3.12 | **138 passed**; `pip check`, profil Ruff CI et quality gates réussis dans la vérification propre précédente |
| Ruff, profil CI `E4,E7,E9,F63,F7,F82` | **PASS** local et dans le conteneur propre |
| Ruff sans profil CI | **55 diagnostics** existants/hors profil : 41 I001, 6 F401, 3 F841, 4 S110, 1 B023 |
| Quality gate historique et gate de développement | **PASS** tous les deux, relancés localement |
| Hygiène des sources/secrets et `pip check` | **PASS** localement |
| Audit pip Windows | Quatre avis Chroma distincts sur `chromadb==1.5.9` |
| Audit pip du lock Linux Python 3.12 | Aucun avis connu dans le lock audité |
| `pnpm install --frozen-lockfile`, test de patch et lint Medusa | **PASS**; le test de non-régression deepmerge passe (1/1) |
| Audit npm | **Un avis faible `deepmerge@4.3.1` demeure**; il n’est ni ignoré ni masqué |
| `git diff --check` | **PASS** dans les deux dépôts; Git affiche seulement ses avertissements usuels de conversion LF/CRLF |

Un lancement initial de `pytest` à la racine a inclus des copies archivées du projet et échoué sur des modules de test homonymes. La commande correspondant au périmètre du projet (`pytest tests`) a ensuite réussi, avec les 138 tests.

Le wrapper de validation Python 3.12 propre a un code de sortie final **1** : tests, `pip check`, Ruff et les deux quality gates avaient réussi, puis `scripts.check_secrets` a échoué parce que l’image ne contient pas `git`, requis par ce scanner. Le contrôle de secrets est donc confirmé **localement seulement**, et non dans le conteneur propre.

### Dépendances et applicabilité

Les sept avis historiques sont tracés ci-dessous. Les statuts « non corrigé » restent visibles dans les audits.

| Avis | Sévérité | Version / chemin | Applicabilité au déploiement vérifié | État |
|---|---|---|---|---|
| GHSA-f4j7-r4q5-qw2c / CVE-2026-45829 | Critique | `chromadb==1.5.9`, lock Windows | Exige le serveur HTTP Chroma vulnérable et `trust_remote_code=true`. L’application utilise le backend lexical; aucun serveur Chroma n’est démarré. Le chemin dense emploie `PersistentClient` local. | **Non corrigé**; aucun correctif PyPI identifié lors de la vérification. Interdire l’exposition d’un serveur Chroma. |
| GHSA-36p7-vc44-83pf / CVE-2026-45833 | Critique | `chromadb==1.5.9`, lock Windows | Exige une actualisation de collection via serveur, `trust_remote_code=true` et la permission `UPDATE_COLLECTION`; ces surfaces ne sont pas activées. | **Non corrigé**; préconditions absentes du déploiement vérifié. |
| GHSA-xph7-9rjv-w5fr / CVE-2026-45831 | Élevée | `chromadb==1.5.9`, lock Windows | Défaut de portée de `SimpleRBACAuthorizationProvider`; aucun serveur Chroma ni fournisseur SimpleRBAC configuré. | **Non corrigé**; aucun chemin RBAC actif. |
| GHSA-2wm9-hf6c-p5cr / CVE-2026-45830 | Élevée | `chromadb==1.5.9`, lock Windows | Lecture/écriture inter-tenant via l’API authentifiée Chroma; cette API n’est pas exposée par le client local. | **Non corrigé**; aucune surface multi-tenant active. |
| GHSA-w5hq-g745-h8pq / CVE-2026-41907 | Modérée | `uuid@11.1.1` | La résolution réellement installée et l’appel `v4()` de BullMQ ont été vérifiés après installation gelée. | **Résolu** par l’override existant. |
| GHSA-g3hv-75wg-m249 / CVE-2026-118764 | Modérée | `minimatch@11.0.1` | Override ciblé; matching, lint et build vérifiés. | **Résolu** par l’override existant. |
| GHSA-gcqx-w48m-w2h4 / CVE-2026-93753 | Faible | `deepmerge@4.3.1` | Le graphe comprend Jest → `jest-config` → `deepmerge` et le graphe Medusa → `@medusajs/notification-sendgrid` → `@sendgrid/mail` → `@sendgrid/helpers` → `deepmerge`. SendGrid n’est pas configuré dans `medusa-config.ts`, mais le paquet est présent dans le graphe de production. | **Toujours signalé**; aucune version upstream corrigée identifiée. Le patch pnpm local rejette `__proto__` dans les entrées CommonJS/UMD et le test vérifie la résolution du chemin SendGrid. Cette mitigation ne retire pas l’avis npm. |

`body-parser@1.20.9` demeure corrigé séparément, sans être compté parmi les sept avis historiques. `trust_remote_code=False` concerne SentenceTransformers et n’est pas présenté comme une protection Chroma.

Mesures de réduction pour Chroma : conserver le moteur lexical courant, ne pas lancer ni exposer le serveur Chroma, ne pas activer SimpleRBAC/API multi-tenant, et réauditer avant tout changement d’architecture ou dès publication d’une version corrigée. Le lock Linux Python 3.12 ne contient pas Chroma.

### Écritures Medusa

La photographie commerciale approuvée, les vérifications de propriété et la confirmation explicite unique sont conservées. Les réponses incertaines ne déclenchent pas de retry automatique ni de compensation. Un panier partiel connu reste consultable; `needs_review` impose la procédure de [MEDUSA_UNCERTAIN_WRITES.md](../../docs/MEDUSA_UNCERTAIN_WRITES.md) : rapprochement en lecture seule côté boutique, puis nouvelle confirmation explicite du client avant toute autre action. Cela réduit le risque, sans promettre l’atomicité entre appels Medusa. Aucun nouvel appel réel de création/écriture n’a été effectué pendant cette vérification.

## Anomalies AUD-01 à AUD-08

| Anomalie | Statut V3 | Preuve / limite |
|---|---|---|
| AUD-01 — tests dépendants de l’index local | **Résolue** | Les fixtures construisent leur index de test; les 138 tests passent localement et les 138 tests passent dans l’environnement propre Python 3.12. |
| AUD-02 — variante exécutée différente de la variante approuvée | **Résolue** | Relecture de la variante et de la photographie commerciale avant écriture; les tests couvrent les divergences et l’invalidation de l’approbation. |
| AUD-03 — avis de dépendances | **Partiellement résolue — bloque le GO** | UUID et minimatch corrigés. Quatre avis Chroma et l’avis faible deepmerge restent détectés. |
| AUD-04 — PDF non synchronisé | **Résolue pour cette édition** | PDF régénéré après mise à jour des résultats; 10 pages et texte extractible; figures, tableau, références et planches vérifiés visuellement. La revue humaine universitaire indépendante reste en attente. |
| AUD-05 — index Git incomplet | **Inventaire réalisé, commit non prêt** | CommerceOps : 287 entrées de statut, dont 88 chemins indexés, 24 avec changements hors index et 190 non suivis après ajout du présent rapport. Medusa : 13 entrées, dont 7 chemins modifiés hors index et 6 non suivis. |
| AUD-06 — panier partiel après échec d’ajout de ligne | **Atténuée, non résolue** | Aucune répétition automatique; rapprochement opérateur en lecture seule documenté. Un panier incomplet peut subsister et requiert une décision opérateur/client. |
| AUD-07 — motif de repli RAG non diagnostiqué | **Résolue au niveau des catégories** | Les erreurs fournisseur, timeout, HTTP, indisponibilité, payload et identifiants de faits non autorisés ont des catégories distinctes; le contenu brut n’est pas consigné. |
| AUD-08 — réponses brèves/génériques | **Partiellement résolue** | Formats courts/détaillés et formulations plus concrètes. Aucune validation linguistique humaine indépendante n’a été réalisée. |

### Rapport PDF

Le rapport [CommerceOps_AI_Rapport_Final.pdf](../../output/pdf/CommerceOps_AI_Rapport_Final.pdf) contient **10 pages** et **19 430 caractères extraits**; les dix pages ont du texte. Les figures, le tableau des validations, les références et les cinq planches de pages ont été inspectés. SHA-256 : `9c318933eb8c6e4b3306d111a4a426eb2295cd579cb13ec4eb8d3cb4d79d35a9`. Les rendus et métadonnées de validation sont conservés sous `reports/pre-push/v3/`; ils ne sont pas tous destinés au commit.

Le PDF distingue les résultats techniques de développement d’une évaluation indépendante. La revue des 16 cas gelés et de la fidélité des réponses reste à faire; aucun résultat indépendant n’est revendiqué.

## Liste exacte proposée pour un futur commit

Cette liste est une sélection explicite du contenu de livraison, à préparer en deux dépôts séparés. Elle n’a pas été ajoutée à l’index par cette mission.

### Dépôt CommerceOps

```text
.env.example
.gitattributes
.github/workflows/ci.yml
.gitignore
README.md
app/agent.py
app/api.py
app/catalog.py
app/conversations.py
app/documentary.py
app/documentary_format.py
app/knowledge_index.py
app/medusa.py
app/presentation.py
app/rag.py
app/storage.py
app/ui.py
docs/CONVERSATION_MEMORY.md
docs/IMPLEMENTATION_STATUS.md
docs/MEDUSA_UNCERTAIN_WRITES.md
docs/RAG_AND_CART_FIXES.md
docs/RAG_UPDATES.md
docs/RAG_SYNTHESIS_FORMATS.md
docs/RAPPORT_TECHNIQUE.md
docs/REPRODUCIBILITY.md
docs/rag-v2-quality-baseline.json
integrations/medusa/README.md
integrations/medusa/dependencies/backend.package.json
integrations/medusa/dependencies/package.json
integrations/medusa/dependencies/patches/deepmerge@4.3.1.patch
integrations/medusa/dependencies/pnpm-lock.yaml
integrations/medusa/dependencies/storefront.package.json
integrations/medusa/dependencies/tests/deepmerge-patch.test.cjs
output/pdf/CommerceOps_AI_Rapport_Final.pdf
reports/pre-push/FINAL_AUDIT_V3.md
reports/pre-push/v3/pdf-validation.json
requirements-dev.txt
requirements-linux-py312.lock.txt
requirements-windows-py314.lock.txt
requirements.txt
scripts/build_index.py
scripts/diagnose_v2.py
scripts/evaluate_answers_v2.py
scripts/evaluate_global_v2.py
scripts/evaluate_retrieval_v2.py
scripts/export_final_report.py
scripts/freeze_final_v3.py
scripts/manifest.py
scripts/verify_conversation_live.py
scripts/verify_global_v2_live.py
scripts/verify_pre_push_v2.py
scripts/verify_rag_formats.py
tests/conftest.py
tests/fixtures/ABCD_LICENSE.txt
tests/fixtures/knowledge/abcd-excerpts.json
tests/test_audit_actions.py
tests/test_conversations.py
tests/test_documentary_answers.py
tests/test_global_v2.py
tests/test_rag_synthesis.py
tests/test_rag_updates.py
tests/test_safety.py
```

### Dépôt Medusa distinct (`my-medusa-store`)

```text
.gitignore
apps/backend/.gitignore
apps/backend/package.json
apps/backend/src/api/commerceops-ownership.ts
apps/backend/src/api/middlewares.ts
apps/backend/src/scripts/configure-agent.ts
apps/backend/src/scripts/prepare-return-demo.ts
apps/backend/test/deepmerge-patch.test.cjs
apps/storefront/package.json
compose.commerceops.yml
package.json
patches/deepmerge@4.3.1.patch
pnpm-lock.yaml
```

### Exclusions impératives

- Ne pas inclure `evaluation/final-v3.jsonl` ni `evaluation/final-v3.review.json`; leurs empreintes SHA-256 restent respectivement `6B0E29CED596FE2458FF1EBDC1D2CF76F2816D479CADCF28FF1C924403AEBCED` et `5BE3A97FE2C48D8C18A9D7B162043227BB571E7181CDC6A53CFAC72164EAC438`. Ces fichiers étaient déjà indexés et n’ont pas été modifiés par cette mission.
- Exclure `.env`, secrets, bases privées, caches, environnements virtuels, journaux/XML, captures PNG, archives ZIP, rendus temporaires et répertoires `node_modules`.
- La liste ci-dessus n’inclut pas les changements historiques d’audit ni les fichiers d’évidence V2. Ne pas utiliser `git add .` : l’index CommerceOps contient déjà d’autres éléments, dont le jeu final gelé exclu.

## Actions restantes avant un GO

1. Obtenir une version corrigée de Chroma ou retirer cette dépendance de l’environnement concerné, puis refaire l’audit; ne pas exposer Chroma HTTP/RBAC avant cela.
2. Remplacer le patch local deepmerge par une version upstream corrigée dès qu’elle existe, puis confirmer que l’audit npm ne signale plus l’avis.
3. Faire réaliser et documenter la revue humaine indépendante des réponses et des 16 cas gelés.
4. Appliquer le runbook opérateur aux éventuels paniers `needs_review`; l’atomicité interservices n’est pas garantie.
5. Réconcilier explicitement l’index avec la liste proposée dans chacun des deux dépôts et exclure le jeu gelé; aucun commit/push ne doit précéder ces décisions.

**Verdict final : NO-GO.** Les vérifications techniques confirmées sont vertes, mais les avis de dépendances toujours actifs, les limites opérationnelles et l’absence de revue indépendante empêchent encore une publication sans réserve.
