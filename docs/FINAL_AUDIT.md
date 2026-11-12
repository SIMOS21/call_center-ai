# Audit final — 12 novembre 2026

**Livraison globale : PARTIAL. Le fonctionnement local ne suffit pas à déclarer tous les P0 terminés.**

| Exigence | Statut | Preuve actuelle |
|---|---|---|
| P0.1 Rotation NVIDIA | COMPLETE, confirmation utilisateur | `reports/final-audit/rotation-safe-read.json` : ancienne clé révoquée/nouvelle installée attestées par utilisateur ; lecture sûre après redémarrage API réussie |
| Secrets et historique | COMPLETE dans le périmètre inspectable | `reports/final-audit/security.json` : fichiers, cellules de traces, historique Git et historique PowerShell inspectés sans valeur secrète affichée ; audit par motifs, non exhaustif |
| P0.2 Tests locaux Python 3.14 | COMPLETE | 42 tests ; `reports/final-audit/pytest.xml`, lint et gates dans ce dossier |
| Reproduction propre Python 3.12 | COMPLETE | `reports/final-audit/python312-clean.log` et `python312.lock.txt` : copie sans secrets, tests/lint/gates réussis dans Docker |
| Correctifs Medusa | PARTIAL | lint officiel réussi ; SHA starter figé ; copie des correctifs comparée aux fichiers appliqués ; pas de nouvelle boutique/base réinitialisée |
| Services locaux | COMPLETE | Redémarrage des conteneurs existants et quatre services ; état de lecture dans `reports/final-audit/readiness-restored.log` |
| P0.3 Jeu inédit | PARTIAL | 16 cas distincts gelés, copie `data/evaluation/manual_gold.jsonl`, SHA et brouillon mesuré dans `reports/final-audit/holdout-draft.json` |
| Revue humaine et fidélité | BLOCKED | `evaluation/manual_gold.review.json` non approuvé ; « vas-y » n'atteste pas une revue des annotations |
| Évaluation indépendante agent/tâche | BLOCKED | n=0 : aucune performance indépendante revendiquée ; transactions historiques non rejouées |
| P0.4 GitHub | IN_PROGRESS | Dépôt autorisé : https://github.com/SIMOS21/call_center-ai ; historique initial conservé, publication après scans |
| P0.5 Rapport PDF | COMPLETE pour pagination, PARTIAL pour captures | `output/pdf/CommerceOps_AI_Rapport_Final.pdf` : 10 pages, contrôle visuel ; architecture et tableau RAG inclus, captures Admin/CI absentes |
| Vidéo réelle 2 minutes | BLOCKED_MANUAL | Accès navigateur automatisé indisponible ; aucune vidéo ni capture synthétique fabriquée |
| P0.6 Terminologie/UTF-8 | COMPLETE pour le statut courant | Ancien statut archivé dans les preuves ; ce statut est réécrit en UTF-8 sans accents remplacés |

## Résultats correctement qualifiés

- Historique de développement : six scénarios guidés, six choix d'outils attendus, un appel moyen et 4 285 ms moyens. Les lignes prepare_cart/request_checkout indiquent pending, pas une tâche terminée. Les confirmations et la persistance sont prouvées séparément dans les scripts/rapports historiques.
- Développement RAG : lexical 8/12, dense 6/12. Nouveau brouillon distinct : cinq questions avec source, lexical 1/5 et dense 2/5. Aucune optimisation après ces résultats ; aucune validation humaine encore attestée. Le jeu n'est donc pas présenté comme un benchmark indépendant validé.
- Sélection d'outils, tâche complète, appels invalides/échoués, refus, escalades et fidélité du nouveau jeu : NOT_EVALUATED, n=0 tant que labels et fixtures ne sont pas revus. Les tests déterministes ne remplacent pas ces mesures.
- 55 documents ABCD, 205 passages ; 99 441 commandes Olist historiques séparées ; eBay non collecté. Demande de retour persistée ≠ remboursement financier. Paiement système de test ≠ transfert d'argent.

## Interventions restantes

1. Revoir individuellement les 16 annotations et leurs sources/extraits ; inscrire identité/date/SHA et corrections dans `evaluation/manual_gold.review.json` avant exécution indépendante supervisée. Les cas transactionnels exigent de nouvelles fixtures de test pour ne pas réutiliser un article déjà retourné.
2. Enregistrer une vraie vidéo de deux minutes et les captures Admin/MLflow/CI sans clés ni données privées. Le poste affichait un éditeur `.env` : aucune capture globale non contrôlée n'a été réalisée.
3. Publication et CI : autorisation explicite reçue ; voir le résultat final archivé avant de conclure à une CI distante réussie.

## Limites maintenues

Absence de TTL des approbations et de recovery après crash confirmed/done ; bus/verrous Medusa en mémoire ; usage local uniquement ; coûts/tokens non mesurés ; fidélité non validée ; aucune suppression de volumes, nouvelle commande ou remise à zéro exécutée pendant cet audit. Le PDF du professeur n'était pas présent : matrice fournie par l'audit utilisée, conformité au PDF original non certifiée.
