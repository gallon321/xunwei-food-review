<# Build a source handoff ZIP without databases, secrets or local dependencies. #>
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$archiveDir = Join-Path $projectRoot 'dist'
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
$archivePath = Join-Path $archiveDir 'xunwei-source-1.0.0.zip'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipStream = [System.IO.File]::Open($archivePath, [System.IO.FileMode]::Create)
try {
    $archive = [System.IO.Compression.ZipArchive]::new($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $entries = @('app.py', 'serve.py', 'setup.ps1', 'start.ps1', 'README.md',
                     'requirements.txt', '.gitignore')
        $folders = @('docs', 'scripts', 'static', 'templates', 'tests', 'xunwei')
        foreach ($folder in $folders) {
            Get-ChildItem -LiteralPath (Join-Path $projectRoot $folder) -File -Recurse | ForEach-Object {
                if ($_.FullName -notmatch '(^|[\\/])(__pycache__|\.pytest_cache)([\\/]|$)' -and
                    $_.Extension -notin @('.pyc', '.db')) {
                    $entries += $_.FullName.Substring($projectRoot.Length + 1)
                }
            }
        }
        foreach ($relative in $entries) {
            $source = Join-Path $projectRoot $relative
            $entryName = 'xunwei/' + $relative.Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, $source, $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    } finally {
        $archive.Dispose()
    }
} finally {
    $zipStream.Dispose()
}
Write-Host "源码包已生成：$archivePath"
