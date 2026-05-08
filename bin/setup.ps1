#requires -Version 5.1
<#
.SYNOPSIS
  Multi-Agent Toolkit - Windows setup (venv, deps, validators, tests, Claude Code plugin registration).

.DESCRIPTION
  PowerShell equivalent of bin/setup. Registers this repo as a global Claude Code plugin and copies agent definitions.

.PARAMETER Check
  Check prerequisites and CLI tools only (no venv/pip/validators/tests/plugin registration).

.EXAMPLE
  .\bin\setup.ps1
.EXAMPLE
  .\bin\setup.ps1 -Check
.EXAMPLE
  .\bin\setup.ps1 --check
#>
param(
    [switch]$Check
)

if ($args -contains '--check') {
    $Check = $true
}

$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

$script:Errors = 0
$script:Warnings = 0

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [pass] $Message" -ForegroundColor Green
}

function Write-WarnLine {
    param([string]$Message)
    Write-Host "  ! $Message" -ForegroundColor Yellow
    $script:Warnings++
}

function Write-FailLine {
    param([string]$Message)
    Write-Host "  [fail] $Message" -ForegroundColor Red
    $script:Errors++
}

function Write-InfoLine {
    param([string]$Message)
    Write-Host "  -> $Message" -ForegroundColor Blue
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-CliVersionOutput {
    param([string]$CliName)
    try {
        & $CliName --version 2>&1 | ForEach-Object { "$_" }
    }
    catch {
        @()
    }
}

function Test-CliWorks {
    param([string]$CliName)
    $output = (Invoke-CliVersionOutput -CliName $CliName) -join "`n"
    if ($output -match 'mise.*not currently active' -or
        $output -match 'mise ERROR' -or
        $output -match 'No version is set for shim') {
        return $false
    }
    $null = & $CliName --version 2>&1
    return ($LASTEXITCODE -eq 0)
}

function Test-CliAuthClaude {
    $homeClaude = Join-Path $env:USERPROFILE '.claude'
    $xdg = Join-Path $env:USERPROFILE '.config\claude'
    return ((Test-Path (Join-Path $homeClaude 'config.json')) -or (Test-Path (Join-Path $xdg 'config.json')))
}

function Test-CliAuthCodex {
    if ($env:OPENAI_API_KEY) { return $true }
    $p = Join-Path $env:USERPROFILE '.codex\config.json'
    return (Test-Path $p)
}

function Test-CliAuthGemini {
    if ($env:GOOGLE_API_KEY) { return $true }
    $p = Join-Path $env:USERPROFILE '.config\gemini\config.json'
    return (Test-Path $p)
}

function Test-Python310Plus {
    param([string]$PythonExe)
    try {
        $verLine = & $PythonExe --version 2>&1
        $verLine = "$verLine"
        if ($verLine -notmatch 'Python\s+(\d+)\.(\d+)') {
            return $false
        }
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -gt 3) { return $true }
        if ($major -eq 3 -and $minor -ge 10) { return $true }
        return $false
    }
    catch {
        return $false
    }
}

function Copy-AgentDefinitions {
    param(
        [string]$RepoRootPath,
        [string]$DestDir
    )
    $src = Join-Path $RepoRootPath 'agents'
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    Get-ChildItem -LiteralPath $src -Filter '*.md' -File | Where-Object { $_.Name -ne 'README.md' } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $DestDir $_.Name) -Force
    }
}

# --- Banner ---
Write-Host "======================================================================"
Write-Host "  Multi-Agent Toolkit - Setup (Windows)"
Write-Host "======================================================================"

# --- Python ---
Write-Header "Python Environment"

if (-not (Test-CommandExists 'python')) {
    Write-FailLine "Python not found on PATH"
    Write-InfoLine "Install: https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "======================================================================"
    Write-Host ("Setup incomplete. {0} error(s), {1} warning(s)." -f $script:Errors, $script:Warnings) -ForegroundColor Red
    exit 1
}

$pyVersionLine = (& python --version 2>&1 | ForEach-Object { "$_" }) -join ''
Write-Success "Python: $pyVersionLine"

if (-not (Test-Python310Plus -PythonExe 'python')) {
    Write-FailLine "Python 3.10 or newer is required"
    Write-InfoLine "Install: https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "======================================================================"
    Write-Host ("Setup incomplete. {0} error(s), {1} warning(s)." -f $script:Errors, $script:Warnings) -ForegroundColor Red
    exit 1
}

$venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not $Check) {
    Write-Header "Virtual Environment"
    $venvDir = Join-Path $RepoRoot '.venv'
    if (Test-Path $venvDir) {
        Write-Success "Virtual environment exists at .venv\"
    }
    else {
        Write-InfoLine "Creating virtual environment..."
        & python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Write-FailLine "python -m venv failed"
            exit 1
        }
        Write-Success "Created .venv\"
    }

    Write-Header "Python Dependencies"
    $reqFile = Join-Path $RepoRoot 'requirements-dev.txt'
    if (Test-Path $reqFile) {
        Write-InfoLine "Installing from requirements-dev.txt (hash-checked)..."
        & $venvPython -m pip install --require-hashes -r $reqFile
        if ($LASTEXITCODE -ne 0) {
            Write-FailLine "pip install failed"
        }
        else {
            Write-Success "Installed Python dependencies"
        }
    }
    else {
        Write-WarnLine "requirements-dev.txt not found"
    }
}

# --- CLI tools ---
Write-Header "CLI Tools (for mat_runtime)"
Write-InfoLine "These are optional but required to use the runtime adapter."
Write-Host ""

if ((Test-CommandExists 'claude') -and (Test-CliWorks -CliName 'claude')) {
    $cv = (Invoke-CliVersionOutput -CliName 'claude' | Select-Object -First 1)
    if (-not $cv) { $cv = 'installed' }
    if (Test-CliAuthClaude) {
        Write-Success "claude: $cv (authenticated)"
    }
    else {
        Write-WarnLine "claude: $cv (not authenticated)"
        Write-InfoLine "Auth: claude login"
    }
}
elseif (Test-CommandExists 'claude') {
    Write-WarnLine "claude: shim exists but not activated (mise)"
    Write-InfoLine "Fix: mise use claude@latest"
}
else {
    Write-WarnLine "claude CLI not found (Claude Code)"
    Write-InfoLine "Install: npm install -g @anthropic-ai/claude-code"
    Write-InfoLine "    or:  winget / brew install per Claude Code docs"
    Write-InfoLine " Docs: https://docs.anthropic.com/en/docs/claude-code"
}

if ((Test-CommandExists 'codex') -and (Test-CliWorks -CliName 'codex')) {
    $cv = (Invoke-CliVersionOutput -CliName 'codex' | Select-Object -First 1)
    if (-not $cv) { $cv = 'installed' }
    if (Test-CliAuthCodex) {
        Write-Success "codex: $cv (authenticated)"
    }
    else {
        Write-WarnLine "codex: $cv (not authenticated)"
        Write-InfoLine "Auth: codex auth"
    }
}
elseif (Test-CommandExists 'codex') {
    Write-WarnLine "codex: shim exists but not activated (mise)"
    Write-InfoLine "Fix: mise install  (uses .mise.toml)"
    Write-InfoLine " or: npm install -g @openai/codex"
}
else {
    Write-WarnLine "codex CLI not found (OpenAI Codex)"
    Write-InfoLine "Install: mise install  (uses .mise.toml)"
    Write-InfoLine "    or:  npm install -g @openai/codex"
    Write-InfoLine " Docs: https://github.com/openai/codex-cli"
}

if ((Test-CommandExists 'gemini') -and (Test-CliWorks -CliName 'gemini')) {
    $gv = (Invoke-CliVersionOutput -CliName 'gemini' | Select-Object -First 1)
    if (-not $gv) { $gv = 'installed' }
    if (Test-CliAuthGemini) {
        Write-Success "gemini: $gv (authenticated)"
    }
    else {
        Write-WarnLine "gemini: $gv (not authenticated)"
        Write-InfoLine "Auth: gemini auth login"
    }
}
elseif (Test-CommandExists 'gemini') {
    Write-WarnLine "gemini: shim exists but not activated (mise)"
    Write-InfoLine "Fix: mise use gemini@latest"
}
else {
    Write-WarnLine "gemini CLI not found (Google Gemini)"
    Write-InfoLine "Install: npm install -g @google/gemini-cli"
    Write-InfoLine " Docs: https://github.com/google-gemini/gemini-cli"
}

if (-not $Check) {
    Write-Header "Schema Validators"
    Set-Location $RepoRoot
    $validators = Get-ChildItem -Path (Join-Path $RepoRoot 'scripts') -Filter 'validate_*.py' -File | Sort-Object Name
    foreach ($v in $validators) {
        $short = $v.BaseName
        $vout = & $venvPython $v.FullName 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success $short
        }
        else {
            Write-FailLine "$short failed"
            $vout | Write-Host
        }
    }

    Write-Header "Unit Tests"
    Set-Location $RepoRoot
    $testsRoot = Join-Path $RepoRoot 'mat_runtime\tests'
    $testout = & $venvPython -m pytest $testsRoot -v 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "mat_runtime tests passed"
    }
    else {
        Write-FailLine "mat_runtime tests failed"
        $testout | Write-Host
    }

    Write-Header "Claude Code plugin + agents"
    try {
        $pluginsDir = Join-Path $env:USERPROFILE '.claude\plugins'
        $pluginsJson = Join-Path $pluginsDir 'installed_plugins.json'
        $mergeScript = Join-Path $RepoRoot 'scripts\merge_installed_plugins_json.py'
        & $venvPython $mergeScript --plugins-json $pluginsJson --repo-root $RepoRoot
        if ($LASTEXITCODE -ne 0) {
            throw "merge_installed_plugins_json.py exited $LASTEXITCODE"
        }
        Write-Success ("Registered plugin at {0}" -f $pluginsJson)
    }
    catch {
        Write-FailLine ("Could not update installed_plugins.json: {0}" -f $_)
    }

    try {
        $agentsDest = Join-Path $env:USERPROFILE '.claude\agents'
        Copy-AgentDefinitions -RepoRootPath $RepoRoot -DestDir $agentsDest
        Write-Success ("Copied agent definitions to {0}" -f $agentsDest)
    }
    catch {
        Write-FailLine ("Could not copy agents: {0}" -f $_)
    }
}

# --- Summary ---
Write-Host ""
Write-Host "======================================================================"

if ($script:Errors -eq 0 -and $script:Warnings -eq 0) {
    Write-Host "Setup complete! All checks passed." -ForegroundColor Green
}
elseif ($script:Errors -eq 0) {
    Write-Host ("Setup complete with {0} warning(s). CLI tools are optional - install them to use mat_runtime." -f $script:Warnings) -ForegroundColor Yellow
}
else {
    Write-Host ("Setup incomplete. {0} error(s), {1} warning(s)." -f $script:Errors, $script:Warnings) -ForegroundColor Red
}

Write-Host ""
Write-Host "Next steps:"
Write-Host ("  {0}\Scripts\Activate.ps1" -f (Join-Path $RepoRoot '.venv'))
Write-Host "  python -m mat_runtime list-agents"
if (-not $Check) {
    Write-Host "Restart Claude Code so the plugin and copied agents are picked up."
}
Write-Host ""

if ($script:Errors -gt 0) {
    exit 1
}
