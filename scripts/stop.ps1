# FinAlly - stop the app (Windows PowerShell). See PLAN.md SS11, SS13.C6.
#
# Idempotent: safe to run repeatedly, including when nothing is running.
# Stops and removes the container only. Does NOT remove the "finally-data"
# volume - your portfolio, watchlist, and chat history persist across
# start/stop cycles.
#
# To fully reset the app's data (irreversible):
#   scripts\stop.ps1
#   docker volume rm finally-data

$ErrorActionPreference = "Continue"

$ContainerName = "finally"

$existing = docker ps -aq --filter "name=^/$ContainerName$"
if ($existing) {
    Write-Host "Stopping $ContainerName..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
    Write-Host "Stopped. Data preserved in the 'finally-data' volume."
} else {
    Write-Host "FinAlly is not running (nothing to do)."
}
