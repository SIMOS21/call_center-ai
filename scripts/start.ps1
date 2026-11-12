param([ValidateSet('api','ui','mlflow','medusa','infra','check')][string]$Service = 'check')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$projectPython = Join-Path (Get-Location) '.venv/Scripts/python.exe'
switch ($Service) {
  'api' { & $projectPython -m uvicorn app.api:api --host 127.0.0.1 --port 8001 }
  'ui' { & $projectPython -m streamlit run app/ui.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false }
  'mlflow' { & $projectPython -m mlflow ui --backend-store-uri sqlite:///data/mlflow.sqlite3 --host 127.0.0.1 --port 5000 }
  'infra' { Set-Location ../my-medusa-store; docker compose --env-file .env.docker -f compose.commerceops.yml up -d }
  'medusa' { Set-Location ../my-medusa-store/apps/backend; npx.cmd --yes pnpm@10.11.1 exec medusa develop }
  'check' { & $projectPython -m scripts.check_readiness }
}
exit $LASTEXITCODE
