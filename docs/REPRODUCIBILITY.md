# Reproductibilité — exécution du 11 novembre 2026

## Environnement observé
Windows PowerShell ; Python 3.14.3 (seule version présente), Node 24.13.0, Git 2.52.0.windows.1, Docker Engine 29.0.1, Compose 2.40.3, pnpm Medusa 10.11.1. Python 3.12 reste la version de CI ; l’environnement local 3.14 a passé les tests mais le lock Windows ne doit pas être utilisé sur Linux. Versions exactes : requirements-windows-py314.lock.txt. Les contraintes d’origine sont conservées dans requirements.txt. Aucun package Python global modifié.

WSL ne contenait qu’une distribution docker-desktop après lancement autorisé de Docker. PowerShell a donc été conservé. Docker Desktop a dû être démarré ; les opérations sur le moteur ont requis l’accès hors sandbox. Aucun volume existant supprimé.

## Sources et versions
ABCD officiel : https://github.com/asappresearch/abcd, révision master observée 6b8700ce67c6b37b062dd7a60abc76d7ef832a97. Le collecteur utilise désormais cette révision immuable ; URLs lisibles des sous-flux conservées dans les résultats. SHA256 de chaque fichier dans reports/source_manifest.json ; les données brutes et documents sont exclus de Git. Guidelines, kb, ontology et dialogues téléchargés. Seules les 55 consignes de sous-flux entrent dans l’index. Les 100 prompts de dialogues restent séparés. Les consignes ABCD sont des procédures de recherche, pas des règles commerciales de la boutique.

Medusa : dépôt officiel dtc-starter, SHA 0a84b2ac13dbf5091a84af4b54ce0b19f6c9ad55 ; paquets 2.22.6 ; installation pnpm avec lockfile gelé. Personnalisations archivées dans integrations/medusa/. PostgreSQL 16-alpine sur 5433 et Redis 7-alpine sur 6380. Le backend est lancé sur Windows ; bus d’événements et verrouillage par défaut en mémoire, adaptés seulement à cette démonstration mono-instance. Redis est lancé mais les modules distribués ne sont pas configurés.

Olist : aucun fichier fourni/importé ; zéro ligne historique locale. eBay : aucune collecte tentée, autorisation et conditions à vérifier avant toute activation. Le PDF du cours n’était pas fourni dans le projet ; matrice de la mission utilisée.

## Reconstruction Python
Depuis commerceops_ai, PowerShell :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt mlflow
Copy-Item .env.example .env # seulement si .env absent
.\.venv\Scripts\python.exe -m scripts.collect_real_sources --abcd
.\.venv\Scripts\python.exe -m scripts.build_abcd_eval
.\.venv\Scripts\python.exe -m scripts.benchmark
.\.venv\Scripts\python.exe -m scripts.manifest
```

WSL/Linux avec Python 3.12 : python3 -m venv .venv, puis .venv/bin/python au lieu de .venv/Scripts/python.exe. Ce chemin Linux est une adaptation documentée, pas une exécution réalisée sur cette machine.

`benchmark` compare 90/20 et 180/35 sur 12 cas explicitement annotés par agent. Il sélectionne la configuration ayant le meilleur Recall@5, reconstruit l’index actif et ne remplace PAS la baseline sans --record-baseline. Les mesures de latence sont des requêtes à chaud, vectorisation exclue, sur cette machine, hors réseau/API. Résultats dans reports/evaluation.json ; deux runs référencés dans ce fichier. Pas d’embedding téléchargé ni d’index dense créé. Seuil lexical 0.12 : garde conservatrice de développement, à calibrer sur annotations humaines ; aucune garantie générale de pertinence.

## Reconstruction Medusa et secrets
Suivre integrations/medusa/README.md et le README officiel du SHA indiqué. Ne jamais écraser des secrets existants. Générer les secrets locaux dans les fichiers ignorés ; configure-agent.ts récupère clé publishable/région de la boutique de test. Exécuter les migrations une fois avant le démarrage. Le seed crée quatre produits, une région Europe, le canal de vente, les stocks, la livraison et le fournisseur de paiement manuel pp_system_default. Aucun paiement financier réel.

L’agent utilise NVIDIA https://integrate.api.nvidia.com/v1 et nvidia/nemotron-3.5-lightning-30b-a3b. LLM_API_KEY doit être renseignée localement, puis l’API relancée. Aucun appel NVIDIA réel validé en l’absence de clé. Référence : https://docs.api.nvidia.com/nim/reference/meta-llama-3_3-70b-instruct-infer .

## Vérifications exécutées
- python -m pytest tests -q : 39 tests réussis ; rapport JUnit dans reports/pytest.xml. Un avertissement de dépréciation Starlette/httpx n’empêche pas les tests.
- python -m ruff check app tests scripts --select E4,E7,E9,F63,F7,F82 : validation après chaque groupe de correctifs ; voir état final.
- python -m scripts.smoke_medusa : vraie commande sandbox, deux comptes, refus étrangers, ticket et confirmation unique. Ce script crée une nouvelle commande à chaque exécution : le lancer intentionnellement sur la boutique locale seulement.
- python -m scripts.check_readiness : quatre endpoints HTTP ; recherche positive FR et refus d’une question sans vocabulaire du corpus.
- python -m scripts.quality_gate : baseline mesurée, contrôles non vides, valeurs finies obligatoires. Tests de régression/absence/vide inclus dans pytest.
- python -m scripts.verify_trace : une trace applicative persistée relue par son ID ; aucune entrée/sortie privée stockée.
- Streamlit AppTest : chargement sans exception. Aucun navigateur ni vidéo enregistré.

## Relance sur cette machine
Depuis commerceops_ai, lancer scripts/start.cmd avec les arguments infra, medusa, api, ui, mlflow dans les terminaux appropriés, puis check. Toutes les commandes sous-jacentes ont été exécutées ; les URLs sont 9000/app, 8001/docs, 8501, 5000. Aucun push ni CI distante effectué. Les fichiers reports/ contiennent des preuves locales, jamais une preuve d’exécution GitHub Actions.

## Validation finale P0/P1

NVIDIA : mod?le Llama initial retir? (HTTP 410), Nemotron 3 Super inaccessible (404), Nemotron 3.5 Lightning r?ellement fonctionnel. `scripts.demo_agent` cr?e un panier apr?s confirmation, `scripts.complete_agent_demo` termine ce m?me panier en sandbox et cr?e un ticket. `scripts.smoke_return` exige la fixture produite par le workflow local prepare-return-demo.ts et les flags locaux activ?s ; ne pas relancer sur un article d?j? retourn?. `scripts.verify_return_security` v?rifie les refus et lit le retour via Admin uniquement dans ce script, jamais dans l?agent.

La cl? doit ?tre remplac?e apr?s son exposition dans une sortie technique. Le d?p?t n?a aucun commit ni remote. Les commandes qui modifient Medusa sont intentionnelles et r?serv?es ? la boutique locale. Les mesures enregistr?es ne constituent pas une validation statistique ind?pendante.

PowerShell est configur? Restricted sur cette machine. Le lanceur start.cmd invoque start.ps1 avec ExecutionPolicy Bypass pour ce seul processus ; aucune politique syst?me n?est modifi?e. L?invocation directe de start.ps1 a ?t? test?e et refus?e ; utiliser start.cmd.
