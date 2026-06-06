/**
 * ArticleDetailPage.jsx — /articles/:id
 *
 * Shows the full article summary and hosts the chat interface.
 * Chat history lives in local state; the full messages array is sent on
 * every request so Claude has context for follow-up questions.
 * The backend caches the article text in the system prompt, so only the
 * new user message is billed at full token cost on each turn.
 */

import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDomain, scoreBadgeClass } from '../utils'

const API_KEY = import.meta.env.VITE_API_KEY ?? ''

export default function ArticleDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [article, setArticle]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [messages, setMessages]     = useState([])   // [{role, content}]
  const [input, setInput]           = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const messagesEndRef = useRef(null)

  // Fetch article on mount.
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/articles/${id}`)
        if (!res.ok) { navigate('/'); return }
        setArticle(await res.json())
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  // Scroll to latest message whenever messages change.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(e) {
    e.preventDefault()
    if (!input.trim() || chatLoading) return

    const userMsg = { role: 'user', content: input.trim() }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setChatLoading(true)

    try {
      const res = await fetch(`/articles/${id}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(API_KEY && { 'X-API-Key': API_KEY }),
        },
        body: JSON.stringify({ messages: nextMessages }),
      })
      if (!res.ok) throw new Error('Chat request failed')
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ])
    } finally {
      setChatLoading(false)
    }
  }

  if (loading) {
    return <div className="detail-loading">Loading…</div>
  }

  if (!article) return null

  const isReady = article.status === 'ready'

  return (
    <div className="app">
      <header className="detail__header">
        <button className="back-btn" onClick={() => navigate('/')}>← Back</button>
        <h1 className="detail__title">{article.title ?? article.url}</h1>
        <div className="detail__meta">
          <span className="card__domain">{getDomain(article.url)}</span>
          <span className={scoreBadgeClass(article.score)}>
            {article.score != null ? article.score : '–'}
          </span>
          <span className={`pill pill--${article.status}`}>{article.status}</span>
        </div>
      </header>

      <main className="detail__main">
        {/* Summary section */}
        {article.summary && (
          <section className="detail__section">
            <h2 className="section__heading">Summary</h2>
            <p className="detail__summary-text">{article.summary}</p>
            {article.score_reason && (
              <p className="detail__score-reason">{article.score_reason}</p>
            )}
          </section>
        )}

        {/* Not-yet-ready notice */}
        {!isReady && (
          <div className="detail__notice">
            Article is <strong>{article.status}</strong> — chat will be available once processing completes.
          </div>
        )}

        {/* Chat section */}
        {isReady && (
          <section className="detail__section">
            <h2 className="section__heading">Chat with this article</h2>

            <div className="chat__messages">
              {messages.length === 0 && (
                <p className="chat__empty">Ask anything about this article.</p>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`chat__bubble chat__bubble--${m.role}`}>
                  {m.content}
                </div>
              ))}
              {chatLoading && (
                <div className="chat__bubble chat__bubble--assistant chat__bubble--loading">
                  Thinking…
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat__form" onSubmit={sendMessage}>
              <input
                className="chat__input"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Ask about this article…"
                disabled={chatLoading}
              />
              <button
                className="chat__send"
                type="submit"
                disabled={!input.trim() || chatLoading}
              >
                Send
              </button>
            </form>
          </section>
        )}
      </main>
    </div>
  )
}
