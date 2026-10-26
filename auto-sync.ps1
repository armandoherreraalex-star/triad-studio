$ErrorActionPreference = "Continue"
while ($true) {
    git fetch origin main 2>$null
    $changes = git status --porcelain
    if ($changes) {
        Write-Host "Cambios detectados. Esperando 20 segundos..." -ForegroundColor Yellow
        Start-Sleep -Seconds 20
        $changes = git status --porcelain
        if ($changes) {
            git add -A
            git diff --cached --quiet
            if ($LASTEXITCODE -ne 0) {
                $fecha = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                git commit -m "Actualizacion automatica $fecha"
                if ($LASTEXITCODE -eq 0) {
                    git push origin main
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "Cambios subidos a GitHub." -ForegroundColor Green
                    } else {
                        Write-Host "Error al subir. Revisa Git." -ForegroundColor Red
                    }
                }
            }
        }
    }
    Start-Sleep -Seconds 10
}
