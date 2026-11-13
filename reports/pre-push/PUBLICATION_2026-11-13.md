# Publication du code CommerceOps AI

Publication demandée explicitement le 13 novembre 2026 vers `https://github.com/SIMOS21/call_center-ai`, branche `main`, depuis la base distante `510549132f9d9fde58afd108063ab7c1cad9cf85`. Cette autorisation remplace la consigne précédente de ne pas committer/pousser. Le verdict historique NO-GO de préparation à la production n'est pas réécrit en validation d'exploitation.

La sélection inclut la dernière version applicative, les régressions, les fixtures documentaires autorisées, les lockfiles, la CI et les livrables d'audit publics expurgés. Elle inclut `app/documentary_format.py`, `app/interpreter.py`, `app/shopping.py` et tous les modules nécessaires. Les correctifs Medusa sont inclus dans `integrations/medusa` avec les manifests, le lockfile, le patch deepmerge et les tests de propriété. Aucun push vers `medusajs/dtc-starter` n'est prévu.

Les seize cas gelés et leurs annotations privées ne sont pas publiés ni modifiés. `.env`, clés, JWT, credentials de démonstration, bases, datasets bruts, environnements, caches, archives et logs sensibles restent exclus. Les anciennes modifications indexées extérieures à la sélection sont retirées de ce commit sans supprimer leur contenu local. Les références métier de démonstration présentes dans les documents retenus sont expurgées sans changer les métriques.

Le contrôle de l'arbre complet a également repéré quatorze fichiers historiques déjà suivis, dont un ancien jeu final, sa revue et des journaux/XML. Ils sont retirés de l'index du nouveau commit, en conservant leurs fichiers locaux. L'historique distant antérieur n'est pas réécrit. Les seize cas actuels `final-v3` gardent leurs empreintes et restent privés.

La recette globale précédente a vérifié 267 tests localement et dans Python 3.12 propre, 25 scénarios réels, cinq tests Node de sécurité, Ruff CI, deux gates, secrets et pip check. Une nouvelle vérification est faite sur le contenu retenu pour publication. Ses journaux et le contrôle de la CI distante sont conservés localement dans `reports/pre-push/publish/`, ignoré par Git. Aucun résultat CI futur n'est présumé réussi dans ce document.

Limites maintenues, sans prétendre à une validation humaine ou indépendante réalisée. La dernière révocation/remplacement de clé exposée n'est pas attestée. Les quatre avis Chroma et l'avis deepmerge restent ouverts avec les protections décrites dans l'audit. La revue des seize scénarios, l'inspection visuelle humaine et la qualification de production restent à effectuer.
