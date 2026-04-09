# Export all .aseprite files from art/ to assets/sprites/.
# Usage: .\tools\export_all.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$ArtDir = Join-Path $ProjectRoot "art"
$ExportScript = Join-Path $ProjectRoot "tools" "export_sprite.ps1"

$files = Get-ChildItem -Path $ArtDir -Filter "*.aseprite" -Recurse

if ($files.Count -eq 0) {
    Write-Host "No .aseprite files found in $ArtDir" -ForegroundColor DarkYellow
    exit 0
}

Write-Host "Found $($files.Count) .aseprite file(s)" -ForegroundColor Cyan

$failed = 0
foreach ($file in $files) {
    try {
        & $ExportScript -InputFile $file.FullName
    } catch {
        Write-Host "FAILED: $($file.Name) - $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n=== Export Complete ===" -ForegroundColor Cyan
Write-Host "  Total:  $($files.Count)"
Write-Host "  OK:     $($files.Count - $failed)" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "  Failed: $failed" -ForegroundColor Red
}
