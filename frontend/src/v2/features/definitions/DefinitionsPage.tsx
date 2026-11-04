import { useEffect } from 'react'
import { getDefinitions } from '../../api/portfolio'
import { QueryPanel } from '../../components/present'
import { PageHeader } from '../../components/ui/PageHeader'
import { useApiQuery } from '../../hooks/useApiQuery'

const STATUS_LABEL: Record<string, string> = {
  provisional: 'Provisional',
  assumption: 'Assumption',
  source: 'Source observation',
  documented_rule: 'Documented rule',
  not_available: 'Not available',
}

/** Display order of the groups, and one line on what each label promises. */
const GROUPS: Array<{ status: string; note: string }> = [
  { status: 'provisional', note: 'Working definitions that the business has not confirmed. Treat results that depend on them as provisional.' },
  { status: 'assumption', note: 'Stated assumptions used to build or read the numbers.' },
  { status: 'source', note: 'What the source data records, without interpretation.' },
  { status: 'documented_rule', note: 'Rules that come from documented sources.' },
  { status: 'not_available', note: 'Things the data cannot answer today.' },
]

export function humanStatus(status: string): string {
  return STATUS_LABEL[status] ?? status.replaceAll('_', ' ')
}

export function groupDefinitions<T extends { status: string }>(items: T[]): Array<{ status: string; label: string; note: string; items: T[] }> {
  const known = GROUPS.map((group) => ({
    status: group.status,
    label: humanStatus(group.status),
    note: group.note,
    items: items.filter((item) => item.status === group.status),
  }))
  const other = items.filter((item) => !GROUPS.some((group) => group.status === item.status))
  const groups = other.length ? [...known, { status: 'other', label: 'Other', note: 'Labels without a standard group.', items: other }] : known
  return groups.filter((group) => group.items.length > 0)
}

export function DefinitionsPage() {
  const query = useApiQuery('definitions', 'all', getDefinitions)
  useEffect(() => {
    if (query.status !== 'success') return
    const id = window.location.hash.replace('#', '')
    if (id) document.getElementById(id)?.scrollIntoView()
  }, [query.status])

  return (
    <div className="page">
      <PageHeader
        eyebrow="Definitions"
        title="Definitions & conventions"
        subtitle="Provisional rates, denominator variants, and derived metrics stay visible and are labelled from the API."
      />
      <QueryPanel query={query}>
        {(data) => {
          const groups = groupDefinitions(data.definitions)
          return (
            <div className="definitions-layout">
              <nav className="card definitions-index" aria-label="Definitions index">
                <h2 className="sec-label">On this page</h2>
                <ul className="list">
                  {data.classification && (
                    <li>
                      <a href="#classification">Provisional classification</a>
                    </li>
                  )}
                  {groups.map((group) => (
                    <li key={group.status}>
                      <a href={`#group-${group.status}`}>
                        {group.label} <span className="fine num">{group.items.length}</span>
                      </a>
                    </li>
                  ))}
                  {data.conventions.length > 0 && (
                    <li>
                      <a href="#conventions">Conventions</a>
                    </li>
                  )}
                </ul>
              </nav>
              <div className="stack">
                {data.classification && (
                  <article className="card" id="classification">
                    <h2>Provisional classification</h2>
                    <p>{data.classification.rate.note}</p>
                    <p className="fine">{data.classification.applicationGreen.note}</p>
                  </article>
                )}
                {groups.map((group) => (
                  <section key={group.status} id={`group-${group.status}`} aria-labelledby={`group-title-${group.status}`} className="stack">
                    <div>
                      <h2 id={`group-title-${group.status}`}>{group.label}</h2>
                      <p className="fine">{group.note}</p>
                    </div>
                    {group.items.map((definition) => (
                      <article key={definition.id} id={definition.id} className="card">
                        <div className="card-head">
                          <h3>{definition.name}</h3>
                          <span className="etag">{definition.id}</span>
                        </div>
                        <p>{definition.definition}</p>
                        <p className="fine">{definition.basis}</p>
                        {definition.appliesTo.length > 0 && <p className="fine">Applies to {definition.appliesTo.join(', ')}</p>}
                        {definition.caveats.length > 0 && (
                          <ul className="list">
                            {definition.caveats.map((caveat) => (
                              <li key={caveat}>{caveat}</li>
                            ))}
                          </ul>
                        )}
                      </article>
                    ))}
                  </section>
                ))}
                <section className="card" id="conventions">
                  <h2>Conventions</h2>
                  <ul className="list">
                    {data.conventions.map((item) => (
                      <li key={item.id} id={item.id}>
                        {item.text}
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
            </div>
          )
        }}
      </QueryPanel>
    </div>
  )
}
