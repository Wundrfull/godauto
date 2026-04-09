# gdauto Game Development Toolkit - Setup Script
# Run once to configure pixel-mcp and verify dependencies.

param(
    [switch]$SkipPixelMcp,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$ToolsDir = Join-Path $ProjectRoot "tools" "bin"
$PixelMcpVersion = "0.5.0"
$PixelMcpExe = Join-Path $ToolsDir "pixel-mcp.exe"
$AsepritePath = "C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe"
$GodotPath = "C:\Users\dared\Documents\GameDev\Godot_v4.6-stable_win64_console.exe"
$ConfigDir = Join-Path $env:USERPROFILE ".config" "pixel-mcp"
$ConfigFile = Join-Path $ConfigDir "config.json"
$TempDir = Join-Path $ProjectRoot ".tmp" "pixel-mcp"

Write-Host "=== gdauto Setup ===" -ForegroundColor Cyan

# --- Step 1: Verify Aseprite ---
Write-Host "`n[1/4] Checking Aseprite..." -ForegroundColor Yellow
if (Test-Path $AsepritePath) {
    $asepriteVersion = & $AsepritePath --version 2>&1
    Write-Host "  Found: $asepriteVersion" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Aseprite not found at $AsepritePath" -ForegroundColor Red
    Write-Host "  Update `$AsepritePath in this script to match your installation." -ForegroundColor Red
    exit 1
}

# --- Step 2: Verify Godot ---
Write-Host "`n[2/4] Checking Godot..." -ForegroundColor Yellow
if (Test-Path $GodotPath) {
    $godotVersion = & $GodotPath --version 2>&1
    Write-Host "  Found: Godot $godotVersion" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Godot not found at $GodotPath" -ForegroundColor DarkYellow
    Write-Host "  Godot is only needed for running the game; file manipulation works without it." -ForegroundColor DarkYellow
}

# --- Step 3: Install pixel-mcp ---
Write-Host "`n[3/4] Setting up pixel-mcp..." -ForegroundColor Yellow

if (-not $SkipPixelMcp) {
    if ((Test-Path $PixelMcpExe) -and -not $Force) {
        Write-Host "  pixel-mcp already installed at $PixelMcpExe" -ForegroundColor Green
    } else {
        # Download pre-built binary (no Go required)
        $downloadUrl = "https://github.com/willibrandon/pixel-mcp/releases/download/v$PixelMcpVersion/pixel-mcp_${PixelMcpVersion}_Windows_x86_64.tar.gz"
        $downloadPath = Join-Path $env:TEMP "pixel-mcp.tar.gz"

        Write-Host "  Downloading pixel-mcp v$PixelMcpVersion..."
        New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
        Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadPath -UseBasicParsing

        Write-Host "  Extracting..."
        # Extract tar.gz
        $extractDir = Join-Path $env:TEMP "pixel-mcp-extract"
        if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
        New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
        tar -xzf $downloadPath -C $extractDir

        # Find and copy the binary
        $extractedExe = Get-ChildItem -Path $extractDir -Filter "pixel-mcp.exe" -Recurse | Select-Object -First 1
        if ($extractedExe) {
            Copy-Item $extractedExe.FullName $PixelMcpExe -Force
            Write-Host "  Installed to $PixelMcpExe" -ForegroundColor Green
        } else {
            Write-Host "  ERROR: pixel-mcp.exe not found in archive" -ForegroundColor Red
            exit 1
        }

        # Cleanup
        Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
        Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    # --- Create pixel-mcp config ---
    if (-not (Test-Path $ConfigFile) -or $Force) {
        New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
        New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

        $config = @{
            aseprite_path = $AsepritePath
            temp_dir = $TempDir
            timeout = 30
        } | ConvertTo-Json -Depth 2

        Set-Content -Path $ConfigFile -Value $config -Encoding UTF8
        Write-Host "  Config written to $ConfigFile" -ForegroundColor Green
    } else {
        Write-Host "  Config already exists at $ConfigFile" -ForegroundColor Green
    }

    # Verify pixel-mcp runs
    try {
        $pmcpVersion = & $PixelMcpExe --version 2>&1
        Write-Host "  pixel-mcp version: $pmcpVersion" -ForegroundColor Green
    } catch {
        Write-Host "  WARNING: Could not verify pixel-mcp version" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  Skipped (--SkipPixelMcp)" -ForegroundColor DarkYellow
}

# --- Step 4: Create directory structure ---
Write-Host "`n[4/4] Creating project directories..." -ForegroundColor Yellow

$dirs = @(
    "art",
    "assets/sprites",
    "assets/ui",
    "assets/fonts",
    "scenes",
    "scenes/ui",
    "scripts",
    "scripts/autoload"
)

foreach ($dir in $dirs) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "  Exists:  $dir" -ForegroundColor DarkGray
    }
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "Next steps:"
Write-Host "  1. Run the game:  tools\godot_cli.ps1 run"
Write-Host "  2. Create art:    Use pixel-mcp MCP tools in Claude Code"
Write-Host "  3. Export assets:  tools\export_all.ps1"
