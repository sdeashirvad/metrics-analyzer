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
        Summary = 'portfolio runtime with offline snapshots and gate'
        Paths   = @('backend/app/portfolio', 'backend/app/common', 'backend/app/main.py')
    },
    @{
        Summary = 'agent registry context builder and prepared investigations'
        Paths   = @('backend/app/agents')
    },
    @{
        Summary = 'packaged offline snapshots and investigation bundles'
        Paths   = @('backend/app/fallback_assets/v2')
    },
    @{
        Summary = 'backend export and outage walk scripts'
        Paths   = @('backend/scripts')
    },
    @{
        Summary = 'backend v2 tests'
        Paths   = @('backend/tests/v2')
    },
    @{
        Summary = 'frontend bootstrap and production api base'
        Paths   = @('frontend/src/bootstrap', 'frontend/src/legacy-entry.tsx', 'frontend/src/App.tsx', 'frontend/src/main.tsx', 'frontend/.env.production')
    },
    @{
        Summary = 'v2 loading skeletons stale panels and centred content'
        Paths   = @(
            'frontend/src/v2/hooks/useApiQuery.ts'
            'frontend/src/v2/components/Skeleton.tsx'
            'frontend/src/v2/components/present.tsx'
            'frontend/src/v2/shell/V2Shell.tsx'
            'frontend/src/v2/styles/components.css'
        )
    },
    @{
        Summary = 'v2 agent answer-first rendering for analysis and data explorer'
        Paths   = @(
            'frontend/src/v2/features/agent/MessageViews.tsx'
            'frontend/src/v2/features/agent/MessageViews.test.tsx'
        )
    },
    @{
        Summary = 'v2 agent workspace layout waiting state and preview continuity'
        Paths   = @(
            'frontend/src/v2/features/agent/AgentPages.tsx'
            'frontend/src/v2/components/ui/AskAgentLink.tsx'
            'frontend/src/v2/features/register/PreviewModal.tsx'
            'frontend/src/v2/styles/pages.css'
        )
    },
    @{
        Summary = 'v2 dashboard movement attention rows and shaped panel loading'
        Paths   = @(
            'frontend/src/v2/features/dashboard/DashboardPage.tsx'
            'frontend/src/v2/features/dashboard/DashboardPage.css'
        )
    },
    @{
        Summary = 'v2 register investigation and metric pages with skeleton keep'
        Paths   = @(
            'frontend/src/v2/features/register/RegisterPage.tsx'
            'frontend/src/v2/features/investigation/MetricInvestigationPage.tsx'
            'frontend/src/v2/features/investigation/ApplicationInvestigationPage.tsx'
            'frontend/src/v2/features/metric/MetricSummaryPage.tsx'
            'frontend/src/v2/features/metric/MetricTrendCard.tsx'
            'frontend/src/v2/features/definitions/DefinitionsPage.tsx'
        )
    },
    @{
        Summary = 'v2 architecture copy for browser conversation storage'
        Paths   = @('frontend/src/v2/features/architecture/model.ts')
    },
    @{
        Summary = 'v2 scope bar always uses business organisation tree'
        Paths   = @(
            'frontend/src/v2/components/ScopeBar.tsx'
            'frontend/src/v2/hooks/useScopeFilters.ts'
            'frontend/src/v2/api/query.ts'
            'frontend/src/v2/api/query.test.ts'
            'frontend/src/v2/scopePath.ts'
        )
    },
    @{
        Summary = 'snowflake mock data setup scripts'
        Paths   = @('snowflake/mock_data_setup')
    },
    @{
        Summary = 'docs and v2 resources'
        Paths   = @('docs', 'resources')
    },
    @{
        Summary = 'ignore tsbuildinfo and add deploy batch script'
        Paths   = @('.gitignore', 'scripts/commit-batches.ps1')
    }
)

foreach ($batch in $batches) {
    Invoke-MetricsCommit -Summary $batch.Summary -Paths $batch.Paths
}

Write-Host 'All batches finished.'
