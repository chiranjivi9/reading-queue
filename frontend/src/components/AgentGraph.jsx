import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

mermaid.initialize({ startOnLoad: false, theme: 'neutral', flowchart: { curve: 'basis' } })

// Build a Mermaid flowchart from the trace.
// Only shows agent_start + tool_call steps — reasoning text stays in the
// expandable trace panel. This keeps the graph tight and readable.
function buildChart(trace) {
  const steps = (trace ?? []).filter(
    s => s.type === 'agent_start' || s.type === 'tool_call'
  )
  if (steps.length === 0) return null

  const lines = [
    'graph TD',
    '  classDef discovery fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f,rx:4',
    '  classDef digest    fill:#dcfce7,stroke:#22c55e,color:#14532d,rx:4',
    '  classDef done      fill:#fef9c3,stroke:#ca8a04,color:#713f12,rx:4',
    '  classDef start     fill:#f3f4f6,stroke:#9ca3af,color:#374151,rx:4',
  ]

  const ids = []

  steps.forEach((step, i) => {
    const id = `N${i}`

    if (step.type === 'agent_start') {
      const label = step.agent === 'discovery' ? 'Discovery Agent' : 'Digest Agent'
      lines.push(`  ${id}(["${label}"]):::start`)
      ids.push({ id, cls: 'start' })
      return
    }

    // tool_call
    let label
    switch (step.tool) {
      case 'web_search':
        label = `search: "${(step.input?.query ?? '').slice(0, 38)}"`
        break
      case 'report_findings':
        label = step.summary ?? 'report findings'
        break
      case 'save_digest':
        label = 'save digest'
        break
      case 'list_articles':
        label = step.summary ?? 'list articles'
        break
      default:
        label = step.tool ?? 'tool'
    }

    const cls =
      step.tool === 'save_digest' || step.tool === 'report_findings'
        ? 'done'
        : step.agent ?? 'discovery'

    // Escape quotes and strip newlines for Mermaid label safety
    const safe = label.replace(/"/g, "'").replace(/\n/g, ' ')
    lines.push(`  ${id}["${safe}"]:::${cls}`)
    ids.push({ id, cls })
  })

  // Sequential edges
  for (let i = 1; i < ids.length; i++) {
    lines.push(`  ${ids[i - 1].id} --> ${ids[i].id}`)
  }

  return lines.join('\n')
}

let counter = 0

export default function AgentGraph({ trace }) {
  const containerRef = useRef(null)
  const graphId = useRef(`ag-${++counter}`)

  useEffect(() => {
    const chart = buildChart(trace)
    if (!chart || !containerRef.current) return

    mermaid
      .render(graphId.current, chart)
      .then(({ svg }) => {
        if (containerRef.current) containerRef.current.innerHTML = svg
      })
      .catch(err => console.error('Mermaid render error:', err))
  }, [trace])

  if (!trace?.length) return null

  return (
    <div className="agent-graph">
      <p className="agent-graph__label">Agent flow</p>
      <div className="agent-graph__canvas" ref={containerRef} />
    </div>
  )
}
