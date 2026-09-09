# FinAlly - start the app (Windows PowerShell). See PLAN.md SS11, SS13.C6.
#
# Idempotent: safe to run repeatedly.
#   - If the container is already running, prints the URL and exits.
#   - If it exists but is stopped, restarts it (no rebuild).
#   - Otherwise builds the image and creates the container.
#
# Usage:
#   scripts\start.ps1              # build only if the image doesn't exist yet
#   scripts\start.ps1 -Build       # force a rebuild even if the image exists
#
# Reset (wipe the database, keep the image): docker volume rm finally-data
# (the container must be stopped first - run scripts\stop.ps1).

param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ImageName = "finally"
$ContainerName = "finally"
$VolumeName = "finally-data"
$Port = if ($env:PORT) { $env:PORT } else { "8000" }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
    Write-Warning ".env not found. Copy .env.example to .env and add your OPENROUTER_API_KEY before chat will work (the rest of the app still runs without it)."
}

$running = docker ps -q --filter "name=^/$ContainerName$"
if ($running) {
    Write-Host "FinAlly is already running at http://localhost:$Port"
    exit 0
}

$imageExists = docker images -q $ImageName
if ($Build -or -not $imageExists) {
    Write-Host "Building image $ImageName..."
    docker build -t $ImageName $RepoRoot
}

docker volume create $VolumeName | Out-Null

$existing = docker ps -aq --filter "name=^/$ContainerName$"
if ($existing) {
    Write-Host "Restarting existing container $ContainerName..."
    docker start $ContainerName | Out-Null
} else {
    Write-Host "Creating container $ContainerName..."
    $envFileArgs = @()
    if (Test-Path (Join-Path $RepoRoot ".env")) {
        $envFileArgs = @("--env-file", ".env")
    }
    docker run -d `
        --name $ContainerName `
        -p "${Port}:8000" `
        -v "${VolumeName}:/app/db" `
        @envFileArgs `
        $ImageName | Out-Null
}

Write-Host "FinAlly is running at http://localhost:$Port"

# Best-effort browser open (PLAN SS11: "optionally"). Never fails the script.
try {
    Start-Process "http://localhost:$Port" | Out-Null
} catch {
    # ignore -- best effort only
}
