/**
 * App.jsx — Root component.
 *
 * Sets up client-side routing. The home route (/) owns article + digest state
 * and polls every 5 seconds. The detail route (/articles/:id) is fully
 * self-contained inside ArticleDetailPage.
 */

import { useEffect, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import AddArticle from './components/AddArticle'
import ArticleCard from './components/ArticleCard'
import DigestView from './components/DigestView'
import ArticleDetailPage from './pages/ArticleDetailPage'
import './App.css'

const POLL_INTERVAL_MS = 5000

export default function App() {
  const [articles, setArticles] = useState([])
  const [digest, setDigest]     = useState(null)
  const [toast, setToast]       = useState(null)

  async function fetchArticles() {
    try {
      const res = await fetch('/articles')
      if (!res.ok) return
      setArticles(await res.json())
    } catch {
      // silently ignore during background polling
    }
  }

  async function fetchDigest() {
    try {
      const res = await fetch('/digest/current')
      if (!res.ok) return
      setDigest(await res.json())
    } catch {
      // digest is optional
    }
  }

  useEffect(() => {
    fetchArticles()
    fetchDigest()
    const interval = setInterval(fetchArticles, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [])

  function handleAdd(newArticle) {
    setArticles(prev => {
      if (prev.some(a => a.id === newArticle.id)) return prev
      return [newArticle, ...prev]
    })
    showToast('Article added — processing…', 'success')
  }

  function handleDelete(deletedId) {
    setArticles(prev => prev.filter(a => a.id !== deletedId))
  }

  function showToast(message, type = 'success') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            <div className="app">
              <header className="app__header">
                <h1 className="app__title">Reading Queue</h1>
                <p className="app__subtitle">Paste articles. Get a ranked digest every Friday.</p>
              </header>

              <main className="app__main">
                <AddArticle onAdd={handleAdd} />
                <DigestView digest={digest} />

                {articles.length === 0 ? (
                  <div className="empty-state">
                    <p>No articles this week yet.</p>
                    <p>Paste a URL above to get started.</p>
                  </div>
                ) : (
                  <ul className="article-list">
                    {articles.map(article => (
                      <li key={article.id}>
                        <ArticleCard article={article} onDelete={handleDelete} />
                      </li>
                    ))}
                  </ul>
                )}
              </main>
            </div>
          }
        />

        <Route path="/articles/:id" element={<ArticleDetailPage />} />
      </Routes>

      {toast && (
        <div className={`toast toast--${toast.type}`}>{toast.message}</div>
      )}
    </>
  )
}
