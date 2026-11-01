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
        Summary = 'fallback pack tr routes and investigation job concurrency'
        Paths   = @(
            'backend/app/analysis/jobs.py',
            'backend/app/analysis/service.py',
            'backend/app/analysis/validator.py',
            'backend/app/db/analyses.py',
            'backend/app/db/connection.py',
            'backend/app/dq/router.py',
            'backend/app/main.py',
            'backend/app/fallback',
            'backend/app/fallback_assets',
            'backend/app/tr',
            'backend/tests/test_fallback.py',
            'backend/tests/test_investigation_jobs.py',
            'backend/tests/test_validator.py'
        )
    },
    @{
        Summary = 'remove frontend mock data and expand live http api'
        Paths   = @(
            'frontend/src/backend/contracts/types.ts',
            'frontend/src/backend/data',
            'frontend/src/backend/services',
            'frontend/src/hooks/useQuery.ts',
            'frontend/src/components/AppShell.tsx',
            'frontend/src/components/EnvironmentBar.tsx',
            'frontend/src/components/NotFoundPage.tsx',
            'frontend/src/components/ui/SectionState.tsx'
        )
    },
    @{
        Summary = 'investigation open flow loaders cache probes and eta'
        Paths   = @(
            'frontend/package.json',
            'frontend/package-lock.json',
            'frontend/src/state',
            'frontend/src/components/ui/CacheChip.tsx',
            'frontend/src/features/investigation/openFlow.ts',
            'frontend/src/features/investigation/openFlow.test.ts',
            'frontend/src/features/investigation/useDqInvestigation.ts',
            'frontend/src/features/investigation/LiveInvestigationLoader.tsx',
            'frontend/src/features/investigation/InvestigationPage.tsx',
            'frontend/src/features/investigation/DqInvestigationView.tsx',
            'frontend/src/features/investigation/AnalysisSimulation.tsx',
            'frontend/src/features/metric/summaryFlow.ts',
            'frontend/src/features/metric/summaryFlow.test.ts',
            'frontend/src/features/metric/MetricDetailPage.tsx',
            'frontend/src/features/glossary/GlossaryPage.tsx',
            'frontend/src/styles/base.css'
        )
    },
    @{
        Summary = 'uniform investigation actions on register triage and dashboard'
        Paths   = @(
            'frontend/src/features/investigation/access.ts',
            'frontend/src/features/investigation/access.test.ts',
            'frontend/src/features/investigation/AccessControls.tsx',
            'frontend/src/features/register/RegisterPage.tsx',
            'frontend/src/features/overview/TriageQueue.tsx',
            'frontend/src/features/dashboard/DashboardPage.tsx',
            'frontend/src/styles/components.css',
            'frontend/src/styles/pages.css',
            'frontend/.env.development'
        )
    },
    @{
        Summary = 'architecture journey play roles legend and vitest'
        Paths   = @(
            'frontend/src/features/architecture/journey.ts',
            'frontend/src/features/architecture/journey.test.ts',
            'frontend/src/features/architecture/model.ts',
            'frontend/src/features/architecture/ArchitectureDiagram.tsx',
            'frontend/src/features/architecture/ArchitecturePage.tsx',
            'frontend/src/styles/architecture.css'
        )
    },
    @{
        Summary = 'batch commit script for release batches'
        Paths   = @('scripts/commit-batches.ps1')
    }
)

foreach ($batch in $batches) {
    Invoke-MetricsCommit -Summary $batch.Summary -Paths $batch.Paths
}

Write-Host 'All batches finished.'
