/**
 * App.jsx — Root component.
 *
 * Sets up client-side routing. The home route (/) owns article + digest state
 * and polls every 5 seconds. The detail route (/articles/:id) is fully
 * self-contained inside ArticleDetailPage.
 */

import { useEffect, useState } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import AddArticle from './components/AddArticle'
import ArticleCard from './components/ArticleCard'
import DigestView from './components/DigestView'
import ArticleDetailPage from './pages/ArticleDetailPage'
import DigestPage from './pages/DigestPage'
import HistoryPage from './pages/HistoryPage'
import './App.css'

const POLL_INTERVAL_MS = 5000
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

export default function App() {
  const [articles, setArticles]         = useState([])
  const [digest, setDigest]             = useState(null)
  const [toast, setToast]               = useState(null)
  const [digestRunning, setDigestRunning] = useState(false)
  const navigate = useNavigate()

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

  function handleFavorite(updatedArticle) {
    setArticles(prev => prev.map(a => a.id === updatedArticle.id ? updatedArticle : a))
  }

  function showToast(message, type = 'success') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  async function handleGenerateDigest() {
    setDigestRunning(true)
    try {
      const res = await fetch('/digest/generate', {
        method: 'POST',
        headers: { ...(API_KEY && { 'X-API-Key': API_KEY }) },
      })
      if (!res.ok) throw new Error(await res.text())
      showToast('Digest agent started — this takes ~30 seconds…')
      // Poll more aggressively until digest appears
      const poll = setInterval(async () => {
        await fetchDigest()
        setDigest(prev => {
          if (prev) { clearInterval(poll); setDigestRunning(false) }
          return prev
        })
      }, 3000)
      setTimeout(() => { clearInterval(poll); setDigestRunning(false) }, 120_000)
    } catch {
      showToast('Failed to start digest agent', 'error')
      setDigestRunning(false)
    }
  }

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            <div className="app">
              <header className="app__header">
                <div className="app__title-row">
                  <h1 className="app__title">Reading Queue</h1>
                  <button className="app__nav-link" onClick={() => navigate('/history')}>History</button>
                </div>
                <p className="app__subtitle">Paste articles. Get a ranked digest every Friday.</p>
              </header>

              <main className="app__main">
                <AddArticle onAdd={handleAdd} />
                <DigestView
                  digest={digest}
                  onGenerate={handleGenerateDigest}
                  generating={digestRunning}
                />

                {articles.length === 0 ? (
                  <div className="empty-state">
                    <p>No articles this week yet.</p>
                    <p>Paste a URL above to get started.</p>
                  </div>
                ) : (
                  <ul className="article-list">
                    {articles.map(article => (
                      <li key={article.id}>
                        <ArticleCard article={article} onDelete={handleDelete} onFavorite={handleFavorite} />
                      </li>
                    ))}
                  </ul>
                )}
              </main>
            </div>
          }
        />

        <Route path="/articles/:id" element={<ArticleDetailPage />} />
        <Route path="/digest" element={<DigestPage />} />
        <Route path="/digest/:id" element={<DigestPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>

      {toast && (
        <div className={`toast toast--${toast.type}`}>{toast.message}</div>
      )}
    </>
  )
}
