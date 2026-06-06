import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  // 'loose' is required to allow click callbacks on nodes
  securityLevel: 'loose',
  flowchart: { curve: 'basis' },
})

// Returns { chart, nodeMap } where nodeMap[nodeIndex] = original trace index.
// Only agent_start and tool_call steps are shown as nodes.
function buildChart(trace, clickable) {
  const visible = (trace ?? [])
    .map((step, i) => ({ step, traceIndex: i }))
    .filter(({ step }) => step.type === 'agent_start' || step.type === 'tool_call')

  if (visible.length === 0) return null

  const lines = [
    'graph TD',
    '  classDef discovery fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f',
    '  classDef digest    fill:#dcfce7,stroke:#22c55e,color:#14532d',
    '  classDef done      fill:#fef9c3,stroke:#ca8a04,color:#713f12',
    '  classDef start     fill:#ede9fe,stroke:#7c3aed,color:#3b0764',
  ]

  const nodeIds = []

  visible.forEach(({ step, traceIndex }, i) => {
    const id = `N${i}`

    if (step.type === 'agent_start') {
      const label = step.agent === 'discovery' ? 'Discovery Agent' : 'Digest Agent'
      lines.push(`  ${id}(["${label}"]):::start`)
    } else {
      let label
      switch (step.tool) {
        case 'web_search':
          label = `search: "${(step.input?.query ?? '').slice(0, 36)}"`
          break
        case 'report_findings': label = step.summary ?? 'report findings'; break
        case 'save_digest':     label = 'save digest'; break
        case 'list_articles':   label = step.summary ?? 'list articles'; break
        default: label = step.tool ?? 'tool'
      }
      const cls = (step.tool === 'save_digest' || step.tool === 'report_findings')
        ? 'done'
        : (step.agent ?? 'discovery')
      const safe = label.replace(/"/g, "'").replace(/\n/g, ' ')
      lines.push(`  ${id}["${safe}"]:::${cls}`)
    }

    if (clickable) {
      lines.push(`  click ${id} call __agGraphClick("${traceIndex}")`)
    }
    nodeIds.push(id)
  })

  for (let i = 1; i < nodeIds.length; i++) {
    lines.push(`  ${nodeIds[i - 1]} --> ${nodeIds[i]}`)
  }

  return lines.join('\n')
}

let counter = 0

export default function AgentGraph({ trace, onNodeClick }) {
  const containerRef = useRef(null)
  const graphId = useRef(`ag-${++counter}`)
  const clickable = typeof onNodeClick === 'function'

  useEffect(() => {
    if (clickable) {
      window.__agGraphClick = (idxStr) => onNodeClick(parseInt(idxStr, 10))
    }
    return () => { if (clickable) delete window.__agGraphClick }
  }, [onNodeClick, clickable])

  useEffect(() => {
    const chart = buildChart(trace, clickable)
    if (!chart || !containerRef.current) return

    mermaid
      .render(graphId.current, chart)
      .then(({ svg, bindFunctions }) => {
        if (!containerRef.current) return
        containerRef.current.innerHTML = svg
        if (bindFunctions) bindFunctions(containerRef.current)
      })
      .catch(err => console.error('Mermaid render error:', err))
  }, [trace, clickable])

  if (!trace?.length) return null

  return (
    <div className="agent-graph">
      <div className="agent-graph__canvas" ref={containerRef} />
      {clickable && (
        <p className="agent-graph__hint">Click any node to see details</p>
      )}
    </div>
  )
}
