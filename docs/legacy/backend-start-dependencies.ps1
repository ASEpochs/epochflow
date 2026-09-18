param(
    [int]$StartupTimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'

function Test-NativeProbe {
    param([string]$Executable, [string[]]$ProbeArguments)
    # Windows PowerShell treats native stderr as an error even when redirected.
    $ErrorActionPreference = 'Continue'
    & $Executable @ProbeArguments *> $null
    return ($LASTEXITCODE -eq 0)
}

Push-Location -LiteralPath $PSScriptRoot
try {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCommand) {
        $dockerExecutable = $dockerCommand.Source
    } else {
        $dockerExecutable = 'D:\DevelopmentTool\Docker\App\resources\bin\docker.exe'
    }
    if (-not (Test-Path -LiteralPath $dockerExecutable)) {
        throw 'Docker is missing. Install Docker Desktop first.'
    }

    # Never install or cancel WSL here: an existing installer may still be running.
    if (-not (Test-NativeProbe 'wsl.exe' @('--version'))) {
        throw 'WSL is not ready. Let the existing WSL installation finish, then rerun this script.'
    }

    if (-not (Test-NativeProbe $dockerExecutable @('info', '--format', '{{.ServerVersion}}'))) {
        $desktopExecutable = Join-Path (Split-Path (Split-Path $dockerExecutable -Parent) -Parent) '..\Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $desktopExecutable)) {
            throw 'Start Docker Desktop manually, then rerun this script.'
        }
        if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
            Start-Process -FilePath $desktopExecutable -WindowStyle Hidden | Out-Null
        }
        Write-Output 'Waiting for the Docker engine to start...'
        $startupDeadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
        do {
            Start-Sleep -Seconds 3
            $engineReady = Test-NativeProbe $dockerExecutable @('info', '--format', '{{.ServerVersion}}')
        } while (-not $engineReady -and (Get-Date) -lt $startupDeadline)
        if (-not $engineReady) {
            throw 'Docker engine startup timed out. Check Docker Desktop for a WSL/restart prompt.'
        }
    }

    # Start only this project's dependencies. Do not prune, delete, or recreate volumes.
    & $dockerExecutable compose up -d --wait --wait-timeout $StartupTimeoutSeconds redis chromadb
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency startup failed. Check the Docker pull output and container health.'
    }
    & $dockerExecutable compose ps redis chromadb
    Write-Output 'Dependencies ready. Run .\start-local.ps1 -Direct to start EchoMind.'
} finally {
    Pop-Location
}
