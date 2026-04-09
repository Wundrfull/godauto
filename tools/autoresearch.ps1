# Autoresearch iteration driver.
# Tracks experiment iterations: modify -> test -> measure -> keep/discard.
# Usage: .\tools\autoresearch.ps1 -Description "Added cookie sprite" -Metric 0.3 -Kept kept

param(
    [Parameter(Mandatory=$true)]
    [string]$Description,

    [Parameter(Mandatory=$true)]
    [double]$Metric,

    [ValidateSet("kept", "discarded", "baseline")]
    [string]$Kept = "kept"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$ResultsFile = Join-Path $ProjectRoot "autoresearch" "results.tsv"

# Get current commit hash
$commit = (git -C $ProjectRoot rev-parse --short HEAD 2>$null)
if (-not $commit) { $commit = "uncommitted" }

# Get next iteration number
$lines = Get-Content $ResultsFile
$lastLine = $lines[-1]
$lastIter = 0
if ($lastLine -match '^\d+') {
    $lastIter = [int]($lastLine -split '\t')[0]
}
$nextIter = $lastIter + 1

# Timestamp
$timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")

# Append result
$entry = "$nextIter`t$timestamp`t$Metric`t$Kept`t$commit`t$Description"
Add-Content -Path $ResultsFile -Value $entry

Write-Host "Iteration $nextIter logged:" -ForegroundColor Green
Write-Host "  Metric:  $Metric"
Write-Host "  Status:  $Kept"
Write-Host "  Commit:  $commit"
Write-Host "  Desc:    $Description"

# Show progress summary
$allLines = Get-Content $ResultsFile | Select-Object -Skip 1
$metrics = $allLines | ForEach-Object { [double](($_ -split '\t')[2]) }
$best = ($metrics | Measure-Object -Maximum).Maximum
Write-Host "`nProgress: $nextIter iterations, best metric: $best" -ForegroundColor Cyan
