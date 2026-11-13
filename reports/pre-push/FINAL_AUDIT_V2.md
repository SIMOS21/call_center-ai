# Audit final V2 — CommerceOps AI

Date : 12 novembre 2026. Vérifications exécutées sur l'état courant du workspace.

## Verdict

**NO-GO pour une publication ou une présentation sans réserve.** Les tests locaux et Python 3.12 propres passent, les corrections AUD-01 et AUD-02 sont confirmées et les dépendances JavaScript ont été réinstallées depuis le lock gelé. Restent toutefois quatre avis Chroma non corrigés (dans une dépendance MLOps optionnelle), un avis npm faible sans correctif publié, des écrits Medusa dont l'issue peut rester incertaine, et un décompte de sécurité périmé dans le PDF. Le périmètre du futur commit est aussi encore réparti entre index, worktree et fichiers non suivis.

Aucun commit, push, paiement, commande, remboursement ou écriture métier n'a été exécuté pendant cette vérification. Le jeu final gelé n'a pas été modifié.

## Résultats vérifiés

| Vérification | Résultat observé |
|---|---|
| Workspace CommerceOps | Python 3.14.3 ; suite complète : **138 passed** |
| Installation propre Python | Docker `python:3.12-slim`, Python 3.12.16 ; installation depuis `requirements-linux-py312.lock.txt`, `pip check` propre et **138 passed** |
| Ruff CI | PASS local et dans l'installation propre (Ruff sans cache dans la copie montée en lecture seule) |
| Quality gates | Gates historiques et RAG de développement : PASS local et propre |
| Secrets / cohérence Python | `scripts.check_secrets` : PASS local ; `pip check` : PASS local et propre |
| Dépendances Medusa | Node 24.13.0 / pnpm 10.11.1 ; `pnpm install --frozen-lockfile` : PASS, lock inchangé |
| Compatibilité JS ciblée | Résolution effective BullMQ → `uuid@11.1.1`, appel `v4()` valide ; `minimatch@11.0.1` accepte le motif de test |
| Medusa backend | `pnpm run lint` : PASS, aucun problème |
| Storefront | Build Next.js 16.4.1 : PASS avec la clé publishable locale fournie au processus sans afficher sa valeur |
| Audit npm du lock actif | Une vulnérabilité faible : `deepmerge@4.3.1`, avis GHSA-GCQX-W48M-W2H4 ; code de sortie 1 dû à cet avis |
| PDF | 10 pages, texte extrait sur les 10, 17 582 caractères ; 138 tests et 217 passages présents ; aucune anomalie de mise en page évidente sur les cinq planches inspectées |
| `git diff --check` | PASS pour changements indexés et non indexés des deux dépôts |

La suite propre a émis un avertissement de dépréciation : l'usage de `httpx` avec `starlette.testclient` est déprécié par la version Starlette installée. Les tests restent verts. La première commande de build du storefront, sans configuration, a échoué proprement faute de `NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY`; le build de validation a ensuite réussi avec la valeur déjà présente dans la configuration locale, sans l'imprimer. Next.js signale aussi la convention `middleware` dépréciée au profit de `proxy`.

Le contrôle des secrets a été exécuté dans le workspace courant. Il n'a pas été lancé dans le conteneur propre : cette image ne contient pas `git`, requis par `scripts.check_secrets`. Son absence dans le conteneur ne constitue pas un résultat PASS.

## AUD-01 à AUD-08

| Anomalie | État V2 | Preuve et constat |
|---|---|---|
| **AUD-01 — tests dépendants de l'index local** | **Résolue** | `tests/conftest.py` construit maintenant un index documentaire temporaire depuis `tests/fixtures/knowledge`. Les 138 tests passent dans une copie propre sans `data/index.json`, sur Python 3.12.16. Preuves antérieures : `v2/pytest-clean.xml` et `v2/clean-run.json`. |
| **AUD-02 — variante exécutée différente de la variante approuvée** | **Résolue** | Avant l'écriture, [app/api.py](../../app/api.py) relit le produit et la variante puis compare leur photographie commerciale approuvée. Les tests [test_audit_actions.py](../../tests/test_audit_actions.py) couvrent taille, disparition, produit, prix, devise, options, SKU et prix manquant ; chaque dérive donne 409, invalide l'approbation et ne déclenche aucune écriture. |
| **AUD-03 — avis de dépendances** | **Partiellement résolue — bloque le GO** | Deux des sept avis de l'ancien état sont corrigés (UUID et minimatch). Le lock JS courant et le lock Python confirment cinq avis toujours présents : quatre Chroma et un deepmerge. `body-parser` 1.20.9 est également corrigé, mais ne faisait pas partie de ces sept avis restants. Les quatre Chroma ne correspondent pas aux chemins réseau/RBAC déployés, mais la dépendance 1.5.9 demeure dans l'environnement optionnel MLOps et aucun correctif PyPI n'est publié. |
| **AUD-04 — PDF non synchronisé** | **Partiellement résolue — bloque une présentation à jour** | Le PDF courant est bien la version V2 de 10 pages et mentionne 138 tests / 217 passages. Le texte et les planches sont lisibles, sans débordement constaté. Cependant, sa page 7 affirme encore « 7 avis restants / 33 résolus » et trois avis JavaScript ; l'état vérifié est maintenant **5 restants / 35 résolus**, dont un seul avis npm. La revue visuelle est effectuée, mais la section de sécurité doit être régénérée après décision sur le risque résiduel. |
| **AUD-05 — index Git incomplet par rapport au worktree** | **Ouverte — commit non prêt** | Avant l'ajout du présent rapport, le dépôt CommerceOps avait 266 entrées de statut : 88 déjà indexées, 24 avec changements supplémentaires hors index et 169 fichiers non suivis. Le rapport V2 ajoute un fichier non suivi. Les changements Medusa sont dans un second dépôt : 7 fichiers suivis modifiés et 4 non suivis, aucun indexé. Un commit de l'index seul ne représente donc pas les sources vérifiées. |
| **AUD-06 — panier partiel après échec d'ajout de ligne** | **Atténuée, non résolue** | [app/medusa.py](../../app/medusa.py) tente une lecture propriétaire de réconciliation après une réponse perdue ; [app/api.py](../../app/api.py) marque ensuite l'approbation `needs_review`, expose l'incertitude et interdit une seconde écriture. Les tests couvrent panier partiel et réponse perdue. Ils ne compensent ni ne suppriment un panier incomplet : son existence reste à vérifier côté boutique. |
| **AUD-07 — motif de repli RAG non diagnostiqué** | **Résolue au niveau des catégories** | [app/documentary.py](../../app/documentary.py) distingue fournisseur absent, timeout, HTTP, indisponibilité, payload invalide et identifiants de faits non vérifiés ; la catégorie est transmise à l'audit sans consigner le contenu brut du fournisseur. |
| **AUD-08 — brièveté et formulations génériques** | **Partiellement résolue** | [app/documentary_format.py](../../app/documentary_format.py) dispose de rendus courts/détaillés et de formulations concrètes ; le texte source du code ne contient plus « Elle prévoit ». Les notes obligatoires de portée, citation et sécurité sont conservées même dans le rendu court. La qualité linguistique n'a pas reçu de validation humaine indépendante. |

## Analyse des sept avis cités dans le bilan précédent

Les sept avis encore ouverts lors du bilan du PDF étaient quatre avis Chroma, UUID, minimatch et deepmerge. UUID et minimatch ont depuis été corrigés. Le fichier [v2/dependency-matrix.json](./v2/dependency-matrix.json) compte désormais 35 avis résolus sur 40. L'audit frais du lock pnpm actif trouve un seul avis npm ; le rapport Python courant identifie quatre avis Chroma sur `chromadb==1.5.9`. Les anciens avis pip sur `pip==25.3` ne sont plus présents après passage à `pip==26.3`.

| Avis | Sévérité | Applicabilité actuelle | Statut |
|---|---|---|---|
| [GHSA-f4j7-r4q5-qw2c / CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) | Critique | L'exécution de code pré-authentification exige l'API HTTP Chroma vulnérable et `trust_remote_code=true`. CommerceOps utilise un client persistant local, ne lance pas ce serveur et impose `trust_remote_code=False`. Non atteignable par le chemin RAG lexical courant ; risque à réévaluer avant toute exposition d'un serveur Chroma. | **Non corrigé** : `chromadb==1.5.9`, aucun correctif PyPI annoncé. |
| [GHSA-36p7-vc44-83pf / CVE-2026-45833](https://github.com/advisories/GHSA-36p7-vc44-83pf) | Critique | L'attaque exige une requête d'actualisation de collection via serveur Chroma, `trust_remote_code=true` et la permission `UPDATE_COLLECTION`. Ces surfaces ne sont pas activées ici. | **Non corrigé**, mais préconditions absentes du déploiement vérifié. |
| [GHSA-xph7-9rjv-w5fr / CVE-2026-45831](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) | Élevée | Défaut de portée dans `SimpleRBACAuthorizationProvider` ; aucun serveur Chroma ni fournisseur SimpleRBAC n'est configuré. | **Non corrigé**, sans chemin RBAC actif. |
| [GHSA-2wm9-hf6c-p5cr / CVE-2026-45830](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) | Élevée | Lecture/écriture inter-tenant via l'API authentifiée Chroma ; le client local persistant n'expose pas cette API. | **Non corrigé**, sans surface multi-tenant active. |
| [GHSA-w5hq-g745-h8pq / CVE-2026-41907](https://github.com/advisories/GHSA-w5hq-g745-h8pq) | Modérée | La faille porte sur les fonctions UUID v3/v5/v6 lorsque leur buffer est fourni. Le lock force désormais `uuid@11.1.1`; après `pnpm install --frozen-lockfile`, la résolution réellement installée et l'appel `v4()` de BullMQ ont été vérifiés. | **Résolu**. Le `uuid@9.0.1` observé avant réinstallation provenait d'un `node_modules` obsolète. |
| [GHSA-g3hv-75wg-m249 / CVE-2026-118764](https://github.com/advisories/GHSA-g3hv-75wg-m249) | Modérée | Déni de service possible par amplification de motifs glob dans `minimatch` avec certaines options d'optimisation. `minimatch` est utilisé dans l'outillage de build ; l'override le force désormais à `11.0.1`, et le matching, le lint et le build ont été vérifiés. | **Résolu** par la mise à jour ciblée ; l'audit du lock courant ne le signale plus. |
| [GHSA-gcqx-w48m-w2h4 / CVE-2026-93753](https://github.com/advisories/GHSA-gcqx-w48m-w2h4) | Faible | `deepmerge@4.3.1` est transitif dans la chaîne Jest/configuration de test. L'avis requiert une entrée hostile transmise à `mergeObject`; aucun usage direct dans le backend métier n'a été établi. | **Toujours signalé**, pas de version corrigée publiée ; risque limité aux outils/tests, mais non supprimé du lock. |

Ainsi, la demande d'analyser sept avis est satisfaite en distinguant leur état historique de l'état courant : **deux résolus (UUID et minimatch), cinq encore signalés**. `body-parser` a aussi été corrigé, mais indépendamment de ces sept avis historiques. Une classification « non applicable » ne rend pas les quatre dépendances Chroma corrigées ; leur activation ou exposition réseau reste interdite jusqu'à une version corrigée et un nouvel audit.

## PDF et éléments du futur commit

- PDF contrôlé : [CommerceOps_AI_Rapport_Final.pdf](../../output/pdf/CommerceOps_AI_Rapport_Final.pdf), SHA-256 `37319b7454c522dec7d3ffff8206edc4161f85753965adace65335b83aaa74ba`. Dix pages textuellement extractibles ; métriques 138 / 217 à jour. La page 7 doit être mise à jour : son comptage de vulnérabilités ne reflète pas les correctifs UUID et minimatch. Le jeu final gelé reste distinct et inchangé.
- Dépôt CommerceOps : l'index est déjà partiellement préparé et 169 fichiers étaient non suivis avant ce rapport, notamment sources/tests/fixtures, quatre fichiers de dépendances Medusa, preuves historiques, rendus PNG du PDF et archive source. Les sources à inclure dans un futur commit doivent être sélectionnées explicitement : code `app/`, scripts et tests concernés, workflow, manifests/locks corrigés, documentation et rapport V2. Les logs, images d'aperçu et archive ZIP ne doivent pas être ajoutés en bloc sans décision de portée.
- Dépôt Medusa distinct : [my-medusa-store](../../../my-medusa-store) conserve ses modifications locales (`package.json`, `pnpm-lock.yaml`, middleware, `.gitignore`, trois helpers et Compose). L'installation gelée et les builds ont laissé son état Git inchangé. Ses changements devront être revus et committés séparément du dépôt CommerceOps.
- Aucun fichier n'a été ajouté à l'index par cette mission. Ne pas utiliser un `git add` global : contrôler `git status --short --untracked-files=all` dans les deux dépôts avant tout commit autorisé.

## Limites et actions bloquantes

1. Mettre à jour le contenu de sécurité du PDF et refaire l'extraction/inspection après approbation ; le PDF n'a pas été modifié pendant cet audit.
2. Garder Chroma désactivé et non exposé tant que les quatre avis restent sans correctif ; réexaminer dès publication d'une version non vulnérable.
3. Décider du traitement de `deepmerge` (suppression du chemin transitoire si possible, sinon acceptation documentée et surveillance d'un correctif).
4. Réconcilier explicitement l'index, les 24 changements hors index et les 170 fichiers non suivis après ajout du présent rapport ; traiter séparément le dépôt Medusa.
5. Fermer le risque opérationnel AUD-06 avec une procédure de rapprochement côté boutique ; aucune compensation destructive n'a été tentée.
6. Faire relire humainement la formulation et les 16 cas gelés selon le protocole existant avant de revendiquer une fidélité indépendante. Aucun résultat de cette revue n'est prétendu ici.

**Verdict final : NO-GO.** Les validations techniques demandées passent pour Python 3.14, Python 3.12 et les builds/lints JavaScript contrôlés, mais la sécurité résiduelle, l'écart de contenu du PDF et les points opérationnels/documentaires ci-dessus empêchent un GO.
