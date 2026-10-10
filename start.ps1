$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Get-Command python -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    & '.\.venv\Scripts\python.exe' serve.py
} elseif ($projectPython) {
    & $projectPython.Source serve.py
} elseif (Test-Path -LiteralPath 'D:\python\python.exe') {
    & 'D:\python\python.exe' serve.py
} else {
    Write-Error 'Python was not found. Install Python and run: python -m pip install -r requirements.txt'
}
