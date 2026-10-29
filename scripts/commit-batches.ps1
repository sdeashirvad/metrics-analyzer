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
            '.gitignore', 'README.md', 'index.html', 'package.json', 'package-lock.json',
            'tsconfig.json', 'vite.config.ts', 'public/favicon.svg', 'src/vite-env.d.ts', 'src/main.tsx'
        )
    },
    @{
        Summary = 'dq fixture build and reconcile scripts'
        Paths   = @('scripts/build-dq-fixtures.py', 'scripts/reconcile-dq.py')
    },
    @{
        Summary = 'mock api contracts and tech-risk data'
        Paths   = @(
            'src/backend/contracts/types.ts', 'src/backend/contracts/routes.ts',
            'src/backend/services/index.ts', 'src/backend/services/errors.ts', 'src/backend/services/delay.ts',
            'src/backend/services/mockApi.ts', 'src/backend/services/dq.ts',
            'src/backend/data/metrics.ts', 'src/backend/data/trends.ts',
            'src/backend/data/investigations.ts', 'src/backend/data/orgContribution.ts',
            'src/domain/evaluateStatus.ts', 'src/domain/format.ts'
        )
    },
    @{
        Summary = 'workbook dq json fixtures'
        Paths   = @(
            'src/backend/data/dq/definitions.json', 'src/backend/data/dq/results.json',
            'src/backend/data/dq/results-by-desk.json', 'src/backend/data/dq/exceptions.json',
            'src/backend/data/dq/hierarchy.json', 'src/backend/data/dq/events.json',
            'src/backend/data/dq/commentary.json', 'src/backend/data/dq/summary.json'
        )
    },
    @{
        Summary = 'router shell and url query hooks'
        Paths   = @(
            'src/App.tsx', 'src/hooks/useQuery.ts', 'src/hooks/useUrlState.ts', 'src/hooks/useOrigin.ts',
            'src/components/AppShell.tsx', 'src/components/EnvironmentBar.tsx', 'src/components/NotFoundPage.tsx'
        )
    },
    @{
        Summary = 'design tokens and layout styles'
        Paths   = @(
            'src/styles/tokens.css', 'src/styles/base.css', 'src/styles/components.css',
            'src/styles/pages.css', 'src/styles/architecture.css'
        )
    },
    @{
        Summary = 'shared ui primitives and charts'
        Paths   = @(
            'src/components/StatusBadge.tsx', 'src/components/TrendChart.tsx',
            'src/components/ThresholdScale.tsx', 'src/components/HotspotChart.tsx',
            'src/components/ui/PageHeader.tsx', 'src/components/ui/Breadcrumbs.tsx',
            'src/components/ui/SegmentedControl.tsx', 'src/components/ui/Tabs.tsx',
            'src/components/ui/SectionState.tsx', 'src/components/ui/ProvenanceChip.tsx',
            'src/components/ui/DataTable.tsx', 'src/components/ui/Pager.tsx',
            'src/components/ui/FilterToolbar.tsx', 'src/components/ui/Disclosure.tsx',
            'src/components/ui/Sparkline.tsx', 'src/components/ui/StatusStrip.tsx',
            'src/components/ui/BookTile.tsx', 'src/components/ui/AttentionRow.tsx',
            'src/components/ui/Select.tsx'
        )
    },
    @{
        Summary = 'dashboard metric health books'
        Paths   = @('src/features/dashboard/DashboardPage.tsx')
    },
    @{
        Summary = 'triage queue movement and trend explorer'
        Paths   = @(
            'src/features/overview/triage.ts', 'src/features/overview/TriageQueue.tsx',
            'src/features/overview/MovementRail.tsx', 'src/features/overview/TrendExplorer.tsx',
            'src/features/overview/OverviewPage.tsx'
        )
    },
    @{
        Summary = 'metric register filters and exports'
        Paths   = @('src/features/register/RegisterPage.tsx')
    },
    @{
        Summary = 'metric detail and dq evidence tabs'
        Paths   = @('src/features/metric/MetricDetailPage.tsx', 'src/features/metric/DqEvidence.tsx')
    },
    @{
        Summary = 'investigation views and analysis simulation'
        Paths   = @(
            'src/features/investigation/InvestigationPage.tsx', 'src/features/investigation/InvestigationChrome.tsx',
            'src/features/investigation/DqInvestigationView.tsx', 'src/features/investigation/AnalysisSimulation.tsx'
        )
    },
    @{
        Summary = 'architecture diagram and walkthrough'
        Paths   = @(
            'src/features/architecture/model.ts', 'src/features/architecture/ArchitecturePage.tsx',
            'src/features/architecture/ArchitectureDiagram.tsx', 'src/features/architecture/DetailPanel.tsx',
            'src/features/architecture/Walkthrough.tsx'
        )
    },
    @{
        Summary = 'glossary and conventions page'
        Paths   = @('src/features/glossary/GlossaryPage.tsx')
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
