# Audit V4 — Corrections conversationnelles après V3

Vérification du 12 novembre 2026 sur la version locale de CommerceOps AI. Les trois bugs de la mission jointe sont reproduits avant correction, corrigés puis rejoués avec Streamlit AppTest, FastAPI et Medusa réels.

**BUG-01, BUG-02 et BUG-03 sont validés sur les scénarios exécutés.** La suite compte **163 tests réussis localement et 163 réussites dans Python 3.12 propre**. Ruff au profil CI, les deux quality gates, le contrôle de secrets et pip check passent. Les limites de publication de l’audit V3 restent ouvertes et le verdict global demeure **NO-GO pour la publication**.

## Tableau des corrections

| Bug | Cause racine | Correction appliquée | Test de validation | Résultat |
|---|---|---|---|---|
| BUG-01 | Le routage documentaire reconnaissait le mot « garantie », mais excluait « garantit » et « officiellement ». La demande empruntait la génération générale NVIDIA et pouvait recevoir une présentation du modèle. | Les formes de garantie, les références officielles et contractuelles imposent la recherche documentaire avant toute génération générale. Une source absente ou inapplicable déclenche l’abstention existante. | Question exacte réelle, variantes de formulation, référence ABCD insuffisante, fournisseur hors sujet ou indisponible. | PASS. Recherche observée et abstention française. |
| BUG-02 | `re.search` retenait la première taille. La quantité reconnaissait les chiffres, puis conservait 1 lorsque le nombre était écrit « deux ». | Dernière mention explicite de taille et de quantité, nombres français, suivi des corrections, catalogue relu et anciennes approbations invalidées. Une variante absente demande clarification. | Message composé M puis L, trois puis deux, « non, plutôt L », nombres écrits et chiffrés, quantités hors plage, taille absente et ancienne approbation. | PASS. Sélection L quantité 2 et panier réel correspondant après confirmation. |
| BUG-03 | Le backend traitait seulement une liste de refus courts. Une phrase naturelle passait au LLM, qui pouvait annoncer une annulation sans modifier l’approbation. L’ancienne notification de réussite persistait dans Streamlit. | Annulation naturelle avant le LLM, vérifications client/session, transition persistante conditionnelle, réponse selon l’état réel et effacement du succès ancien au nouvel échange. | Annulation en attente, refus inter-clients, reset, confirmation annulée, opération déjà créée et annulation concurrente à une confirmation. | PASS. État cancelled et refus HTTP 409. Le panier déjà créé demeure consultable. |

## Réponses réelles avant et après

Les réponses intégrales et leur ordre figurent dans `conversation-final/before.json` et `conversation-final/after.json`. Le scénario avant ne crée aucun panier et annule son approbation de démonstration après avoir constaté son état.

### BUG-01

Question exécutée — « Votre boutique garantit-elle officiellement tous les appareils électroniques pendant 36 mois ? »

Avant — « Non, je suis un modèle de langage développé par des chercheurs de NVIDIA. » Les outils observés sont vides.

Après — « Je ne dispose pas d'une source pertinente et applicable permettant de confirmer cette procédure ou cette politique de boutique. Je préfère ne pas inventer de conditions. Vous pouvez préciser la référence recherchée ou demander l'aide d'un conseiller. »

La réponse après utilise `search_knowledge` et le mode `documentary_abstention`. Une référence ABCD ne confirme pas une garantie officielle de la boutique. Les tests n’acceptent aucune affirmation de garantie de 36 mois.

### BUG-02

Question exécutée — « Je veux deux sweatshirts taille M. Finalement, je préfère la taille L. »

Avant — « Variante trouvée au catalogue : Medusa Sweatshirt, M, quantité 1. Stock réel non vérifié. Voulez-vous préparer une demande de panier ? Un « oui » créera seulement une approbation à confirmer séparément. »

Après — « Variante trouvée au catalogue : Medusa Sweatshirt, L, quantité 2. Stock réel non vérifié. Voulez-vous préparer une demande de panier ? Un « oui » créera seulement une approbation à confirmer séparément. »

Le parcours poursuit les modifications de taille et de quantité. L’acceptation crée une nouvelle approbation. La case explicite puis le bouton Confirmer déclenchent la création. La lecture Medusa retrouve le produit Medusa Sweatshirt, la variante L et la quantité 2. La disponibilité du stock demeure non vérifiée par la recherche catalogue.

### BUG-03

Question exécutée sur une approbation en attente — « Je ne veux plus ajouter cet article. Annule la préparation du panier. »

Avant — « Annulation demandée. Aucune action n'a été effectuée sur le panier. » L’approbation est pourtant toujours `pending`. Cette reproduction met en évidence une réponse trompeuse sur l’état de préparation.

Après — « La préparation de votre panier est annulée. L'approbation annulée ne peut plus être confirmée. » La lecture persistante confirme `cancelled` et une tentative de confirmation renvoie HTTP 409.

Après création effective, « Annule ma dernière demande » reçoit — « Le panier déjà confirmé reste associé à cette conversation. Cette demande n'a pas modifié son contenu. Vous pouvez le consulter. Les préparations encore en attente sont annulées. » Le panier est ensuite relu avec succès. Une annulation arrivée après revendication de l’approbation signale une opération en cours et conserve les références permettant sa consultation.

## Commandes exécutées et preuves

| Vérification | Résultat réel | Preuve dans `conversation-final/` |
|---|---|---|
| Pytest local sur Python 3.14 | 163 passed, 34,46 s | `pytest.log`, `pytest.xml`, `pytest-command.json` |
| Pytest propre sur Python 3.12 | 163 passed | `pytest-clean.log`, `pytest-clean.xml`, `clean-run.json` |
| Ruff CI local et propre | PASS | `ruff.log`, `ruff-clean.log` |
| Gates historique et développement, local et propre | PASS | `gate-historical.log`, `gate-development.log` et variantes `-clean.log` |
| Hygiène de sources et pip check, local et propre | PASS | `secrets.log`, `secrets-clean.log`, `pip-check.log`, `clean-pip-check.log` |
| Patch deepmerge installé | Un test réussi | `deepmerge-patch.log` |
| Parcours réel avant/après | PASS après correction | `before.json`, `after.json`, `live-after-command.json` |
| RAG positif et source manquante | Diagnostics publics exécutés, extraits et sources conservés | `rag-quality.json`, `rag-mlflow.log` |
| MLflow | Trace persistée relue, spans retrieval et search_knowledge présents | `mlflow.json` |
| Protections V3 et jeu gelé | 18 empreintes identiques, HEAD et index Git identiques | `protected-before.json`, `protected-after.json` |
| Rapport universitaire | PDF actualisé de 10 pages, rendus inspectés par l’agent | `pdf-validation.json`, `pdf/` |

Les commandes principales sont les suivantes. La reproduction avant est une preuve historique enregistrée avant les modifications.

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_conversation_final before
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short --basetemp <répertoire-temporaire-unique> -o cache_dir=data/runtime/conversation-cache --junitxml=reports/pre-push/conversation-final/pytest.xml
.\.venv\Scripts\python.exe -m scripts.verify_conversation_final after
.\.venv\Scripts\python.exe -m scripts.verify_conversation_final clean
.\.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.\.venv\Scripts\python.exe -m scripts.quality_gate
.\.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
.\.venv\Scripts\python.exe -m scripts.check_secrets
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.export_final_report
```

Le test deepmerge emploie `node --test test/deepmerge-patch.test.cjs` depuis le backend Medusa. Les arguments exacts et codes de sortie des vérifications locales figurent dans `checks.json`.

Le conteneur propre monte une copie de sources en lecture seule et installe le lock Linux Python 3.12 préservé. Les clés, bases et index personnels sont absents. Les fixtures construisent leur index temporaire. Git est installé uniquement dans ce conteneur et le modèle public `.env.example` fait partie de la copie. Ces deux éléments permettent au scanner existant de fonctionner. Les premiers essais avaient confirmé les tests, puis révélé ces prérequis manquants dans le harnais. Le dernier code de sortie complet vaut 0.

Les quality gates contrôlent les résultats archivés et leurs seuils existants. Les dialogues et tests de régression constituent les preuves courantes. Les scénarios proviennent de la mission et de variantes de développement. Le jeu final gelé n’est pas exécuté pour cette correction.

## Fichiers modifiés par cette correction

- `app/agent.py` étend le routage documentaire des demandes commerciales.
- `app/conversations.py` résout les préférences et l’annulation à partir de l’état propriétaire persistant.
- `app/ui.py` efface l’ancienne notification de réussite au nouvel échange.
- `tests/test_conversations.py` ajoute 25 cas exécutés aux 138 tests de V3.
- `scripts/verify_conversation_final.py` fournit la reproduction réelle avant/après et la reproduction propre.
- `scripts/verify_pre_push_v2.py` complète le harnais propre avec Git, l’exemple public de configuration et la vérification du répertoire temporaire.
- `docs/IMPLEMENTATION_STATUS.md`, `docs/RAPPORT_TECHNIQUE.md` et l’export PDF enregistrent les résultats actuels. Le script d’export identifie l’édition V4 et conserve ses rendus dans les preuves courantes.

Les contrôles par empreinte portent sur les modules de confirmation, catalogue, stockage, connecteur Medusa, synthèse et retrieval, les fichiers de dépendances, le patch deepmerge, les middlewares de propriété et les deux fichiers gelés. Le test du chemin SendGrid patched passe également. Les preuves ne contiennent pas de JWT, de mot de passe ou de clé fournisseur.

## Périmètre et limites restantes

Le parcours après correction effectue une création de panier sur les seules fixtures de démonstration autorisées. La liste de commandes du compte est identique avant et après. Aucun endpoint de commande ou remboursement n’est appelé. Les écritures potentiellement incertaines continuent de relever du runbook V3 et de la confirmation explicite existante.

La reconnaissance des préférences est déterministe et bornée aux tailles prises en charge et aux quantités autorisées. Les formulations ambiguës et les langues non couvertes restent à évaluer. Les tests d’interface sont des assertions AppTest avec des échanges HTTP réels. L’inspection visuelle du navigateur et la validation linguistique humaine restent en attente. Les dix pages du PDF ont été examinées par l’agent sur leurs rendus, sans revendication de revue humaine indépendante.

Les cinq avis résiduels recensés en V3, la revue indépendante et la réconciliation de l’index Git avant publication restent ouverts. Cette campagne préserve les dépendances et ne relance pas une évaluation de vulnérabilités exhaustive. L’ancienne clé NVIDIA reste révoquée selon l’attestation utilisateur déjà consignée en V3. Aucun contrôle auprès du portail émetteur n’est revendiqué.

**Verdict global NO-GO pour la publication.** Les trois bugs conversationnels sont corrigés et vérifiés dans le périmètre décrit. Les points de publication identifiés en V3 sont conservés dans le bilan.
