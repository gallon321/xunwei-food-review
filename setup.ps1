<#
Prepare a fresh course/portfolio installation on Windows.
Usage: .\setup.ps1             # empty application and prompted administrator
       .\setup.ps1 -Demo       # fictional restaurants and demo accounts
#>
param([switch]$Demo)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    $projectPython = '.\.venv\Scripts\python.exe'
} else {
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if ($systemPython) {
        $bootstrapPython = $systemPython.Source
    } elseif (Test-Path -LiteralPath 'D:\python\python.exe') {
        $bootstrapPython = 'D:\python\python.exe'
    } else {
        throw 'Python 3.11+ 未找到。请安装 Python 并确保 python 在 PATH 中。'
    }
    & $bootstrapPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败。' }
    $projectPython = '.\.venv\Scripts\python.exe'
}

& $projectPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败。' }

if ($Demo) {
    & $projectPython -m flask --app app init-db --demo
} else {
    & $projectPython -m flask --app app init-db
}
if ($LASTEXITCODE -ne 0) { throw '初始化数据库失败。' }

if (-not $Demo) {
    Write-Host '接下来创建管理员账号。用户名 3–20 字，密码 8–72 字。'
    & $projectPython -m flask --app app create-admin
    if ($LASTEXITCODE -ne 0) { throw '创建管理员失败。' }
}

Write-Host '安装完成。运行 .\start.ps1，然后打开 http://127.0.0.1:5000/'
