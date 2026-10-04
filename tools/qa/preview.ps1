# One command to LOOK at the app: builds a throwaway SQLite database with demo data and serves it on
# http://localhost:8001. The real PostgreSQL database and .env are never touched.
#
#   .\tools\qa\preview.ps1
#
# Run from the repo root. Stop the server with Ctrl+C. Every run starts from a clean demo database.
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

$env:PYTHONIOENCODING = "utf-8"
$env:QA_DB = (Join-Path $PWD "tools\qa\.preview.sqlite3")
Remove-Item $env:QA_DB -ErrorAction SilentlyContinue

python tools/qa/run_qa_server.py migrate
python tools/qa/seed_qa_db.py
python tools/qa/seed_demo_data.py

Write-Host ""
Write-Host "Open http://localhost:8001  - sign in with (phone, then password):"
Get-Content "tools\qa\.qa_login.txt"
Write-Host ""
python tools/qa/run_qa_server.py
