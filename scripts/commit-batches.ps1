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
        if (-not (Test-Path -LiteralPath (Join-Path $Root $p))) {
            $missing += $p
        }
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
        Summary = 'snowflake dq tables seeds and smoke test'
        Paths   = @('snowflake', 'scripts/snowflake_smoke_test.py')
    },
    @{
        Summary = 'fastapi dq api docker and cortex cache'
        Paths   = @(
            '.gitignore',
            'backend/README.md', 'backend/.dockerignore', 'backend/.env.example',
            'backend/Dockerfile', 'backend/docker-compose.yml', 'backend/requirements.txt', 'backend/pytest.ini',
            'backend/app', 'backend/tests'
        )
    },
    @{
        Summary = 'wire data quality screens to the api'
        Paths   = @(
            'frontend/.env.development',
            'frontend/src/backend/contracts/types.ts',
            'frontend/src/backend/services/errors.ts',
            'frontend/src/backend/services/index.ts',
            'frontend/src/backend/services/httpApi.ts',
            'frontend/src/features/metric/MetricDetailPage.tsx',
            'frontend/src/features/investigation/AnalysisSimulation.tsx',
            'frontend/src/features/investigation/DqInvestigationView.tsx',
            'frontend/src/features/investigation/InvestigationPage.tsx'
        )
    },
    @{
        Summary = 'batch commit script'
        Paths   = @('scripts/commit-batches.ps1')
    }
)

foreach ($batch in $batches) {
    Invoke-MetricsCommit -Summary $batch.Summary -Paths $batch.Paths
}

Write-Host 'All batches finished.'
