import { useState } from 'react'

const TOOL_ICONS = {
  list_articles: '📋',
  web_search: '🔍',
  save_digest: '✅',
}

function TraceStep({ step }) {
  if (step.type === 'reasoning') {
    return (
      <div className="trace__step trace__step--reasoning">
        <span className="trace__icon">💭</span>
        <p className="trace__reasoning-text">{step.content}</p>
      </div>
    )
  }

  const icon = TOOL_ICONS[step.tool] ?? '🔧'
  return (
    <div className="trace__step trace__step--tool">
      <span className="trace__icon">{icon}</span>
      <div className="trace__tool-body">
        <span className="trace__tool-name">{step.tool}</span>
        {step.input?.query && (
          <span className="trace__tool-query">"{step.input.query}"</span>
        )}
        {step.summary && (
          <span className="trace__tool-summary">{step.summary}</span>
        )}
      </div>
    </div>
  )
}

export default function AgentTrace({ trace }) {
  const [open, setOpen] = useState(false)

  if (!trace || trace.length === 0) return null

  return (
    <div className="trace">
      <button className="trace__toggle" onClick={() => setOpen(o => !o)}>
        How the agent thought&nbsp;{open ? '▲' : '▼'}
      </button>

      {open && (
        <div className="trace__steps">
          {trace.map((step, i) => (
            <TraceStep key={i} step={step} />
          ))}
        </div>
      )}
    </div>
  )
}
