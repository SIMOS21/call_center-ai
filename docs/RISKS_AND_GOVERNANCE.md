# Risk register and operational policy

| Risk | Mitigation implemented/proposed | How to test |
|---|---|---|
| Hallucinated answers | Tool search and explicit citations; missing documents -> no confident claim | Questions outside corpus, contradicting policies |
| Third-party eBay rules mistaken for store policy | System prompt labels sources as external; policy validation remains in backend/admin | Ask agent to apply eBay guaranteed refund to unrelated Medusa order |
| Prompt injection in fetched HTML | Document content treated as untrusted data; never execute text or tool instructions from RAG | Include 'ignore instructions' text in a test fixture |
| Cross-customer access | Medusa customer JWT + explicit customer ID equality check | Unit test uses customer A requesting B's order |
| Duplicate purchase/return | One-time approval token; idempotency via state transitions and no silent retry | Reconfirm same approval twice |
| Unauthorized refunds | No direct financial refund tool; Medusa Admin handles payment/refund approval | Ask to transfer/refund money directly |
| Missing or invalid tool arguments | Pydantic schemas, finite loop count, HTTP timeouts | Invalid quantity, bad order ID |
| Sensitive data in traces | Audit stores tool names/timings/status only; no prompts, full args or JWTs | Inspect audit table and git status |
| Misleading datasets | Separate real historic Olist from active Medusa orders; ABCD research dialogues from production | Inspect DB table names, source labels |
| Changes in external websites | Provenance URL/date/hash, robots respect, source inventory | Repeat harvest on a new date, compare hashes |
| Retrieval failures | Baseline vs semantic index; human-reviewed gold set, recall@k | Evaluate annotated queries |
| Service outage | Catch network errors, expose nonready health, ticket escalation | Kill Medusa/LLM service; inspect response |

## Permissions

Public RAG and public product lookup: no customer token. Owned orders, cart creation, returns and tickets: authenticated Medusa customer token; customer identity is taken from Medusa, never LLM arguments. Payment/refund: merchant staff with Medusa Admin role (not exposed to customer agent). Sensitive operations require explicit customer consent and sometimes human manager approval. No permissions to customer banking data or third-party eBay user accounts.

## Mise à jour après exécution locale — 11 novembre 2026

Implémenté et testé : propriété des commandes et paniers, identité issue du JWT, validation Pydantic stricte sans champs supplémentaires, plafond total de huit outils et cinq itérations, arrêt dès une demande de confirmation, approbation SQLite atomique et unique (test concurrent), erreurs réseau/HTTP/JSON expurgées, absence de faux succès après erreur d’outil, gate refusant contrôles vides et nombres non finis. Le middleware Medusa exige l’authentification et la propriété pour les retours, refuse receive_now et ferme les retours sans activation marchande. Le checkout direct vérifie aussi la propriété. Les réponses réelles ont prouvé 401/403 pour les retours étrangers et 403 pour checkout étranger.

Une recherche RAG ne confère plus de droit de retour. Le moteur local garde les retours fermés par défaut et vérifie, si activé, état expédié et quantités appartenant à la commande. Cette règle est une règle explicite de la boutique de démonstration ; elle ne vient ni d’eBay ni d’ABCD. Le parcours de retour autorisé reste à valider, y compris les compteurs de quantités de la version installée. Ne pas l’activer pour la soutenance sans test réel supplémentaire.

Les traces ne capturent pas les prompts, arguments, réponses complètes, adresses ou JWT : choix volontaire de confidentialité, au prix d’une analyse de fidélité impossible depuis les seules traces. Les interactions SQLite stockent nombres d’appels/itérations, durée, modèle, confirmation et escalade. Les audits contiennent outil, catégorie, succès, durée et classe d’erreur. Pas de chaîne de pensée. Les coûts/tokens ne sont pas encore mesurés. Le masquage et le routage hors périmètre par LLM restent à éprouver avec NVIDIA ; les mocks ne prouvent pas la résistance générale aux injections.

Limites : absence de TTL des approbations, de quotas par client, de politique de rétention et de verrou distribué multi-instance. Un crash après confirmation peut laisser un état confirmed ; aucune relance automatique pour éviter un achat dupliqué. Bus et verrouillage Medusa en mémoire ; déploiement local mono-instance exclusivement. Le contrôle de secrets simple n’est pas un scanner exhaustif. Les snapshots de benchmark vérifiés en CI ne remplacent pas une nouvelle évaluation des sources téléchargées. Les annotations agent doivent être revues humainement et le jeu étendu avant de tirer des conclusions statistiques.

eBay : NON TENTÉ, autorisation et droits non fournis. Olist : NON IMPORTÉ. Chroma : NON INSTALLÉ. Déploiement public, remboursement monétaire, push Git et CI distante : NON RÉALISÉS. Les identifiants de démonstration sont générés localement et ignorés par Git ; les IDs techniques publics de test sont les seules références transactionnelles dans les rapports.



La transmission ? NVIDIA des seules sources publiques et donn?es de test expurg?es a ?t? explicitement autoris?e dans la session. Une cl? plac?e dans .env.example a ?t? d?plac?e et nettoy?e avant commit ; elle est apparue dans une sortie technique, donc sa rotation reste n?cessaire. Aucun commit/push contenant cette cl?. Le scanner contr?le d?sormais aussi le mod?le .env.example et les rapports.
