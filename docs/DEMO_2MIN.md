# Démonstration de deux minutes — parcours réellement exécuté

État : parcours vertical local fonctionnel avec NVIDIA Nemotron 3.5 Lightning. Aucune vidéo enregistrée. Les captures ci-dessous restent à réaliser ; les rapports JSON et runs MLflow proviennent d’exécutions réelles.

- **00:00–00:15** : ouvrir http://127.0.0.1:8501 et http://127.0.0.1:8001/health. Les quatre indicateurs de santé/configuration sont positifs. Dans la barre latérale, ouvrir « Comptes de démonstration locale » et connecter Client A ; aucun JWT à copier dans la conversation.
- **00:15–00:35** : demander au chat « Recherche les consignes ABCD pour un retour dû à une mauvaise couleur et cite la source ». Montrer le titre/URL et rappeler qu’ABCD n’est pas la politique contractuelle de la boutique.
- **00:35–00:55** : demander le catalogue réel puis le statut de la commande de démonstration. Les outils search_products et get_order_status ont déjà été exécutés par NVIDIA. Les variantes du catalogue ne prouvent pas un stock disponible.
- **00:55–01:15** : montrer la demande prepare_cart et son ID d’approbation ; confirmer explicitement avec le bouton UI. La création de panier est réelle. Le checkout complet existant est documenté dans reports/agent-live.json ; la livraison et le paiement système de test ont été configurés par API locale avant request_checkout et sa confirmation.
- **01:15–01:35** : montrer dans Medusa Admin la commande order_01M76FXF3CQBMTZ81FGHD5N638 et son retour return_01M76G6DA7M4AJZ0J9YBNEA44Z. Le retour a été créé séparément via l’outil et confirmation API après fulfillment manuel de test. Aucun remboursement financier, aucune réception automatique. Ne pas demander un second retour sur le même article.
- **01:35–01:50** : montrer reports/agent-negative.json et return-smoke.json : commande étrangère refusée, remboursements financiers autonomes refusés, accès direct au retour 401/403, receive_now 400 et répétition de confirmation 409. Un ticket a été persisté sur la commande.
- **01:50–02:00** : montrer MLflow et la sortie des 42 tests. Résultats guidés : 6/6 outils attendus, un appel moyen, latence moyenne 4 285 ms ; Recall@5 lexical 8/12 et dense 6/12, annotations par agent non revues humainement. Annoncer cette limite.

## Captures et actions restantes
- [ ] Capturer santé, recherche et réponse NVIDIA sans clé/JWT.
- [ ] Capturer catalogue, commande et retour Admin sans identifiants privés.
- [ ] Capturer les runs MLflow, métriques et traces imbriquées.
- [ ] Enregistrer une vraie vidéo de deux minutes.
- [ ] Faire revoir les annotations et mettre en page le rapport technique.

Ne pas remplacer une capture réelle par une image générée. Les scripts de démonstration créent des données persistantes ; ne les relancer que volontairement sur la boutique locale. La clé NVIDIA doit être remplacée après son exposition dans une sortie technique, puis l’API relancée.
