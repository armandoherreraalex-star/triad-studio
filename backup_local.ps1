$ErrorActionPreference = "Stop"
$root = "$env:USERPROFILE\Documents\triad-studio"
Set-Location $root
$log = Join-Path $root "backup_local.log"
$desktop = Join-Path $env:USERPROFILE "Desktop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zip = Join-Path $desktop "TRIAD_STUDIO_LOCAL_$stamp.zip"
try {
    $exclude = @(".git", ".venv", ".venv313", "__pycache__", "node_modules", ".pytest_cache", ".env", ".env.local")
    $items = Get-ChildItem -Force | Where-Object { $_.Name -notin $exclude }
    Compress-Archive -Path $items.FullName -DestinationPath $zip -CompressionLevel Optimal -ErrorAction Stop
    $env:TRIAD_BACKUP_ZIP = $zip
    & "$root\.venv\Scripts\python.exe" "$root\upload_local_backup.py" *>> $log
    if ($LASTEXITCODE -ne 0) { throw "Falló la subida a R2." }
    Add-Content $log "$(Get-Date -Format s) OK: $zip"
}
catch {
    Add-Content $log "$(Get-Date -Format s) ERROR: $($_.Exception.Message)"
    exit 1
}
