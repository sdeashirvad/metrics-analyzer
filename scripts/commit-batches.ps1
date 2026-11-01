# Commits metrics-analyzer changes in logical batches.
# Messages: HUSTLER | metrics-analyzer | <concise summary>
# Uses plain `git commit -m` only — no co-author trailers.

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$ScriptPath = $PSCommandPath
Set-Location $Root

function Assert-NoCoAuthor {
    foreach ($line in (Get-Content -LiteralPath $ScriptPath)) {
        if ($line -match '^\s*git\s+commit' -and $line -match '(?i)co-authored-by|co-author|-F\b|--file') {
            throw "Disallowed git commit line: $line"
        }
    }
    $template = git config --get commit.template 2>$null
    if ($template -and (Test-Path -LiteralPath $template)) {
        $tpl = Get-Content -LiteralPath $template -Raw
        if ($tpl -match '(?i)co-authored-by|co-author') {
            throw "commit.template contains a co-author line: $template"
        }
    }
    foreach ($var in @('GIT_EDITOR', 'EDITOR')) {
        $val = (Get-Item -Path "Env:$var" -ErrorAction SilentlyContinue).Value
        if ($val -and $val -match '(?i)co-author') {
            throw "Environment variable $var appears to reference co-author tooling."
        }
    }
}

function Invoke-MetricsCommit {
    param(
        [Parameter(Mandatory = $true)][string]$Summary,
        [Parameter(Mandatory = $true)][string[]]$Paths
    )
    $missing = @()
    foreach ($p in $Paths) {
        if (Test-Path -LiteralPath (Join-Path $Root $p)) { continue }
        $tracked = git ls-files -- $p 2>$null
        if ($tracked) { continue }
        if (git status --porcelain -- $p 2>$null) { continue }
        $missing += $p
    }
    if ($missing.Count -gt 0) {
        throw "Missing paths for batch '$Summary': $($missing -join ', ')"
    }
    git add -- @Paths
    $staged = git diff --cached --name-only -- @Paths
    if (-not $staged) {
        Write-Host "Skip (nothing staged): $Summary"
        return
    }
    $msg = "HUSTLER | metrics-analyzer | $Summary"
    git commit -m $msg -- @Paths
    Write-Host "Committed: $msg"
}

Assert-NoCoAuthor

$batches = @(
    @{
        Summary = 'document the live ui api and snowflake layout'
        Paths   = @('README.md', 'backend/README.md', 'snowflake/README.md')
    },
    @{
        Summary = 'batch commit script for the readme update'
        Paths   = @('scripts/commit-batches.ps1')
    }
)

foreach ($batch in $batches) {
    Invoke-MetricsCommit -Summary $batch.Summary -Paths $batch.Paths
}

Write-Host 'All batches finished.'
