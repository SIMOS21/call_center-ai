# Mémoire conversationnelle — 12 novembre 2026

La cause du redémarrage apparent était l'absence de contexte backend : Streamlit affichait les anciens messages, mais `/chat` recevait uniquement la dernière phrase. « Oui » arrivait donc sans produit ni intention. Aucun remplacement de l'architecture ou du client Medusa n'a été nécessaire.

## Contrat et sécurité

- Premier `POST /chat` authentifié : le backend vérifie le client Medusa, crée un identifiant aléatoire `sess_` avec 32 octets d'aléa et renvoie `session_id`. Les tours suivants transmettent ce seul identifiant avec le JWT dans l'en-tête Authorization. L'UI ne fournit jamais l'historique comme autorité.
- Chaque lecture, tour et reset vérifie l'identité auprès de Medusa puis filtre par `session_id` **et** `customer_id`. Une session étrangère renvoie 404 ; token absent 401, authentification refusée 403. Deux sessions du même client conservent des sélections distinctes. L'UI efface son contexte quand le token change.
- SQLite conserve l'état du produit, sa variante, taille/couleur, quantité, intention, proposition et approbations en attente. Les identifiants métier viennent du catalogue, jamais d'une déduction de texte libre. Une demande de nouveau produit inconnu invalide l'ancien choix. Une variante ambiguë impose une clarification.
- L'historique durable contient au maximum 40 messages canoniques, construits à partir de champs autorisés. Le modèle reçoit les 20 derniers, plus le contexte actuel. Les textes bruts utilisateur, réponses complètes et corps d'outils ne sont pas archivés dans cette mémoire. Les coordonnées, JWT et secrets ne font pas partie de l'état autorisé ; seuls les identifiants/statuts des résultats métier sont repris. La saisie sensible détectée est refusée avant appel au fournisseur et masquée dans l'historique d'affichage Streamlit.
- Un bail SQLite et une version sérialisent les échanges d'une session, sans transaction ouverte pendant les appels réseau. Un second échange ou reset concurrent renvoie 409. Un crash peut bloquer cette session pendant 15 minutes ; le bail expire ensuite. Le contrôle de version empêche un ancien tour d'écraser un tour plus récent.
- `GET /sessions/{id}` expose uniquement la mémoire autorisée à son propriétaire. `DELETE /sessions/{id}` efface cette mémoire et annule les approbations encore en attente. Il n'annule aucun panier, commande ou retour déjà exécuté.

## Préparation et exécution

1. « Medusa Sweatshirt taille M » consulte réellement le catalogue. Une variante trouvée n'est jamais présentée comme disponible : **stock non vérifié**.
2. « Oui » ou « celui-là » après ce choix revérifie produit/variante dans le catalogue puis appelle `prepare_cart` avec la variante et la quantité retenues. Cela crée une approbation locale, pas un panier Medusa.
3. L'interface relit les détails authentifiés par `GET /actions/{approval_id}` : identifiant, type, produit, variante, quantité et arguments exacts. La case d'accord est remise à zéro si ces détails changent. Le bouton reste désactivé tant qu'elle n'est pas cochée.
4. Seul `POST /actions/confirm` avec consentement explicite exécute. Une approbation issue du chat exige aussi sa session d'origine ; omettre ou changer cette session échoue. Les approbations historiques conservent leur contrat. Propriété client, validation des arguments et transition atomique à usage unique restent en place.
5. La réussite n'est affichée qu'après `status=done` et les références renvoyées par Medusa. Un appel en erreur ne devient jamais un succès ; l'approbation échouée ne se rejoue pas silencieusement. Une erreur d'enregistrement de mémoire après réussite métier ne transforme pas cette réussite en nouvel essai.

Un second « oui » montre l'approbation existante. Il n'exécute ni checkout, paiement, annulation ni retour. « Non », une autre taille ou un changement de produit annulent l'ancienne approbation en attente. Les contrôles et middlewares Medusa n'ont pas été modifiés.

## Réponses documentaires

La recherche obligatoire et l'abstention sans source sont conservées. Lorsque des passages existent, une étape sans outils produit une explication française fondée sur les extraits, suivie de références titre/URL et d'un court extrait. Les citations identiques sont dédupliquées. La réponse rappelle que les procédures ABCD ne sont pas les politiques officielles de Medusa ou de la boutique. Fournisseur indisponible : réponse prudente explicitant que les références ne suffisent pas à établir les droits du client. Aucune procédure documentaire n'autorise une opération métier.

Le résumé généré reste soumis aux erreurs possibles du modèle ; la présence de citations ne prouve pas sa fidélité sémantique. Aucun score de fidélité humaine ou d'amélioration indépendante n'est revendiqué. Le jeu final-v3 reste non exécuté, sans revue humaine attestée.

## Vérifications et reproduction

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=reports/conversations/pytest.xml
.\.venv\Scripts\python.exe -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82
.\.venv\Scripts\python.exe -m scripts.check_secrets
.\.venv\Scripts\python.exe -m scripts.quality_gate
.\.venv\Scripts\python.exe -m scripts.quality_gate --results reports/rag-v2/gate-results.json --baseline docs/rag-v2-quality-baseline.json
```

88 tests passent, dont les tests de sélection multi-tours, taille/couleur/quantité, nouveau produit connu/inconnu, isolation client/session, refus d'accès croisé, reset, concurrence, historique borné, données sensibles, variante supprimée ou modifiée, outil indisponible, erreur métier, double confirmation, explication française et repli documentaire. Le profil Ruff exécuté comme gate est celui de la CI existante. Le lint large sans ce profil a également été essayé : il relève des dettes de style/robustesse hors profil CI (imports, variables inutilisées, exceptions larges), non corrigées globalement afin de limiter le périmètre et de préserver les fichiers Medusa.

Avec les services locaux déjà démarrés et les comptes de démonstration locaux :

```powershell
# Crée un nouveau panier local après case + bouton ; jamais de commande.
.\.venv\Scripts\python.exe -m scripts.verify_conversation_live --execute-live --documentary
```

`--documentary` envoie uniquement la question et les extraits ABCD publics au fournisseur configuré ; ne pas l'activer avec des sources privées sans autorisation. Aucun secret n'est écrit dans le rapport. Le test utilise le vrai script Streamlit via son AppTest, les véritables endpoints FastAPI et la boutique Medusa existante, sans mocks. Il vérifie la variante M, le panier appartenant au client, le refus 409 du second clic, le refus 404 d'un autre client, l'absence de nouvelle commande, puis le reset. Ce harnais ne remplace pas un contrôle visuel dans un navigateur. Rapport : `reports/conversations/live-streamlit-medusa.json`.

Les refus de retours Medusa ont été revérifiés : 401 sans token, 403 pour un autre client, 400 pour `receive_now`, éligibilité d'un retour déjà demandé refusée, retour historique toujours persisté et aucun remboursement. Le script de contrôle consulte également l'Admin local pour cette seule vérification ; ces droits ne sont jamais exposés à l'agent.

## Limites

La mémoire libre et exhaustive d'une conversation n'est volontairement pas persistée : seules les informations canoniques utiles au commerce sont conservées. Cela limite les rappels portant sur un détail libre sans champ prévu. Les exemples « oui », « non », « celui-là », taille et changements de produit ont des transitions explicites ; toutes les formulations possibles ne sont pas couvertes. Les identifiants de session ne remplacent jamais l'authentification. La détection de saisies sensibles est heuristique, pas une garantie de détection de toute donnée personnelle ; les messages bruts ne sont pas archivés côté backend. Le JWT reste dans la session d'interface pour authentifier les requêtes, jamais dans l'historique transmis au modèle. La base SQLite locale doit être protégée par les droits de la machine. Pas de purge automatique des sessions anciennes dans ce prototype. La disponibilité du stock ne fait toujours l'objet d'aucune promesse.

Le dernier contrôle de secrets a détecté et retiré une valeur active de `LLM_API_KEY` dans `.env.example` ; la configuration ignorée `.env` n'a pas été modifiée. Le contrôle a ensuite passé. La valeur n'est pas présente dans HEAD ni dans l'historique local de ce fichier, vérifiés sans afficher le secret ; cette vérification ne couvre pas d'éventuelles copies externes. Voir les rapports `example-sanitization.json` et `secret-history-check.json`.
