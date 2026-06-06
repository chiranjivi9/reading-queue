/**
 * ArticleCard.jsx
 *
 * Displays one article in the list. Clicking the card navigates to the
 * detail page (/articles/:id). The delete button stops propagation so
 * it doesn't trigger navigation.
 */

import { useNavigate } from 'react-router-dom'
import { getDomain, scoreBadgeClass } from '../utils'

const API_KEY = import.meta.env.VITE_API_KEY ?? ''

export default function ArticleCard({ article, onDelete, onFavorite }) {
  const { id, url, title, score, score_reason, status, is_favorite } = article
  const navigate = useNavigate()

  async function handleDelete(e) {
    e.stopPropagation()
    if (!window.confirm('Delete this article?')) return
    await fetch(`/articles/${id}`, {
      method: 'DELETE',
      headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
    })
    onDelete(id)
  }

  async function handleFavorite(e) {
    e.stopPropagation()
    const res = await fetch(`/articles/${id}/favorite`, {
      method: 'PATCH',
      headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
    })
    if (res.ok && onFavorite) {
      const updated = await res.json()
      onFavorite(updated)
    }
  }

  return (
    <div className="card" onClick={() => navigate(`/articles/${id}`)}>
      <div className="card__header">
        <div className="card__title-group">
          <span className="card__title">{title ?? url}</span>
          <span className="card__domain">{getDomain(url)}</span>
        </div>

        <div className="card__actions">
          <span className={scoreBadgeClass(score)} title={score_reason ?? ''}>
            {score != null ? score : '–'}
          </span>
          <span className={`pill pill--${status}`}>{status}</span>
          <button
            className={`card__star${is_favorite ? ' card__star--active' : ''}`}
            onClick={handleFavorite}
            aria-label={is_favorite ? 'Unstar article' : 'Star article'}
          >
            {is_favorite ? '★' : '☆'}
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

      {score_reason && (
        <p className="card__score-reason">{score_reason}</p>
      )}
    </div>
  )
}
