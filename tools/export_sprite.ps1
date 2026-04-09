# Export a single .aseprite file to spritesheet PNG + JSON metadata.
# Usage: .\tools\export_sprite.ps1 art\cookie.aseprite [assets\sprites\cookie]

param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile,

    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

$AsepritePath = "C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)

if (-not (Test-Path $InputFile)) {
    Write-Host "ERROR: File not found: $InputFile" -ForegroundColor Red
    exit 1
}

$baseName = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)

# Default output dir: assets/sprites/<basename>/
if (-not $OutputDir) {
    $OutputDir = Join-Path $ProjectRoot "assets" "sprites" $baseName
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$sheetPath = Join-Path $OutputDir "${baseName}_sheet.png"
$jsonPath = Join-Path $OutputDir "${baseName}.json"

Write-Host "Exporting: $InputFile -> $OutputDir" -ForegroundColor Cyan

# Export spritesheet + JSON metadata
& $AsepritePath -b $InputFile `
    --sheet $sheetPath `
    --sheet-type rows `
    --data $jsonPath `
    --format json-array `
    --trim `
    --list-tags

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Aseprite export failed" -ForegroundColor Red
    exit 1
}

# Also export individual frame as standalone PNG (for single-frame sprites)
$singlePath = Join-Path $OutputDir "${baseName}.png"
& $AsepritePath -b $InputFile --save-as $singlePath

Write-Host "Exported:" -ForegroundColor Green
Write-Host "  Sheet: $sheetPath"
Write-Host "  JSON:  $jsonPath"
Write-Host "  Frame: $singlePath"
