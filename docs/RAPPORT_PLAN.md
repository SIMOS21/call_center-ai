# Plan de rapport technique 8–12 pages — ne pas inventer les résultats

**Titre :** CommerceOps AI — Industrialisation d'un agent d'assistance e-commerce avec RAG, outils métier et observabilité MLOps.

1. **Contexte et problématique** (1 page). Centre de support e-commerce, documentation disparate, besoin de décisions cohérentes et d'actions autorisées.
2. **Exigences et périmètre** (1 page). Trois sources réelles distinctes; portée de Medusa, outils, exclusions et critères de succès.
3. **Architecture** (1–1,5 page). Schéma de `README.md`, séparation documentaire/transactif, sécurité du LLM.
4. **Ingestion et reproductibilité** (1–1,5 page). URL, licences et droits, métadonnées, nettoyage, chunking, embedding, version manifest.
5. **Orchestration agentique** (1–1,5 page). Outils et entrées/sorties/erreurs/permissions; les étapes d'une transaction; validation Pydantic.
6. **Tests, CI et quality gates** (1 page). Unitaire, intégration Medusa, scénario erreur et hors périmètre, CI pass/fail; justifier seuils.
7. **Expérimentations et évaluation** (1–1,5 page). TF-IDF baseline vs dense, Recall@5, fidélité/citations, sélection et échec d'outils, latence et nombre appels.
8. **Monitoring et gouvernance** (1 page). MLflow, audit, absence de chaîne de pensée, secrets, accès minimaux, supervision des remboursements.
9. **Démonstration, limites et perspectives** (0,5–1 page). Captures réelles avec sources; limites d'eBay/ABCD/Olist; Medusa auth; amélioration future.

Insert ONLY actual measured results in tables and figures. When results are not yet measured, mark **Non évalué**, never invent percentages.
