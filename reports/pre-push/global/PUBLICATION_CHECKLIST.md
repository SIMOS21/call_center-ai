# Checklist de publication globale

Recette locale du 13 novembre 2026. Aucun commit, push ou changement d'index Git n'est effectué par cette préparation. Les autorisations anciennes ne sont pas utilisées pour contourner la consigne actuelle de ne pas publier.

## Code et preuves

- [x] Préserver les corrections conversationnelles, la limite de quantité, l'authentification, les approbations uniques, les contrôles de propriété et l'interdiction des remboursements autonomes.
- [x] Exécuter les tests locaux et Python 3.12 propre, Ruff CI, deux gates, scanner de secrets et pip check.
- [x] Exécuter les tests du vrai middleware Medusa et du chemin deepmerge installé, puis le lint officiel.
- [x] Réaliser la recette AppTest/HTTP avec un panier client de démonstration multiligne, sa relecture et l'ajout d'un produit au même panier.
- [x] Contrôler refus étrangers, double confirmation, annulation persistante, reset et absence de nouvelle commande.
- [x] Lire les traces MLflow persistées et vérifier les valeurs sensibles selon les règles documentées.
- [x] Préserver les empreintes du jeu final et laisser la revue indépendante PENDING.
- [x] Mettre à jour les copies d'intégration Medusa, y compris le nouveau test de propriété et la commande `test:security`.
- [x] Ajouter pip check et le second quality gate à la CI Python préparée.

## Sélection explicite des deux dépôts

Les listes `commerceops_ai-include.txt` et `my-medusa-store-include.txt`, à côté de cette checklist, sont les candidats autorisés à la revue de publication. Les inventaires JSON homonymes donnent le SHA du fichier local et du contenu indexé, et indiquent les différences. `publication-summary.json` donne les nombres réellement vérifiés. Cette préparation n'exécute ni staging ni export public.

Pour CommerceOps, inclure notamment tous les modules `app/`, dont `documentary_format.py`, les nouveaux `interpreter.py` et `shopping.py`, les tests avec leurs fixtures documentaires autorisées, les scripts, les requirements/lockfiles, la CI, les configurations d'exemple non sensibles, les trois livrables globaux et les preuves publiques expurgées explicitement sélectionnées. Les gates ont besoin de `reports/evaluation.json`, `reports/rag-v2/gate-results.json` et de leurs baselines documentées.

Pour Medusa, conserver l'ensemble du starter et ses manifests/lockfile déjà locaux nécessaires, les middlewares de propriété réellement déployés, le patch pnpm deepmerge et les deux tests Node. Le script `test:security` modifié doit accompagner `apps/backend/test/cart-ownership.test.cjs`. Aucun fichier de `node_modules` ou de `.medusa` ne doit être ajouté.

- [ ] Revoir les fichiers dont le contenu local diffère du contenu indexé, selon les inventaires. Ne pas publier l'ancien index en supposant qu'il représente la version testée.
- [ ] Réconcilier les fichiers déjà indexés mais extérieurs à la sélection proposée, sans `git add .`. Le choix de les retirer d'un futur commit doit être explicite. Ils comprennent des rapports historiques et des évaluations privées, pas nécessairement des secrets.
- [ ] Revoir puis expurger les références métier réelles de démonstration signalées dans les inventaires, notamment les documents historiques. Une empreinte de cas ou un identifiant synthétique de fixture n'est pas un credential, mais les identifiants réels de session/commande ne sont pas requis pour une démonstration publique.
- [ ] Conserver les seize questions et annotations finales en accès privé, avec la fiche de revue et les empreintes. Ne pas les publier dans le dépôt public par staging aveugle.
- [ ] Recontrôler les deux listes après toute modification de code, document ou dépendance.
- [ ] Demander l'autorisation actuelle de commit/push seulement une fois le contenu final prêt à revoir. Aucune publication n'est incluse dans cette mission.
- [ ] Après autorisation et publication, vérifier la CI distante du SHA effectivement poussé. Les succès CI historiques ne valident pas ce futur SHA.

## Exclusions obligatoires

Exclure `.env` et variantes privées, `.env.admin`, `.env.docker`, credentials de démonstration, clés privées, jetons, mots de passe, données clients, bases SQLite/PostgreSQL, volumes, datasets bruts, index personnels, `.git`, `.venv`, `node_modules`, caches, builds, archives temporaires et journaux sensibles. `.env.example` reste autorisé après vérification. Les logs/JUnit bruts de cette recette restent consultables localement et ne sont pas inclus aveuglément dans les listes publiques.

Les contrôles d'inventaire recherchent les motifs de jetons/JWT/clés et les correspondances exactes des secrets locaux dans les candidats, l'index et l'historique. Ils affichent uniquement les chemins et les catégories. Un résultat positif bloque la sélection du fichier et la publication, sans afficher de valeur sensible. Le scanner ne prouve pas la détection universelle de tous les secrets.

## Interventions et validations encore requises

- [ ] Révoquer la dernière clé NVIDIA exposée dans le contexte IDE et installer une nouvelle clé uniquement dans `.env`. Confirmer l'opération sans divulguer la valeur. Les attestations de rotations antérieures ne couvrent pas cette exposition.
- [ ] Effectuer ensuite un contrôle fournisseur limité aux données publiques/de démonstration autorisées.
- [ ] Désigner un évaluateur indépendant pour les seize cas. Utiliser `../v5/HUMAN_REVIEW_16.md` et `../v5/HUMAN_REVIEW_16.csv`. Identité, date, indépendance et notes restent vierges tant que la revue n'est pas faite.
- [ ] Réaliser une inspection visuelle humaine de Streamlit et les captures/vidéo universitaires sans afficher de secret. AppTest n'est pas cette inspection.
- [ ] Décider de l'actualisation du PDF universitaire historique pour la version globale. Aucune validation du nouveau contenu ou de sa présentation n'est revendiquée ici.
- [ ] Revoir le risque des quatre avis Chroma et de l'avis deepmerge avant exposition publique. Ne pas activer un serveur Chroma distant sans réaudit. Le patch deepmerge est une réduction de risque testée, pas une version upstream corrigée.
- [ ] Qualifier l'installation intégrée sur une seconde machine, les permissions réseau et les procédures opérateur d'écriture incertaine avant exploitation réelle.

Verdict de publication **NO-GO** tant que ces critères bloquants ne sont pas traités ou explicitement arbitrés avec leurs limites. Le dossier contient des preuves techniques locales, sans validation humaine fabriquée.
