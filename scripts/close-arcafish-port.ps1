param(
    [Parameter(Mandatory = $true)]
    [int]$Port
)

$allowedProcessNames = @("python", "pythonw", "uvicorn")

for ($attempt = 1; $attempt -le 5; $attempt++) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if (-not $listeners) {
        exit 0
    }

    foreach ($listener in $listeners) {
        $processId = [int]$listener.OwningProcess
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }

        if ($allowedProcessNames -notcontains $process.ProcessName) {
            Write-Host "El puerto $Port esta ocupado por $($process.ProcessName) (PID $processId). No se cierra automaticamente."
            exit 2
        }

        Write-Host "Cerrando servidor anterior en el puerto $Port (PID $processId)..."
        Stop-Process -Id $processId -Force -ErrorAction Stop
    }

    Start-Sleep -Milliseconds 700
}

$remaining = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
if ($remaining) {
    $pids = ($remaining | ForEach-Object { $_.OwningProcess }) -join ", "
    Write-Host "No se pudo liberar el puerto $Port. PID(s) restante(s): $pids"
    exit 3
}

exit 0
