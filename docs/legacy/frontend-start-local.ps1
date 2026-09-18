param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5173
)

$ErrorActionPreference = 'Stop'
$nodeDirectory = 'D:\DevelopmentTool\NodeJS\App\node-v24.21.0-win-x64'
$previousTaskPath = $env:PATH
Push-Location -LiteralPath $PSScriptRoot
try {
    $nodeExecutable = Join-Path $nodeDirectory 'node.exe'
    if (-not (Test-Path -LiteralPath $nodeExecutable)) {
        throw 'Configured Node LTS is missing. See README.md for the local Node directory.'
    }
    $viteExecutable = Join-Path $PSScriptRoot 'node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $viteExecutable)) {
        throw 'Frontend dependencies are missing. Install them using the configured Node LTS first.'
    }
    $env:PATH = "$nodeDirectory;$previousTaskPath"
    Write-Output "Frontend: http://127.0.0.1:$Port"
    & $nodeExecutable $viteExecutable '--host' '127.0.0.1' '--port' ([string]$Port) '--strictPort'
    if ($LASTEXITCODE -ne 0) { throw 'Frontend startup failed; check the port and output above.' }
} finally {
    $env:PATH = $previousTaskPath
    Pop-Location
}
