import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDomain, scoreBadgeClass } from '../utils'

const API_KEY = import.meta.env.VITE_API_KEY ?? ''

const PREVIEW_LEN = 200

function formatDate(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
  })
}

function DigestRow({ digest, onDelete }) {
  const preview = digest.content.slice(0, PREVIEW_LEN) + (digest.content.length > PREVIEW_LEN ? '…' : '')
  const navigate = useNavigate()

  async function handleDelete(e) {
    e.stopPropagation()
    if (!window.confirm(`Delete Week ${digest.week_number} digest?`)) return
    await fetch(`/digest/${digest.id}`, {
      method: 'DELETE',
      headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
    })
    onDelete(digest.id)
  }

  return (
    <div className="history-digest" onClick={() => navigate(`/digest/${digest.id}`)} role="button" tabIndex={0}
         onKeyDown={e => e.key === 'Enter' && navigate(`/digest/${digest.id}`)}>
      <div className="history-digest__header">
        <div>
          <span className="history-digest__week">Week {digest.week_number}</span>
          <span className="history-digest__date">{formatDate(digest.created_at)}</span>
        </div>
        <button
          className="card__delete"
          onClick={handleDelete}
          aria-label="Delete digest"
        >
          ✕
        </button>
      </div>
      <p className="history-digest__preview">{preview}</p>
    </div>
  )
}

function FavoriteRow({ article, onUnfavorite, onDelete }) {
  async function handleUnfavorite(e) {
    e.stopPropagation()
    const res = await fetch(`/articles/${article.id}/favorite`, {
      method: 'PATCH',
      headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
    })
    if (res.ok) onUnfavorite(article.id)
  }

  async function handleDelete(e) {
    e.stopPropagation()
    if (!window.confirm('Delete this article?')) return
    await fetch(`/articles/${article.id}`, {
      method: 'DELETE',
      headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
    })
    onDelete(article.id)
  }

  return (
    <div className="history-fav">
      <div className="history-fav__info">
        <span className="history-fav__title">{article.title ?? article.url}</span>
        <span className="history-fav__domain">{getDomain(article.url)}</span>
      </div>
      <div className="history-fav__actions">
        <span className={scoreBadgeClass(article.score)}>
          {article.score != null ? article.score : '–'}
        </span>
        <button
          className="card__star card__star--active"
          onClick={handleUnfavorite}
          aria-label="Unstar article"
          title="Remove from favorites"
        >
          ★
        </button>
        <button
          className="card__delete"
          onClick={handleDelete}
          aria-label="Delete article"
        >
          ✕
        </button>
      </div>
    </div>
  )
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [digests, setDigests] = useState([])
  const [favorites, setFavorites] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/digest/all').then(r => r.ok ? r.json() : []),
      fetch('/articles/favorites').then(r => r.ok ? r.json() : []),
    ]).then(([allDigests, favArticles]) => {
      setDigests(allDigests)
      setFavorites(favArticles)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  function removeDigest(id) {
    setDigests(prev => prev.filter(d => d.id !== id))
  }

  function removeFavorite(id) {
    setFavorites(prev => prev.filter(a => a.id !== id))
  }

  function deleteArticle(id) {
    setFavorites(prev => prev.filter(a => a.id !== id))
  }

  if (loading) return <div className="detail-loading">Loading…</div>

  return (
    <div className="app">
      <div className="digest-page__nav">
        <button className="back-btn" onClick={() => navigate('/')}>← Back</button>
      </div>

      <h1 className="digest-page__title" style={{ marginBottom: 24 }}>History</h1>

      {/* Favorites */}
      <section className="history-section">
        <h2 className="history-section__heading">Starred Articles</h2>
        {favorites.length === 0 ? (
          <p className="history-section__empty">No starred articles yet. Hit ☆ on any article to save it here.</p>
        ) : (
          <ul className="history-fav-list">
            {favorites.map(a => (
              <li key={a.id}>
                <FavoriteRow
                  article={a}
                  onUnfavorite={removeFavorite}
                  onDelete={deleteArticle}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Past digests */}
      <section className="history-section">
        <h2 className="history-section__heading">Past Digests</h2>
        {digests.length === 0 ? (
          <p className="history-section__empty">No digests yet. Generate one from the home page.</p>
        ) : (
          <ul className="history-digest-list">
            {digests.map(d => (
              <li key={d.id}>
                <DigestRow digest={d} onDelete={removeDigest} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
