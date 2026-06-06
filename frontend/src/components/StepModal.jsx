const AGENT_LABELS = { discovery: 'Discovery', digest: 'Digest' }
const TOOL_ICONS   = { web_search: '🔍', report_findings: '📤', save_digest: '✅', list_articles: '📋' }

function Field({ label, value }) {
  if (!value) return null
  return (
    <div className="step-modal__field">
      <p className="step-modal__field-label">{label}</p>
      <p className="step-modal__field-value">{value}</p>
    </div>
  )
}

export default function StepModal({ step, onClose }) {
  const isReasoning = step.type === 'reasoning'
  const isAgentStart = step.type === 'agent_start'
  const icon = isReasoning ? '💭' : isAgentStart ? '🤖' : (TOOL_ICONS[step.tool] ?? '🔧')
  const title = isReasoning ? 'Reasoning'
              : isAgentStart ? step.summary
              : step.tool

  return (
    <div className="step-modal__overlay" onClick={onClose}>
      <div className="step-modal" onClick={e => e.stopPropagation()}>
        <div className="step-modal__header">
          <div className="step-modal__title-row">
            <span className="step-modal__icon">{icon}</span>
            <span className="step-modal__title">{title}</span>
            {step.agent && (
              <span className={`trace__agent-badge trace__agent-badge--${step.agent}`}>
                {AGENT_LABELS[step.agent] ?? step.agent}
              </span>
            )}
          </div>
          <button className="step-modal__close" onClick={onClose}>✕</button>
        </div>

        <div className="step-modal__body">
          {isReasoning && (
            <Field label="Thought" value={step.content} />
          )}
          {isAgentStart && (
            <Field label="Agent" value={AGENT_LABELS[step.agent] ?? step.agent} />
          )}
          {step.tool === 'web_search' && (
            <>
              <Field label="Query" value={step.input?.query} />
              <Field label="Result" value={step.summary} />
            </>
          )}
          {step.tool === 'report_findings' && (
            <Field label="Outcome" value={step.summary} />
          )}
          {step.tool === 'save_digest' && (
            <Field label="Outcome" value="Digest written and saved" />
          )}
          {step.tool === 'list_articles' && (
            <Field label="Outcome" value={step.summary} />
          )}
        </div>
      </div>
    </div>
  )
}
