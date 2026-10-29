import type { ArchNode } from './model'
import { statusLabel } from './model'

export function DetailPanel({ node }: { node: ArchNode }) {
  return (
    <section className="arch-detail" aria-label={`${node.label} details`}>
      <p className={`arch-status is-${node.status}`}>{statusLabel(node.status)}</p>
      <h2>{node.label}</h2>
      <p>{node.purpose}</p>
      <h3>Inputs</h3>
      <ul>
        {node.inputs.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <h3>Outputs</h3>
      <ul>
        {node.outputs.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <h3>Responsibilities</h3>
      <ul>
        {node.responsibilities.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}
