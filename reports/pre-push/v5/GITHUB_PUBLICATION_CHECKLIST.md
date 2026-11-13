# Checklist de publication GitHub

Les deux dépôts sont préparés séparément. Les fichiers `commerceops_ai-include.txt` et `my-medusa-store-include.txt` constituent les listes explicites proposées. Leurs inventaires JSON comparent les versions de travail et les objets indexés par Git. Cette recette conserve les index et HEAD existants.

## Avant l’accord de publication

- [ ] Révoquer la clé NVIDIA exposée dans le contexte IDE, installer une nouvelle clé localement et confirmer la rotation sans publier sa valeur.
- [x] Valider le parcours NVIDIA existant avec les références publiques autorisées. Six sélections de faits et deux abstentions réussissent, modèle configuré et modes de génération consignés dans `nvidia-documentary-scenarios.json`.
- [ ] Vérifier de nouveau le fournisseur après la rotation et le rechargement effectifs de la nouvelle clé.
- [ ] Examiner les listes explicites des deux dépôts et les différences avec leurs index actuels.
- [ ] Retirer de la sélection publique les fichiers du jeu final privé et les éléments exclus, y compris ceux déjà présents dans l’index historique.
- [ ] Vérifier à nouveau les secrets sur les octets qui seront réellement indexés, puis sur l’historique destiné à être publié.
- [ ] Conserver les manifests, lockfiles, correctifs Medusa, tests et documents nécessaires. Le patch deepmerge et sa déclaration pnpm doivent être livrés ensemble.
- [ ] Consigner la décision concernant les cinq avis résiduels et le profil d’environnement retenu. Les scanners doivent continuer à signaler les versions concernées.
- [x] Préparer la revue humaine indépendante à l’aide de `HUMAN_REVIEW_16.md` et de sa fiche CSV. Son statut reste PENDING avant revue effective.
- [ ] Faire le contrôle visuel humain du navigateur si cette validation est requise pour la soutenance. Les assertions AppTest sont déjà identifiées dans les preuves.
- [ ] Donner un accord explicite pour le commit, le push et l’exécution distante de la CI sur les dépôts et branches choisis.

## Préparation locale après sélection approuvée

Employer les chemins explicites et relire `git diff --cached --stat` ainsi que les contenus indexés. Les listes produites incluent également des fichiers de base déjà suivis. La revue doit porter sur l’ensemble du futur commit, en tenant compte des fichiers historiques déjà indexés.

Exclure `.env`, credentials, clés, jetons, bases, environnements virtuels, `node_modules`, caches, archives, rendus temporaires, corpus et données clients. Les dossiers de preuves brutes ne sont pas sélectionnés automatiquement. Les journaux et XML restent disponibles localement pour l’audit. Les questions finales privées restent hors des listes publiques proposées.

Les références commerciales opaques dans `docs/DEMO_2MIN.md` et `reports/evaluation.json` demandent une revue avant sélection définitive. Le scanner les signale séparément des secrets. Conserver les preuves originales localement si une version publique expurgée est préparée.

## Reproduction de la livraison

Pour CommerceOps, installer le lock Linux Python 3.12 dans un environnement neuf et exécuter les tests sur `tests`, le profil Ruff CI, les quality gates et les contrôles de sources. Générer les secrets et les credentials de démonstration dans des fichiers locaux ignorés. Les fixtures documentaires des tests construisent automatiquement leur index.

Pour Medusa, utiliser pnpm 10.11.1 et le lockfile livré. Conserver `patches/deepmerge@4.3.1.patch`, la déclaration `patchedDependencies` de `package.json` et `apps/backend/test/deepmerge-patch.test.cjs`. Le test du patch et le lint backend doivent réussir. Les migrations et les données de démonstration sont à préparer selon le README existant dans un environnement dédié.

Le miroir `integrations/medusa/dependencies/` a été synchronisé avec ces fichiers pour la reproduction à partir des documents CommerceOps. La recette V5 a corrigé l’absence de déclaration du patch dans son manifeste racine et ajouté le patch et son test au miroir.

Les résultats de cette recette sont locaux. Un clone réellement publié et une exécution GitHub Actions sur son commit restent à vérifier après autorisation et publication.
