# Medusa local integration

Starter officiel : https://github.com/medusajs/dtc-starter, SHA 0a84b2ac13dbf5091a84af4b54ce0b19f6c9ad55, Medusa 2.22.6. Copier compose.commerceops.yml à la racine du clone voisin, les deux fichiers API dans apps/backend/src/api/, et configure-agent.ts dans apps/backend/src/scripts/. Le middleware conserve la recherche existante et ajoute authentification, propriété et interdiction de receive_now. Retours fermés sauf activation marchande COMMERCEOPS_RETURNS_ENABLED=true côté serveur ET STORE_RETURNS_ENABLED=true côté agent ; le parcours complet de retour reste non validé.

Le compose utilise un mot de passe local DEMO_DB_PASSWORD à créer dans .env.docker ignoré. Ne pas committer ce fichier. Backend DATABASE_URL sur localhost:5433, Redis localhost:6380 ; générer JWT_SECRET et COOKIE_SECRET localement. Les données PostgreSQL sont dans le volume commerceops-demo_commerceops_pg. Ne jamais exécuter down -v sans autorisation.

Installation : npx.cmd --yes pnpm@10.11.1 install --frozen-lockfile. Depuis apps/backend : npx.cmd --yes pnpm@10.11.1 exec medusa db:migrate, puis medusa exec ./src/scripts/configure-agent.ts, puis medusa develop. Ces commandes ont été exécutées. Le script configure-agent ne fournit que clé publishable/région à l’agent, aucun accès Admin.

Les identifiants Admin générés sur cette machine se trouvent uniquement dans apps/backend/.env.admin ignoré. Ce fichier n’est pas livré dans Git. Les deux comptes client de test sont dans commerceops_ai/data/demo-credentials.json ignoré. Le storefront optionnel n’a pas été lancé ; le checkout sandbox a été exécuté via les API officielles.

Documentation officielle : https://docs.medusajs.com/resources/commerce-modules/order/secure-return-creation . La documentation et les fichiers du paquet installé ont été consultés.
