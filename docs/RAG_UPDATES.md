# Recherche et actualisation des connaissances — 12 novembre 2026

## Causes et périmètre

L'ancien chargeur ne lisait que les objets JSON text/source et ignorait texte et Markdown. Les caches étaient attachés au chemin ou à une collection fixe, donc une API déjà lancée pouvait conserver une ancienne vectorisation. Le constructeur dense supprimait la collection active avant que les nouvelles embeddings soient prêtes. Le moteur ne vectorisait que le corps des passages ; les titres explicites des sous-flux ABCD étaient absents du signal. Enfin, l'obligation documentaire reposait sur le seul prompt du LLM, avec une ambiguïté entre politique de livraison et statut d'une commande.

Les modifications concernent l'ingestion, les index, le routage documentaire et la disponibilité de ce moteur. `app/medusa.py`, les middlewares Medusa et les transitions/contrôles d'approbation restent inchangés. Aucune nouvelle commande ou demande de retour autorisée n'a été créée pendant cette intervention.

## Contrat d'ingestion

JSON UTF-8, avec BOM accepté : un objet documentaire, une liste de documents ou une enveloppe `{"documents": [...]}`. Un document contient `text` (ou `content`), `source` (ou `url`), et facultativement `title`, `category`, `source_type`, `retrieved_at`. Le texte doit être non vide et la provenance une URI HTTP(S) ou URN explicite. Aucune permission de réutilisation n'est déduite de ces métadonnées.

Texte/Markdown : `guide.md` accompagné de `guide.md.meta.json`, par exemple :

```json
{"title":"Titre du document autorisé","category":"shipping","source":"https://example.org/original"}
```

Le Markdown peut aussi fournir du front matter YAML chargé avec `safe_load` :

```markdown
---
title: Titre du document autorisé
category: shipping
source: https://example.org/original
---
Texte réel du document.
```

Une provenance contradictoire entre front matter et sidecar est rejetée. Les fichiers invalides ou sans source font échouer la construction au lieu d'être ignorés silencieusement. Les exemples ci-dessus décrivent le format, pas un corpus officiel ajouté au projet. Les documents courts restent indexés. Les références et SHA256 du corps sont conservés ; titre, catégorie, URI et contenu constituent le texte vectorisé.

## Reconstruction et publication sûres

Depuis `commerceops_ai`, une reconstruction utilise un verrou exclusif par fichier cible. Le manifeste est écrit dans un fichier temporaire, synchronisé puis remplacé atomiquement. Une erreur laisse l'ancien manifeste disponible. Un verrou survivant à un crash exige une vérification opérateur ; il n'est jamais supprimé automatiquement par un autre constructeur.

Pour le dense, chaque construction crée une collection immutable avec un nom unique. Le manifeste n'est publié qu'après insertion complète et validation du nombre de passages. Il référence cette collection, le modèle et sa révision. Les anciennes collections sont conservées pour les lecteurs déjà en cours ; leur nettoyage éventuel est une opération séparée. Aucun index actif n'est détruit pendant un téléchargement ou calcul d'embeddings.

Le cache lexical dépend du contenu exact du manifeste, pas du chemin ni de la date du fichier. Le lecteur dense dépend de la collection/version enregistrée. L'hybride lit un seul manifeste pour toute la requête et refuse de fusionner des générations incompatibles. Une importation de nouveaux fichiers exige une reconstruction explicite ; après publication sur le même chemin, l'API la détecte sans redémarrage. Aucun endpoint public de reconstruction n'a été ajouté.

```powershell
.\.venv\Scripts\python.exe -m scripts.build_index --backend hybrid --source data/knowledge --output data/rag-v2/index.json --chunk-words 90 --overlap-words 20
```

L'API locale utilise désormais `INDEX_FILE=data/rag-v2/index.json` et conserve le backend lexical. Le changement initial de variable nécessite une relance ; les reconstructions suivantes sur ce chemin n'en nécessitent pas. `data/index.json` et la collection historique `knowledge` sont préservés, avec vérification de l'empreinte dans `reports/rag-v2/baseline-hashes.json`. Le nouvel index contient 55 documents et 217 passages, contre 205 dans la baseline : les petits passages terminaux ne sont plus perdus.

Le comparatif historique suppose ces deux artefacts locaux préservés. Ils ne sont pas redistribués dans Git. Pour reproduire les anciennes baselines sur une nouvelle machine, utiliser le constructeur du commit antérieur `5105491` avec le corpus/révision documentés, avant de construire le candidat séparément ; un index v2 ne doit pas être renommé « baseline historique ». Les nouveaux paramètres optionnels figurent dans `.env.example`, sans clé.

## Hybride et reranking optionnel

`RAG_BACKEND=hybrid` utilise l'union des candidats lexicaux et denses, puis une somme pondérée des similarités cosinus : `0.5 * lexical + 0.5 * dense`. Une absence dans un moteur vaut zéro. Chaque moteur conserve son seuil de candidature existant ; le seuil de fusion est 0,06. Ces valeurs sont des paramètres de développement figés, pas des probabilités ni des seuils cliniques de pertinence. Le pool vaut 20 par moteur, puis les sources sont dédupliquées avant le top 5. Les scores composants et les références restent visibles.

Le reranker CrossEncoder est désactivé par défaut. L'activer exige `RAG_RERANKER` et une révision figée `RAG_RERANKER_REVISION`. Il classe seulement les candidats déjà admis, sans inventer de références ou modifier les permissions. Son branchement a été testé par doublure, mais aucun modèle de reranking réel n'a été téléchargé ni mesuré : aucune performance de reranking n'est revendiquée.

## Routage et fidélité

Un garde explicite identifie les demandes de politique, conditions, procédure ou référence et lance `search_knowledge` avant toute génération. Ces réponses sont des extraits attribués, clairement présentés comme références externes. Sans résultat admissible, l'agent exprime son incertitude et demande une vérification humaine. Les instructions contenues dans un passage ne sont jamais exécutées. Cette voie est identifiée par `generation=extractive_documentary` : elle ne prétend pas être une réponse NVIDIA.

Une demande de statut, paiement ou livraison d'une commande identifiable garde la voie transactionnelle Medusa, sauf demande explicite de référence. Une question mêlant politique et action reçoit d'abord les références ; elle ne déclenche pas implicitement l'action. Les confirmations, l'identité, la propriété et les règles Medusa n'ont pas été assouplies. Le routage par motifs reste limité aux formulations couvertes ; il ne constitue pas une compréhension universelle des intentions.

Les citations extraites sont traçables, mais leur présence ne prouve pas qu'un passage répond au cas client. Les seuils peuvent produire des faux positifs ou des abstentions excessives. La fidélité sémantique et la pertinence doivent encore être jugées sur des annotations humaines vérifiées ; elles ne sont pas assimilées à la présence mécanique d'une citation.

## Mesures et limites

Rapport : `reports/rag-v2/development.json`. Les cinq configurations utilisent les mêmes 12 questions déjà consultées. Les noms de flux/sous-flux et l'existence des sources ont été vérifiés dans les vrais guidelines ; la pertinence n'est pas validée humainement. Les latences sont à chaud, chargement du modèle exclu. Le P95 utilise l'ordre statistique inférieur `floor(0.95*(n-1))` ; n=12 ne permet pas une conclusion robuste sur les queues de latence.

| Configuration | Recall@5 (n=12) | Latence moyenne mesurée |
|---|---:|---:|
| Lexical historique | 8/12 | 1,16 ms |
| Dense historique | 6/12 | 23,70 ms |
| Lexical avec métadonnées | 12/12 | 1,71 ms |
| Dense avec métadonnées | 12/12 | 27,16 ms |
| Hybride pondéré | 12/12 | 27,37 ms |

Abstention sur questions positives : 2/12 pour chaque baseline, 0/12 pour les trois variantes candidates. Deux sondes négatives de développement donnent une abstention de 2/2 pour chaque configuration. Ces chiffres mesurent seulement ce jeu ; ils ne prouvent ni une généralisation ni un gain additionnel de l'hybride. Le lexical enrichi est retenu pour la démo pour sa latence inférieure. Les rapports et baselines historiques n'ont pas été remplacés par ces scores.

Le jeu antérieur final ayant déjà été consulté, `evaluation/final-v3.jsonl` contient 16 nouveaux cas gelés. Ils n'ont pas été évalués ni utilisés pour modifier les paramètres. Leur SHA est dans `evaluation/final-v3.review.json`, qui exige identité, date et approbation humaine. « Vas-y » autorise la poursuite du travail, mais ne fournit pas cette attestation. La commande suivante échoue avant toute recherche si la revue du SHA exact manque :

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_retrieval_v2 --final
```

Résultats indépendants et fidélité humaine : `NOT_EVALUATED`, n=0, dans `reports/rag-v2/final-status.json`. Aucune amélioration générale n'est déclarée. Les tests techniques, le gate historique et un gate de non-régression limité au développement passent ; les refus Medusa réels 401/403, receive_now 400, confirmation étrangère 404 et répétition 409 restent vérifiés.
