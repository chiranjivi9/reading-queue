/**
 * ArticleCard.jsx
 *
 * Displays one article in the list. Clicking the card navigates to the
 * detail page (/articles/:id). The delete button stops propagation so
 * it doesn't trigger navigation.
 */

import { useNavigate } from 'react-router-dom'
import { getDomain, scoreBadgeClass } from '../utils'

export default function ArticleCard({ article, onDelete }) {
  const { id, url, title, score, score_reason, status } = article
  const navigate = useNavigate()

  async function handleDelete(e) {
    e.stopPropagation()
    if (!window.confirm('Delete this article?')) return
    await fetch(`/articles/${id}`, { method: 'DELETE' })
    onDelete(id)
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
