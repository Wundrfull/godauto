# Godot headless operations wrapper.
# Usage: .\tools\godot_cli.ps1 <command>
#   import  - Force reimport all assets
#   run     - Launch the game
#   export  - Export the project (requires export presets)
#   editor  - Open in Godot editor

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("import", "run", "editor", "export")]
    [string]$Command
)

$ErrorActionPreference = "Stop"

$GodotConsole = "C:\Users\dared\Documents\GameDev\Godot_v4.6-stable_win64_console.exe"
$GodotGui = "C:\Users\dared\Documents\GameDev\Godot_v4.6-stable_win64.exe"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)

switch ($Command) {
    "import" {
        Write-Host "Reimporting assets..." -ForegroundColor Cyan
        & $GodotConsole --headless --path $ProjectRoot --import
        Write-Host "Import complete." -ForegroundColor Green
    }
    "run" {
        Write-Host "Launching game..." -ForegroundColor Cyan
        & $GodotGui --path $ProjectRoot
    }
    "editor" {
        Write-Host "Opening editor..." -ForegroundColor Cyan
        & $GodotGui --editor --path $ProjectRoot
    }
    "export" {
        Write-Host "Exporting project..." -ForegroundColor Cyan
        $exportDir = Join-Path $ProjectRoot "export"
        New-Item -ItemType Directory -Force -Path $exportDir | Out-Null
        & $GodotConsole --headless --path $ProjectRoot --export-release "Windows Desktop" "$exportDir\IdleClicker.exe"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Exported to $exportDir" -ForegroundColor Green
        } else {
            Write-Host "Export failed. Do you have export presets configured?" -ForegroundColor Red
        }
    }
}
