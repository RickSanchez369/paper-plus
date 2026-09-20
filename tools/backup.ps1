# Dump the paper_plus database into backups/ with a timestamped filename.
# Credentials are read from .env; the password is passed via PGPASSWORD,
# never on the command line.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pgDump = "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
$envFile = Join-Path $root ".env"
$backupDir = Join-Path $root "backups"

if (-not (Test-Path $pgDump)) { throw "pg_dump not found at $pgDump" }
if (-not (Test-Path $envFile)) { throw ".env not found at $envFile" }

$line = Select-String -Path $envFile -Pattern '^\s*DATABASE_URL\s*=' | Select-Object -First 1
if (-not $line) { throw "DATABASE_URL not found in .env" }

$url = ($line.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
$m = [regex]::Match($url, '^postgres(?:ql)?://(?<user>[^:]+):(?<pass>[^@]+)@(?<host>[^:/]+):(?<port>\d+)/(?<db>.+)$')
if (-not $m.Success) { throw "Could not parse DATABASE_URL" }

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$outFile = Join-Path $backupDir "$($m.Groups['db'].Value)_$stamp.sql"

$env:PGPASSWORD = $m.Groups['pass'].Value
try {
    & $pgDump `
        --host $m.Groups['host'].Value `
        --port $m.Groups['port'].Value `
        --username $m.Groups['user'].Value `
        --dbname $m.Groups['db'].Value `
        --encoding UTF8 `
        --no-owner `
        --file $outFile
}
finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

$sizeKb = [math]::Round((Get-Item $outFile).Length / 1KB, 1)
Write-Host "Backup OK: $outFile ($sizeKb KB)"