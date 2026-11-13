# Medusa local integration

## Renforcement global du 13 novembre 2026

Les copies `commerceops-ownership.ts` et `middlewares.ts` incluent désormais la propriété sur les lectures de paniers rattachés à un client et les ajouts, modifications et suppressions de lignes. Le propriétaire authentifié reste obligatoire pour ces paniers. Les paniers anonymes du storefront conservent leur parcours existant. Les finalisations et retours gardent leur authentification stricte et le refus de `receive_now`.

Copier aussi `dependencies/tests/cart-ownership.test.cjs` vers `apps/backend/test/cart-ownership.test.cjs`. Le manifeste backend synchronisé lance ce test et le test deepmerge avec `pnpm --filter @dtc/backend test:security`. Cinq tests ont été exécutés après ce changement. Les empreintes des middlewares ont donc changé intentionnellement depuis V5. Les données, volumes, migrations existantes et règles de remboursement n'ont pas été reconstruits.

## Correctifs de dépendances après audit

La recette V5 a synchronisé le manifeste racine avec le dépôt Medusa et ajouté les fichiers nécessaires au patch deepmerge. Copier aussi `dependencies/patches/deepmerge@4.3.1.patch` vers `patches/deepmerge@4.3.1.patch` à la racine Medusa, puis `dependencies/deepmerge-patch.test.cjs` vers `apps/backend/test/deepmerge-patch.test.cjs`. La déclaration pnpm `patchedDependencies` et le lockfile doivent accompagner ce patch. Après installation gelée, lancer `node --test test/deepmerge-patch.test.cjs` depuis `apps/backend`. Le patch réduit le risque identifié et l’avis upstream reste visible dans `pnpm audit`.

Le dossier `dependencies/` conserve les manifests et le lockfile effectivement vérifiés le 12 novembre 2026. Dans le clone du starter documenté ci-dessous, copier `dependencies/package.json` à la racine, `backend.package.json` vers `apps/backend/package.json`, `storefront.package.json` vers `apps/storefront/package.json`, `pnpm-lock.yaml` à la racine, `patches/` à la racine et `tests/deepmerge-patch.test.cjs` vers `apps/backend/test/`. Installer avec pnpm 10.11.1 et `install --frozen-lockfile`. Le lockfile est produit par pnpm. Les correctifs privilégient les versions majeures existantes. UUID 11.1.1 et minimatch 11.0.1 gardent leurs overrides ciblés. `deepmerge@4.3.1` reste signalé par npm (aucune version corrigée publiée) ; le patch local bloque la clé `__proto__` dans les points d’entrée CommonJS et UMD. Le contrôle reproductible est `pnpm --filter @dtc/backend test:security`. L’avis demeure visible dans `pnpm audit` et exige de retirer le patch seulement après mise à jour vers une version upstream corrigée.

Next.js et eslint-config-next sont en 16.4.1, Zod en 4.6.6. Les avis restants et les préconditions figurent dans `reports/pre-push/v2/dependency-matrix.json`. Le build storefront passe avec `NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY` et `MEDUSA_BACKEND_URL` fournis depuis la configuration locale. Les valeurs de secrets et credentials ne sont pas livrées. Les middlewares de propriété conservent les mêmes empreintes.

Starter officiel : https://github.com/medusajs/dtc-starter, SHA 0a84b2ac13dbf5091a84af4b54ce0b19f6c9ad55, Medusa 2.22.6. Copier compose.commerceops.yml à la racine du clone voisin, les deux fichiers API dans apps/backend/src/api/, et configure-agent.ts dans apps/backend/src/scripts/. Le middleware conserve la recherche existante et ajoute authentification, propriété et interdiction de receive_now. Retours fermés sauf activation marchande COMMERCEOPS_RETURNS_ENABLED=true côté serveur ET STORE_RETURNS_ENABLED=true côté agent ; le parcours complet de retour reste non validé.

Le compose utilise un mot de passe local DEMO_DB_PASSWORD à créer dans .env.docker ignoré. Ne pas committer ce fichier. Backend DATABASE_URL sur localhost:5433, Redis localhost:6380 ; générer JWT_SECRET et COOKIE_SECRET localement. Les données PostgreSQL sont dans le volume commerceops-demo_commerceops_pg. Ne jamais exécuter down -v sans autorisation.

Installation : npx.cmd --yes pnpm@10.11.1 install --frozen-lockfile. Depuis apps/backend : npx.cmd --yes pnpm@10.11.1 exec medusa db:migrate, puis medusa exec ./src/scripts/configure-agent.ts, puis medusa develop. Ces commandes ont été exécutées. Le script configure-agent ne fournit que clé publishable/région à l’agent, aucun accès Admin.

Les identifiants Admin générés sur cette machine se trouvent uniquement dans apps/backend/.env.admin ignoré. Ce fichier n’est pas livré dans Git. Les deux comptes client de test sont dans commerceops_ai/data/demo-credentials.json ignoré. Le storefront optionnel n’a pas été lancé ; le checkout sandbox a été exécuté via les API officielles.

Documentation officielle : https://docs.medusajs.com/resources/commerce-modules/order/secure-return-creation . La documentation et les fichiers du paquet installé ont été consultés.
