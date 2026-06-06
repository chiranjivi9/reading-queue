import { useNavigate } from 'react-router-dom'

const PREVIEW_LEN = 180

export default function DigestView({ digest, onGenerate, generating }) {
  const navigate = useNavigate()
  const preview = digest
    ? digest.content.slice(0, PREVIEW_LEN) + (digest.content.length > PREVIEW_LEN ? '…' : '')
    : null

  return (
    <section className="digest">
      <div className="digest__header">
        <h2 className="digest__heading">
          {digest ? `Week ${digest.week_number} Digest` : 'Weekly Digest'}
        </h2>
        <button
          className="digest__generate-btn"
          onClick={e => { e.stopPropagation(); onGenerate() }}
          disabled={generating}
        >
          {generating ? 'Running…' : digest ? 'Regenerate' : 'Generate'}
        </button>
      </div>

      {digest ? (
        <div className="digest__preview" onClick={() => navigate('/digest')} role="button" tabIndex={0}
             onKeyDown={e => e.key === 'Enter' && navigate('/digest')}>
          <p className="digest__preview-text">{preview}</p>
          <span className="digest__read-more">Read full digest →</span>
        </div>
      ) : (
        <p className="digest__empty">
          {generating
            ? 'Agents are running — check back in ~30 seconds…'
            : 'No digest yet this week. Click Generate to run the agents.'}
        </p>
      )}
    </section>
  )
}
