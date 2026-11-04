export type SkeletonShape = 'lines' | 'kpis' | 'list' | 'bars' | 'chart' | 'table' | 'preview' | 'investigation' | 'stack-bar'

function Line({ w = '100%', h = 12 }: { w?: string; h?: number }) {
  return <span className="sk" style={{ width: w, height: h }} />
}

function Kpis({ count = 4 }: { count?: number }) {
  return (
    <div className="grid g4 sk-kpis">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="sk-tile">
          <Line w="46%" h={10} />
          <Line w="38%" h={26} />
          <Line w="30%" h={10} />
        </div>
      ))}
    </div>
  )
}

function ListRows({ rows }: { rows: number }) {
  return (
    <div className="sk-list">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="sk-row">
          <span className="sk-col">
            <Line w={`${52 - (index % 3) * 8}%`} h={12} />
            <Line w="22%" h={10} />
          </span>
          <Line w="88px" h={18} />
          <Line w="20px" h={12} />
        </div>
      ))}
    </div>
  )
}

function Bars({ rows }: { rows: number }) {
  return (
    <div className="sk-list">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="sk-bar">
          <Line w="70%" h={10} />
          <span className="sk" style={{ width: `${86 - index * 11}%`, height: 12 }} />
          <Line w="56px" h={10} />
        </div>
      ))}
    </div>
  )
}

function Table({ rows }: { rows: number }) {
  return (
    <div className="sk-table">
      <div className="sk-thead">
        <Line w="18%" h={10} />
        <Line w="12%" h={10} />
        <Line w="12%" h={10} />
        <Line w="12%" h={10} />
      </div>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="sk-trow">
          <Line w="18%" h={12} />
          <Line w="10%" h={12} />
          <Line w="14%" h={12} />
          <Line w="10%" h={12} />
        </div>
      ))}
    </div>
  )
}

function Lines({ rows }: { rows: number }) {
  return (
    <div className="sk-lines">
      {Array.from({ length: rows }, (_, index) => (
        <Line key={index} w={index === rows - 1 ? '62%' : `${96 - (index % 2) * 7}%`} />
      ))}
    </div>
  )
}

function Body({ shape, rows }: { shape: SkeletonShape; rows?: number }) {
  switch (shape) {
    case 'kpis':
      return <Kpis count={rows} />
    case 'list':
      return <ListRows rows={rows ?? 3} />
    case 'bars':
      return <Bars rows={rows ?? 3} />
    case 'chart':
      return <span className="sk sk-chart" />
    case 'table':
      return <Table rows={rows ?? 3} />
    case 'stack-bar':
      return (
        <div className="sk-lines">
          <Line w="40%" h={10} />
          <span className="sk" style={{ width: '100%', height: 18 }} />
          <ListRows rows={rows ?? 3} />
        </div>
      )
    case 'preview':
      return (
        <div className="sk-stack">
          <div className="sk-pair">
            <Lines rows={2} />
            <Lines rows={2} />
          </div>
          <div className="sk-preview-kpis">
            <span className="sk sk-block" />
            <span className="sk sk-block" />
            <span className="sk sk-block" />
          </div>
          <Lines rows={3} />
          <ListRows rows={4} />
          <span className="sk sk-chart" />
        </div>
      )
    case 'investigation':
      return (
        <div className="sk-stack">
          <div className="sk-card">
            <Line w="28%" h={14} />
            <Lines rows={4} />
          </div>
          <Kpis />
          <div className="sk-card">
            <Line w="22%" h={14} />
            <ListRows rows={5} />
          </div>
        </div>
      )
    default:
      return <Lines rows={rows ?? 3} />
  }
}

/**
 * Placeholder shaped like the content it stands in for, so the page does not jump when data lands.
 * It fades in after a short delay, so cached or fast responses never flash a placeholder.
 */
export function Skeleton({ shape = 'lines', rows, label = 'Loading' }: { shape?: SkeletonShape; rows?: number; label?: string }) {
  return (
    <div className={`sk-wrap sk-${shape}`} role="status">
      <span className="sr-only">{label}…</span>
      <div aria-hidden="true">
        <Body shape={shape} rows={rows} />
      </div>
    </div>
  )
}
