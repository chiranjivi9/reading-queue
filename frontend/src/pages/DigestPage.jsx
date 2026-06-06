import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AgentGraph from '../components/AgentGraph'
import AgentTrace from '../components/AgentTrace'
import StepModal from '../components/StepModal'

const API_KEY = import.meta.env.VITE_API_KEY ?? ''

function TokenBadge({ usage }) {
  if (!usage) return null
  const total = (usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)
  const cached = usage.cache_read_tokens ?? 0
  return (
    <div className="digest-page__tokens">
      <span className="token-stat">{total.toLocaleString()} tokens</span>
      <span className="token-divider">·</span>
      <span className="token-stat">{usage.output_tokens?.toLocaleString()} out</span>
      {cached > 0 && (
        <>
          <span className="token-divider">·</span>
          <span className="token-stat token-stat--cached">{cached.toLocaleString()} cached</span>
        </>
      )}
    </div>
  )
}

function formatTimestamp(ts) {
  if (!ts) return null
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function DigestPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const [digest, setDigest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [toast, setToast] = useState(null)
  const [selectedStep, setSelectedStep] = useState(null)

  const isPastDigest = Boolean(id)

  function showToast(message, type = 'success') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  function fetchDigest() {
    const url = id ? `/digest/${id}` : '/digest/current'
    return fetch(url)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setDigest(data); return data })
      .catch(() => null)
  }

  useEffect(() => {
    fetchDigest().finally(() => setLoading(false))
  }, [id])

  async function handleRegenerate() {
    setGenerating(true)
    try {
      const res = await fetch('/digest/generate', {
        method: 'POST',
        headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
      })
      if (!res.ok) throw new Error(await res.text())
      showToast('Digest agent started — this takes ~30 seconds…')
      const poll = setInterval(async () => {
        const data = await fetchDigest()
        if (data) { clearInterval(poll); setGenerating(false) }
      }, 3000)
      setTimeout(() => { clearInterval(poll); setGenerating(false) }, 120_000)
    } catch {
      showToast('Failed to start digest agent', 'error')
      setGenerating(false)
    }
  }

  if (loading) return <div className="detail-loading">Loading digest…</div>
  if (!digest)  return (
    <div className="detail-loading">
      No digest yet this week.
      <br />
      <button className="back-btn" style={{ marginTop: 12 }} onClick={() => navigate('/')}>← Back</button>
    </div>
  )

  return (
    <div className="app">
      {toast && <div className={`toast toast--${toast.type}`}>{toast.message}</div>}

      <div className="digest-page__nav">
        <button className="back-btn" onClick={() => navigate(-1)}>← Back</button>
        {!isPastDigest && (
          <button
            className="digest__generate-btn"
            onClick={handleRegenerate}
            disabled={generating}
          >
            {generating ? 'Running…' : 'Regenerate'}
          </button>
        )}
      </div>

      <div className="digest-page__header">
        <h1 className="digest-page__title">Week {digest.week_number} Digest</h1>
        <div className="digest-page__meta">
          {digest.created_at && (
            <span className="digest-page__timestamp">{formatTimestamp(digest.created_at)}</span>
          )}
          <TokenBadge usage={digest.token_usage} />
        </div>
      </div>

      <div className="digest-page__body">
        {/* Full digest content */}
        <section className="digest-page__section">
          <pre className="digest-page__content">{digest.content}</pre>
        </section>

        {/* Discovery picks */}
        {digest.suggested_articles?.length > 0 && (
          <section className="digest-page__section">
            <h2 className="digest-page__section-heading">Also worth reading</h2>
            <p className="digest-page__section-sub">Found by the Discovery agent</p>
            <ul className="digest-page__suggested-list">
              {digest.suggested_articles.map((a, i) => (
                <li key={i} className="digest-page__suggested-item">
                  <a href={a.url} target="_blank" rel="noreferrer" className="digest-page__suggested-title">
                    {a.title}
                  </a>
                  <p className="digest-page__suggested-reason">{a.reason}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Clickable agent graph */}
        {digest.trace?.length > 0 && (
          <section className="digest-page__section">
            <h2 className="digest-page__section-heading">Agent flow</h2>
            <p className="digest-page__section-sub">Click any node to see details</p>
            <AgentGraph
              trace={digest.trace}
              onNodeClick={idx => setSelectedStep(digest.trace[idx])}
            />
          </section>
        )}

        {/* Full expandable trace */}
        <AgentTrace trace={digest.trace} />
      </div>

      {selectedStep && (
        <StepModal step={selectedStep} onClose={() => setSelectedStep(null)} />
      )}
    </div>
  )
}
