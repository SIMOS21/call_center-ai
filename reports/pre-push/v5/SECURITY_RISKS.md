# Risques de sécurité et mesures compensatoires V5

## Clé NVIDIA exposée

Une clé NVIDIA a été visible dans le contexte IDE transmis pendant cette mission. Sa valeur est exclue des preuves. La révocation de cette clé et son remplacement restent à confirmer par l’utilisateur. La réponse « continue » permet de poursuivre les travaux indépendants et ne constitue pas une attestation de rotation.

La première série de recette a utilisé un processus FastAPI isolé avec une clé fournisseur vide et une base SQLite de test. L’environnement V4 et son fichier `.env` ont été conservés. Les parcours métier réels et le rendu documentaire de secours ont été vérifiés. Une série complémentaire a ensuite utilisé l’API existante et NVIDIA avec les seules questions publiques et données de démonstration autorisées. Six sélections de faits NVIDIA réussissent et deux demandes sans politique applicable s’abstiennent avant inférence. Aucun secret n’a été modifié ou exporté. Le succès d’un appel fournisseur ne permet pas d’attester la révocation de la clé exposée. Ce dernier point constitue un risque P0 de livraison.

## Les cinq avis recensés

L’audit de l’environnement Windows lit les métadonnées de 170 paquets et signale quatre avis ChromaDB distincts sur la version 1.5.9. La sortie contient cinq enregistrements, avec un identifiant répété. L’audit pnpm du graphe de 1 700 dépendances signale un avis faible deepmerge. Les codes de sortie des deux scanners valent 1 et leurs sorties originales sont conservées.

| Avis | Précondition décrite par la source | Applicabilité observée et mesure compensatoire | État |
|---|---|---|---|
| GHSA-f4j7-r4q5-qw2c, critique | Création de collection par une API serveur Chroma avec modèle malveillant et code distant autorisé. | Le chemin configuré est lexical. L’application n’utilise pas de client HTTP Chroma et son Compose ne lance pas ce serveur. Le profil API/MLflow alternatif ne contient pas Chroma. | Version Windows affectée, préconditions absentes du chemin vérifié. [Avis primaire](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) |
| GHSA-36p7-vc44-83pf, critique | Actualisation d’une collection sur le serveur, code distant autorisé et permission UPDATE_COLLECTION. | La Store API Medusa et l’API CommerceOps ne proposent pas cette opération Chroma. Le client dense existant est embarqué et le profil alternatif exclut cette bibliothèque. | Avis conservé dans l’audit Windows. [Avis primaire](https://github.com/advisories/GHSA-36p7-vc44-83pf) |
| GHSA-xph7-9rjv-w5fr, élevée | Contrôle de permission SimpleRBAC sans vérification de portée tenant, base ou collection. | Aucun fournisseur SimpleRBAC n’est configuré par l’application. Un déploiement Chroma multi-tenant demanderait une nouvelle analyse. | Avis conservé, surface RBAC hors du chemin vérifié. [Avis primaire](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) |
| GHSA-2wm9-hf6c-p5cr, élevée | API Chroma authentifiée acceptant des opérations inter-tenant. | L’API de collections Chroma est absente de l’architecture exécutée. Les contrôles Medusa portent sur un autre système et ne sont pas présentés comme un correctif Chroma. | Avis conservé dans l’environnement complet. [Avis primaire](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) |
| GHSA-gcqx-w48m-w2h4, faible | Fusion d’un objet malveillant entraînant un empoisonnement du prototype du résultat. | Le graphe comprend Jest et le chemin Medusa/SendGrid. Le provider SendGrid n’est pas configuré. Le patch pnpm rejette `__proto__` et son test vérifie le chemin effectivement résolu depuis SendGrid. | Mitigation locale testée, avis npm toujours présent. [Avis primaire](https://github.com/advisories/GHSA-gcqx-w48m-w2h4) |

Les registres interrogés donnent ChromaDB 1.5.9 et deepmerge 4.3.1 comme dernières versions publiées. Les avis consultés ne proposent pas de version corrigée. Les réponses datées de la recette sont conservées dans `vendor-versions.json`. [Registre Python](https://pypi.org/pypi/chromadb/json), [registre npm](https://registry.npmjs.org/deepmerge/latest)

`trust_remote_code=False` concerne les chargeurs SentenceTransformers. Cette option n’est pas utilisée comme preuve de correction des failles serveur Chroma. L’analyse ci-dessus repose sur les surfaces réellement utilisées, le code préservé et les audits exécutés. Elle ne constitue pas un test d’intrusion.

## Profil API et MLflow sans Chroma

Un conteneur Python 3.12 neuf a installé le lock Linux existant et MLflow 3.18.0. Les versions exactes ont été figées dans `api-mlflow-profile.lock.txt`. Les 163 tests passent. Une recherche lexicale sur les fixtures autorisées et une trace MLflow persistée puis relue réussissent. Le test confirme l’absence de module Chroma. L’audit des 111 paquets de cette résolution ne trouve aucun avis connu. Le lock Linux de base, composé de 61 paquets, donne également zéro avis connu.

Ce profil offre une voie pour éviter l’installation de Chroma dans l’environnement API lexical tout en conservant MLflow. Les composants denses et hybrides restent disponibles dans le code et dans le profil MLOps existant. Leur activation exige leurs dépendances et une revue de leur exposition. Aucun paquet du poste ni service existant n’a été supprimé ou reconstruit.

La validation de ce profil couvre les tests, le retrieval lexical et la persistance locale MLflow. Le parcours complet Medusa depuis ce conteneur précis reste PENDING. Les parcours métier V5 réels ont utilisé l’installation Windows V4 avec une instance API de recette isolée.

## Configuration et exploitation

Les ports API, Streamlit, MLflow, PostgreSQL et Redis observés sont liés à la boucle locale. Medusa écoute sur `::` au port 9000. Ce constat ne démontre pas son exposition à Internet. Les règles de pare-feu et le périmètre réseau du poste restent à contrôler avant un déploiement public.

Une suppression de deepmerge par retrait de ses dépendants affecterait le graphe Medusa/SendGrid et les outils Jest. Cette recette préserve les fonctionnalités et conserve le patch testé. Une évolution du graphe doit être suivie des tests du patch, du lint et des parcours métier concernés.

Les écritures Medusa incertaines continuent de relever de `docs/MEDUSA_UNCERTAIN_WRITES.md`. La création d’un panier et son ajout de ligne restent deux écritures distinctes. Le rapprochement opérateur et une nouvelle confirmation explicite demeurent nécessaires dans les cas non résolus. Les tests de recette ne créent aucune commande ni remboursement financier.

## Secrets dans les preuves et les traces

Le scanner local de sources passe. Le contrôle complémentaire confronte les fichiers candidats, les objets indexés et l’historique local des deux dépôts aux formats de clés et aux credentials connus, conservés uniquement en mémoire. Les listes publiques excluent les fichiers privés et le jeu final gelé.

Un échantillon des 50 traces MLflow les plus récentes a été relu. Aucun JWT, marqueur d’autorisation ni credential connu n’a été détecté. Les contenus bruts et les identifiants de traces ne sont pas exportés. Ce contrôle est borné à cet échantillon et aux règles documentées dans `trace-privacy.json`.
