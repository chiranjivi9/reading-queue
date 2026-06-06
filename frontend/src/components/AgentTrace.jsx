import { useState } from 'react'

const TOOL_ICONS = {
  list_articles:   '📋',
  web_search:      '🔍',
  save_digest:     '✅',
  report_findings: '📤',
}

const AGENT_LABELS = {
  discovery: 'Discovery',
  digest:    'Digest',
}

function AgentBadge({ agent }) {
  if (!agent) return null
  return (
    <span className={`trace__agent-badge trace__agent-badge--${agent}`}>
      {AGENT_LABELS[agent] ?? agent}
    </span>
  )
}

function TraceStep({ step }) {
  if (step.type === 'agent_start') {
    return (
      <div className="trace__step trace__step--agent-start">
        <AgentBadge agent={step.agent} />
        <span className="trace__agent-start-label">{step.summary}</span>
      </div>
    )
  }

  if (step.type === 'reasoning') {
    return (
      <div className="trace__step trace__step--reasoning">
        <span className="trace__icon">💭</span>
        <div className="trace__reasoning-body">
          <AgentBadge agent={step.agent} />
          <p className="trace__reasoning-text">{step.content}</p>
        </div>
      </div>
    )
  }

  const icon = TOOL_ICONS[step.tool] ?? '🔧'
  return (
    <div className="trace__step trace__step--tool">
      <span className="trace__icon">{icon}</span>
      <div className="trace__tool-body">
        <div className="trace__tool-header">
          <span className="trace__tool-name">{step.tool}</span>
          <AgentBadge agent={step.agent} />
        </div>
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
        How the agents thought&nbsp;{open ? '▲' : '▼'}
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
