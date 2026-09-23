import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ToastContainer, useToast } from '../components/Toast'
import { API_BASE } from '../services/api'
import './Dashboard.css'

const PIPELINE_STEPS = [
  { key: 'fetch', label: 'Fetching market data', icon: '📡' },
  { key: 'fundamental', label: 'Analyzing fundamentals', icon: '📊' },
  { key: 'sentiment', label: 'Evaluating sentiment', icon: '💬' },
  { key: 'risk', label: 'Assessing risks', icon: '⚠️' },
  { key: 'valuation', label: 'Calculating valuation', icon: '💰' },
  { key: 'done', label: 'Finalizing verdict', icon: '✅' },
]

// Smart Query Mapping
const SMART_QUERIES = [
  { trigger: 'high dividend tech', match: 'tech', targets: ['MSFT', 'AAPL'] },
  { trigger: 'indian IT', match: 'it', targets: ['TCS', 'INFY'] },
  { trigger: 'growth stocks', match: 'growth', targets: ['NVDA', 'TSLA'] },
  { trigger: 'conglomerate', match: 'conglomerate', targets: ['RELIANCE'] },
]

function Dashboard() {
  const { user } = useAuth()
  const { toasts, addToast, removeToast } = useToast()
  const [query, setQuery] = useState('')
  const [ticker, setTicker] = useState('')
  const [reports, setReports] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(-1)
  const [smartSuggestions, setSmartSuggestions] = useState([])
  const [quotes, setQuotes] = useState({})
  const [quotesLoading, setQuotesLoading] = useState(false)

  // Load saved data
  useEffect(() => {
    if (user) {
      const savedReports = localStorage.getItem(`reports_${user.id}`)
      if (savedReports) {
        try { setReports(JSON.parse(savedReports)) } catch {}
      }
      const savedWatchlist = localStorage.getItem(`watchlist_${user.id}`)
      if (savedWatchlist) {
        try { setWatchlist(JSON.parse(savedWatchlist)) } catch {}
      }
    }
  }, [user])

  // Persist reports & watchlist
  useEffect(() => {
    if (user && reports.length > 0) localStorage.setItem(`reports_${user.id}`, JSON.stringify(reports))
  }, [reports, user])

  useEffect(() => {
    if (user) localStorage.setItem(`watchlist_${user.id}`, JSON.stringify(watchlist))
  }, [watchlist, user])

  // Evaluate Smart Query
  useEffect(() => {
    if (query.trim().length > 3) {
      const q = query.toLowerCase()
      const matches = SMART_QUERIES.filter(sq => q.includes(sq.match) || q.includes(sq.trigger))
      if (matches.length > 0) {
        setSmartSuggestions([...new Set(matches.flatMap(m => m.targets))])
      } else {
        setSmartSuggestions([])
      }
    } else {
      setSmartSuggestions([])
    }
  }, [query])

  const handleNewResearch = async (e, directTicker = null) => {
    if (e) e.preventDefault()
    const targetTicker = directTicker || ticker

    if (!targetTicker.trim()) {
      addToast('Please enter a stock ticker symbol (e.g. AAPL)', 'warning')
      return
    }

    setTicker(targetTicker)
    setLoading(true)
    setPipelineStep(0)

    try {
      for (let i = 0; i < PIPELINE_STEPS.length; i++) {
        setPipelineStep(i)
        // Shorter delay since we actually make a network call now
        await new Promise((r) => setTimeout(r, 400 + Math.random() * 200))
      }

      // Fetch from DJANGO local server!
      const response = await fetch(`${API_BASE}/api/research/quick-demo/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticker: targetTicker.toUpperCase(),
          query: query || `Comprehensive analysis of ${targetTicker.toUpperCase()}`
        })
      });

      if (!response.ok) {
        // The API explains unknown tickers and upstream outages; show that
        // rather than a generic "server down" message.
        const detail = await response.json().catch(() => null)
        addToast(detail?.detail || 'Failed to fetch from Django server.', 'error')
        setLoading(false)
        setPipelineStep(-1)
        return
      }

      const report = await response.json()

      setReports([report, ...reports])
      setQuery('')
      setTicker('')
      setSmartSuggestions([])
      // The backend may resolve 'TCS' to its NSE listing, 'TCS.NS'.
      addToast(`Live report for ${report.ticker_symbol} (${report.company_name}) generated!`, 'success')
    } catch (error) {
      console.error(error)
      addToast('Failed to connect to Django server. Is it running?', 'error')
    }

    setLoading(false)
    setPipelineStep(-1)
  }

  // Live prices for the watchlist, keyed by the symbol the user starred.
  const fetchQuotes = useCallback(async (symbols) => {
    if (symbols.length === 0) {
      setQuotes({})
      return
    }
    setQuotesLoading(true)
    try {
      const params = new URLSearchParams({ symbols: symbols.join(',') })
      const response = await fetch(`${API_BASE}/api/research/quotes/?${params}`)
      if (response.ok) {
        const data = await response.json()
        const next = {}
        data.quotes.forEach((q) => { next[q.requested_symbol] = q })
        setQuotes(next)
      }
    } catch {
      // A failed refresh leaves the last known prices on screen.
    }
    setQuotesLoading(false)
  }, [])

  useEffect(() => {
    fetchQuotes(watchlist)
  }, [watchlist, fetchQuotes])

  const refreshQuotes = () => fetchQuotes(watchlist)

  const toggleWatchlist = (e, sym) => {
    e.preventDefault()
    e.stopPropagation()
    if (watchlist.includes(sym)) {
      setWatchlist(watchlist.filter(t => t !== sym))
      addToast(`${sym} removed from watchlist`, 'info')
    } else {
      setWatchlist([...watchlist, sym])
      addToast(`${sym} added to watchlist!`, 'success')
    }
  }

  return (
    <div className="dashboard fade-in" id="dashboard-page">
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      <header className="dashboard-header">
        <div className="header-content">
          <h1>Research Dashboard</h1>
          <p className="subtitle">Launch AI-powered stock analysis with autonomous agents</p>
        </div>
        {user && (
          <div className="header-actions">
            <Link to="/compare" className="btn btn-secondary">⚖️ Compare Stocks</Link>
            <div className="header-welcome">
              <span className="welcome-msg">Welcome, <strong>{user.username}</strong></span>
            </div>
          </div>
        )}
      </header>

      <div className="dashboard-layout">
        <div className="main-column">
          {/* New Research Form */}
          <section className="card-static new-research" id="new-research-form">
            <h2>🚀 New Research</h2>
            <form onSubmit={handleNewResearch} className="research-form">
              <div className="form-row">
                <div className="input-group">
                  <label htmlFor="ticker-input">Stock Ticker</label>
                  <input
                    id="ticker-input"
                    type="text"
                    className="input-field"
                    placeholder="e.g. AAPL, TCS, NVDA"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    disabled={loading}
                  />
                </div>
                <div className="input-group" style={{ flex: 2, position: 'relative' }}>
                  <label htmlFor="query-input">Smart Query (optional) 💡</label>
                  <input
                    id="query-input"
                    type="text"
                    className="input-field"
                    placeholder='e.g. "high dividend tech" or "indian it"'
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    disabled={loading}
                  />
                  {/* Smart Query Dropdown */}
                  {smartSuggestions.length > 0 && !loading && (
                    <div className="smart-suggestions fade-in">
                      <span className="smart-label">🎯 AI Suggestions for your query:</span>
                      <div className="smart-chips">
                        {smartSuggestions.map(s => (
                          <button key={s} type="button" className="suggestion-chip" onClick={() => handleNewResearch(null, s)}>
                            {s} / Analyze Now
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? <><span className="spinner"></span> Calling Django API...</> : '⚡ Start Research'}
              </button>
            </form>

            {/* Pipeline Progress */}
            {loading && (
               <div className="pipeline-progress" id="pipeline-progress">
                {PIPELINE_STEPS.map((step, i) => (
                  <div key={step.key} className={`pipeline-step ${ i < pipelineStep ? 'step-done' : i === pipelineStep ? 'step-active' : 'step-pending' }`}>
                    <span className="step-icon">{i < pipelineStep ? '✅' : step.icon}</span>
                    <span className="step-label">{step.label}</span>
                    {i === pipelineStep && <span className="spinner step-spinner"></span>}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Reports List */}
          <section className="reports-section">
            <div className="reports-header">
              <h2>📄 Recent Reports</h2>
              {reports.length > 0 && <span className="report-count">{reports.length} report{reports.length !== 1 ? 's' : ''}</span>}
            </div>
            {reports.length === 0 ? (
              <div className="empty-state card-static">
                <div className="empty-icon">📈</div>
                <h3>No research reports yet</h3>
                <p>Enter a stock ticker above and click "Start Research" to safely test the Django backend connection.</p>
              </div>
            ) : (
              <div className="reports-grid">
                {reports.map((report) => (
                  <Link to={`/report/${report.id}`} key={report.id} className="report-card card">
                    <div className="report-card-header">
                      <div className="report-ticker-group">
                        <span className="report-ticker">{report.ticker_symbol || '🔍'}</span>
                        <button className="watchlist-star-btn" onClick={(e) => toggleWatchlist(e, report.ticker_symbol)}>
                          {watchlist.includes(report.ticker_symbol) ? '⭐' : '☆'}
                        </button>
                      </div>
                      <span className={`badge badge-${report.status.replace('_', '-')}`}>{report.status}</span>
                    </div>
                    {report.company_name && <span className="report-company">{report.company_name}</span>}
                    <p className="report-query">{report.query}</p>
                    <div className="report-card-footer">
                      <span className="report-date">{new Date(report.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                      <span className="report-view">View Insights →</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Watchlist Sidebar */}
        <div className="sidebar-column">
          <div className="card-static watchlist-card">
            <div className="watchlist-header">
              <h2>⭐ Watchlist</h2>
              <span className="badge badge-pending">{watchlist.length} saved</span>
            </div>
            {watchlist.length === 0 ? (
              <p className="empty-watchlist-text">Star a report to save it here.</p>
            ) : (
              <div className="watchlist-list">
                {watchlist.map(sym => {
                  const quote = quotes[sym]
                  return (
                    <div key={sym} className="watchlist-item">
                      <div className="watchlist-info">
                        <span className="watchlist-sym">{quote?.symbol || sym}</span>
                        {quote && !quote.error && (
                          <span className="watchlist-price">
                            {quote.currency}{quote.price}
                            <span className={quote.change_pct >= 0 ? 'text-green' : 'text-red'}>
                              {' '}{quote.change_display}
                            </span>
                          </span>
                        )}
                        {quotesLoading && !quote && <span className="watchlist-price muted">loading…</span>}
                        {quote?.error && <span className="watchlist-price muted">unavailable</span>}
                      </div>
                      <button className="btn btn-secondary btn-sm" onClick={() => handleNewResearch(null, sym)}>Analyze</button>
                    </div>
                  )
                })}
              </div>
            )}
            {watchlist.length > 0 && (
              <button
                className="btn btn-secondary btn-sm watchlist-refresh"
                onClick={refreshQuotes}
                disabled={quotesLoading}
              >
                {quotesLoading ? 'Refreshing…' : '🔄 Refresh prices'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
