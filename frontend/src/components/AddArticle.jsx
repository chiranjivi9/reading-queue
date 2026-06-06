/**
 * AddArticle.jsx
 *
 * URL input bar at the top of the page. On submit it calls POST /articles
 * and immediately passes the new pending article up to App so a card
 * appears without waiting for the next poll cycle.
 */

import { useState } from 'react'

// Read from frontend/.env.local (gitignored). If not set, no header is sent
// and the backend skips auth (dev mode). In production set both SECRET_KEY
// (backend) and VITE_API_KEY (frontend) to the same value.
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

/**
 * @param {function} onAdd - called with the new article object after a
 *                           successful POST so App can add it to state
 */
export default function AddArticle({ onAdd }) {
  const [url, setUrl]         = useState('')     // controlled input value
  const [loading, setLoading] = useState(false)  // disables button while posting
  const [error, setError]     = useState(null)   // inline error message

  async function handleSubmit(e) {
    // prevent the browser's default form behaviour (page reload)
    e.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/articles', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(API_KEY && { 'X-API-Key': API_KEY }),
        },
        body: JSON.stringify({ url: url.trim() }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail ?? `Server error ${response.status}`)
      }

      const article = await response.json()
      onAdd(article)   // hand the new article up to App
      setUrl('')        // clear the input
    } catch (err) {
      setError(err.message)
    } finally {
      // always re-enable the button, whether the request succeeded or failed
      setLoading(false)
    }
  }

  return (
    <form className="add-article" onSubmit={handleSubmit}>
      <input
        type="url"
        placeholder="Paste an article URL…"
        value={url}
        onChange={e => setUrl(e.target.value)}
        disabled={loading}
        required
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Adding…' : 'Add'}
      </button>
      {error && <p className="add-article__error">{error}</p>}
    </form>
  )
}
