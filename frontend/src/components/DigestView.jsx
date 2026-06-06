import AgentTrace from './AgentTrace'
import AgentGraph from './AgentGraph'

export default function DigestView({ digest, onGenerate, generating }) {
  return (
    <section className="digest">
      <div className="digest__header">
        <h2 className="digest__heading">
          {digest ? `Week ${digest.week_number} Digest` : 'Weekly Digest'}
        </h2>
        <button
          className="digest__generate-btn"
          onClick={onGenerate}
          disabled={generating}
        >
          {generating ? 'Running…' : digest ? 'Regenerate' : 'Generate'}
        </button>
      </div>

      {digest ? (
        <>
          <pre className="digest__content">{digest.content}</pre>

          {digest.suggested_articles?.length > 0 && (
            <div className="digest__suggested">
              <p className="digest__suggested-heading">Also worth reading — found by the Discovery agent</p>
              <ul className="digest__suggested-list">
                {digest.suggested_articles.map((a, i) => (
                  <li key={i} className="digest__suggested-item">
                    <a href={a.url} target="_blank" rel="noreferrer" className="digest__suggested-title">
                      {a.title}
                    </a>
                    <p className="digest__suggested-reason">{a.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <AgentGraph trace={digest.trace} />
          <AgentTrace trace={digest.trace} />
        </>
      ) : (
        <p className="digest__empty">
          {generating
            ? 'Agent is thinking — check back in ~30 seconds…'
            : 'No digest yet this week. Click Generate to run the agent.'}
        </p>
      )}
    </section>
  )
}
