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
    foreach ($p in $Paths) {
        if ($p -like 'frontend/*') {
            $old = $p.Substring(9)
            git cat-file -e "HEAD:${old}" 2>$null
            if ($LASTEXITCODE -eq 0) {
                git add -u -- $old
            }
        }
    }
    $staged = git diff --cached --name-only
    if (-not $staged) {
        Write-Host "Skip (nothing staged): $Summary"
        return
    }
    $msg = "HUSTLER | metrics-analyzer | $Summary"
    git commit -m $msg
    Write-Host "Committed: $msg"
}

Assert-NoCoAuthor

$batches = @(
    @{
        Summary = 'vite react app scaffold'
        Paths   = @(
            '.gitignore', 'README.md', 'backend/README.md',
            'frontend/index.html', 'frontend/package.json', 'frontend/package-lock.json',
            'frontend/tsconfig.json', 'frontend/vite.config.ts', 'frontend/public/favicon.svg',
            'frontend/src/vite-env.d.ts', 'frontend/src/main.tsx'
        )
    },
    @{
        Summary = 'dq fixture build and reconcile scripts'
        Paths   = @('scripts/build-dq-fixtures.py', 'scripts/reconcile-dq.py')
    },
    @{
        Summary = 'mock api contracts and tech-risk data'
        Paths   = @(
            'frontend/src/backend/contracts/types.ts', 'frontend/src/backend/contracts/routes.ts',
            'frontend/src/backend/services/index.ts', 'frontend/src/backend/services/errors.ts', 'frontend/src/backend/services/delay.ts',
            'frontend/src/backend/services/mockApi.ts', 'frontend/src/backend/services/dq.ts',
            'frontend/src/backend/data/metrics.ts', 'frontend/src/backend/data/trends.ts',
            'frontend/src/backend/data/investigations.ts', 'frontend/src/backend/data/orgContribution.ts',
            'frontend/src/domain/evaluateStatus.ts', 'frontend/src/domain/format.ts'
        )
    },
    @{
        Summary = 'workbook dq json fixtures'
        Paths   = @(
            'frontend/src/backend/data/dq/definitions.json', 'frontend/src/backend/data/dq/results.json',
            'frontend/src/backend/data/dq/results-by-desk.json', 'frontend/src/backend/data/dq/exceptions.json',
            'frontend/src/backend/data/dq/hierarchy.json', 'frontend/src/backend/data/dq/events.json',
            'frontend/src/backend/data/dq/commentary.json', 'frontend/src/backend/data/dq/summary.json'
        )
    },
    @{
        Summary = 'router shell and url query hooks'
        Paths   = @(
            'frontend/src/App.tsx', 'frontend/src/hooks/useQuery.ts', 'frontend/src/hooks/useUrlState.ts', 'frontend/src/hooks/useOrigin.ts',
            'frontend/src/components/AppShell.tsx', 'frontend/src/components/EnvironmentBar.tsx', 'frontend/src/components/NotFoundPage.tsx'
        )
    },
    @{
        Summary = 'design tokens and layout styles'
        Paths   = @(
            'frontend/src/styles/tokens.css', 'frontend/src/styles/base.css', 'frontend/src/styles/components.css',
            'frontend/src/styles/pages.css', 'frontend/src/styles/architecture.css'
        )
    },
    @{
        Summary = 'shared ui primitives and charts'
        Paths   = @(
            'frontend/src/components/StatusBadge.tsx', 'frontend/src/components/TrendChart.tsx',
            'frontend/src/components/ThresholdScale.tsx', 'frontend/src/components/HotspotChart.tsx',
            'frontend/src/components/ui/PageHeader.tsx', 'frontend/src/components/ui/Breadcrumbs.tsx',
            'frontend/src/components/ui/SegmentedControl.tsx', 'frontend/src/components/ui/Tabs.tsx',
            'frontend/src/components/ui/SectionState.tsx', 'frontend/src/components/ui/ProvenanceChip.tsx',
            'frontend/src/components/ui/DataTable.tsx', 'frontend/src/components/ui/Pager.tsx',
            'frontend/src/components/ui/FilterToolbar.tsx', 'frontend/src/components/ui/Disclosure.tsx',
            'frontend/src/components/ui/Sparkline.tsx', 'frontend/src/components/ui/StatusStrip.tsx',
            'frontend/src/components/ui/BookTile.tsx', 'frontend/src/components/ui/AttentionRow.tsx',
            'frontend/src/components/ui/Select.tsx'
        )
    },
    @{
        Summary = 'dashboard metric health books'
        Paths   = @('frontend/src/features/dashboard/DashboardPage.tsx')
    },
    @{
        Summary = 'triage queue movement and trend explorer'
        Paths   = @(
            'frontend/src/features/overview/triage.ts', 'frontend/src/features/overview/TriageQueue.tsx',
            'frontend/src/features/overview/MovementRail.tsx', 'frontend/src/features/overview/TrendExplorer.tsx',
            'frontend/src/features/overview/OverviewPage.tsx'
        )
    },
    @{
        Summary = 'metric register filters and exports'
        Paths   = @('frontend/src/features/register/RegisterPage.tsx')
    },
    @{
        Summary = 'metric detail and dq evidence tabs'
        Paths   = @('frontend/src/features/metric/MetricDetailPage.tsx', 'frontend/src/features/metric/DqEvidence.tsx')
    },
    @{
        Summary = 'investigation views and analysis simulation'
        Paths   = @(
            'frontend/src/features/investigation/InvestigationPage.tsx', 'frontend/src/features/investigation/InvestigationChrome.tsx',
            'frontend/src/features/investigation/DqInvestigationView.tsx', 'frontend/src/features/investigation/AnalysisSimulation.tsx'
        )
    },
    @{
        Summary = 'architecture diagram and walkthrough'
        Paths   = @(
            'frontend/src/features/architecture/model.ts', 'frontend/src/features/architecture/ArchitecturePage.tsx',
            'frontend/src/features/architecture/ArchitectureDiagram.tsx', 'frontend/src/features/architecture/DetailPanel.tsx',
            'frontend/src/features/architecture/Walkthrough.tsx'
        )
    },
    @{
        Summary = 'glossary and conventions page'
        Paths   = @('frontend/src/features/glossary/GlossaryPage.tsx')
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
