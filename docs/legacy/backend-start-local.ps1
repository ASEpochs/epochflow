param(
    [switch]$Cli,
    [switch]$Direct,
    [ValidateRange(0, 65535)]
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$previousNoProxy = [Environment]::GetEnvironmentVariable('NO_PROXY', 'Process')
$previousApiPort = [Environment]::GetEnvironmentVariable('API_PORT', 'Process')
Push-Location -LiteralPath $PSScriptRoot
try {
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        throw 'Missing .venv. Create it and install requirements-dev.txt first.'
    }
    if ($Direct) {
        $env:NO_PROXY = '*'
        Write-Output 'Direct network mode for this launch only; system proxy settings are unchanged.'
    }
    if ($Port -gt 0) {
        $env:API_PORT = [string]$Port
        Write-Output "API port for this launch: $Port"
    }

    & $projectPython 'scripts\check_environment.py'
    if ($LASTEXITCODE -ne 0) {
        throw 'Startup prerequisites are incomplete. Fix the errors listed above.'
    }

    if ($Cli) {
        & $projectPython 'api\main.py' '--cli'
    } else {
        & $projectPython 'api\main.py'
    }
} finally {
    [Environment]::SetEnvironmentVariable('NO_PROXY', $previousNoProxy, 'Process')
    [Environment]::SetEnvironmentVariable('API_PORT', $previousApiPort, 'Process')
    Pop-Location
}
