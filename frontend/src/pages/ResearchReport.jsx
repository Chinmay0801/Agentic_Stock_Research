import { useParams, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { LineChart, Line, XAxis, Tooltip, ResponsiveContainer, YAxis } from 'recharts'
import './ResearchReport.css'

function ResearchReport() {
  const { id } = useParams()
  const { user } = useAuth()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showSimple, setShowSimple] = useState(false)

  useEffect(() => {
    if (user) {
      const saved = localStorage.getItem(`reports_${user.id}`)
      if (saved) {
        try {
          const reports = JSON.parse(saved)
          const found = reports.find((r) => String(r.id) === String(id))
          setReport(found || null)
        } catch {}
      }
    }
    setLoading(false)
  }, [id, user])

  if (loading) {
    return <div className="report-loading fade-in"><div className="spinner"></div><p className="loading-text">Loading report...</p></div>
  }

  if (!report) {
    return (
      <div className="report-error fade-in">
        <div className="error-icon">🔍</div>
        <h2>Report Not Found</h2>
        <p>The research report you're looking for doesn't exist.</p>
        <Link to="/" className="btn btn-primary">← Back to Dashboard</Link>
      </div>
    )
  }

  return (
    <div className="research-report fade-in" id="research-report-page">
      <Link to="/" className="back-link">← Back to Dashboard</Link>

      <header className="report-header">
        <div className="report-header-top">
          <div className="report-title-block">
            <h1>{report.ticker_symbol || 'General Research'}</h1>
            {report.company_name && <span className="report-company-name">{report.company_name}</span>}
          </div>
          <span className={`badge badge-${report.status.replace('_', '-')}`}>{report.status}</span>
        </div>
        <p className="report-query-text">{report.query}</p>
        <span className="report-timestamp">
          Generated {new Date(report.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </span>
      </header>

      {/* Feature 1: Stock Snapshot */}
      {report.snapshot && (
        <section className="snapshot-dashboard">
          <div className="snapshot-metrics">
            <div className="snapshot-item">
              <span className="snap-label">Current Price</span>
              <span className="snap-value">{report.snapshot.currency || '$'}{report.snapshot.price}</span>
            </div>
            <div className="snapshot-item">
              <span className="snap-label">Market Cap</span>
              <span className="snap-value">{report.snapshot.mcap}</span>
            </div>
            <div className="snapshot-item">
              <span className="snap-label">P/E Ratio</span>
              <span className="snap-value">{report.snapshot.pe}</span>
            </div>
            <div className="snapshot-item">
              <span className="snap-label">1-Day Change</span>
              <span className={`snap-value ${report.snapshot.diff1d.includes('+') ? 'text-green' : 'text-red'}`}>{report.snapshot.diff1d}</span>
            </div>
            <div className="snapshot-item">
              <span className="snap-label">1-Week Change</span>
              <span className={`snap-value ${report.snapshot.diff1w.includes('+') ? 'text-green' : 'text-red'}`}>{report.snapshot.diff1w}</span>
            </div>
          </div>
          <div className="snapshot-verdict">
            <span className="snap-label">AI Consensus</span>
            <span className={`snap-badge verdict-${report.snapshot.recommendation.toLowerCase()}`}>
              {report.snapshot.recommendation}
            </span>
          </div>
        </section>
      )}

      <div className="report-layout">
        <div className="report-main-col">
          {/* Feature 6: Price Chart */}
          <section className="card-static chart-section">
            <h2>📈 30-Session Price Trend</h2>
            <div className="chart-container">
              {report.chart_data ? (
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={report.chart_data}>
                    <XAxis dataKey="name" hide />
                    <YAxis domain={['auto', 'auto']} hide />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-color)', color: 'white' }} />
                    <Line type="monotone" dataKey="price" stroke="var(--accent-blue)" strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p>Chart data unavailable.</p>
              )}
            </div>
            {/* Feature 8: Explain Like Beginner */}
            <div className="beginner-toggle-section">
              <button className="btn btn-secondary" onClick={() => setShowSimple(!showSimple)}>
                🧠 {showSimple ? 'Hide Simple Explanation' : 'Explain this stock simply'}
              </button>
              {showSimple && report.summary && (
                <div className="beginner-explanation fade-in">
                  <p>{report.summary.text}</p>
                </div>
              )}
            </div>
          </section>

          {/* Feature 5 & 2: Fundamental Agent (Simple AI Summary) */}
          <section className="card-static agent-card" id="agent-fundamentals">
            <div className="agent-header">
              <span className="agent-avatar">🧑‍💼</span>
              <h2>Fundamental Agent</h2>
            </div>
            {report.summary && report.summary.bullets ? (
              <ul className="ai-summary-bullets">
                {report.summary.bullets.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            ) : (
              <p>No fundamental summary available.</p>
            )}
            <div className="agent-details">
              <p className="agent-verdict">Verdict: <strong>{report.fundamental_analysis?.verdict}</strong></p>
            </div>
          </section>

          {/* Feature 5 & 3: News Agent */}
          <section className="card-static agent-card" id="agent-news">
            <div className="agent-header">
              <span className="agent-avatar">📰</span>
              <h2>News Agent</h2>
            </div>
            {report.sentiment_analysis?.headlines ? (
              <div className="news-list">
                {report.sentiment_analysis.headlines.map((news, i) => (
                  <div key={i} className="news-item">
                    <span className={`news-label label-${news.sentiment}`}>
                      {news.sentiment === 'positive' ? '✅' : news.sentiment === 'negative' ? '❌' : '😐'} {news.label}
                    </span>
                    <p className="news-text">{news.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p>No news analyzed.</p>
            )}
          </section>
        </div>

        <div className="report-side-col">
          {/* Feature 5 & 4: Risk Agent */}
          <section className="card-static agent-card" id="agent-risk">
            <div className="agent-header">
              <span className="agent-avatar">⚠️</span>
              <h2>Risk Agent</h2>
            </div>
            <div className="risk-indicator-box">
              <span className="risk-label">Risk Level</span>
              <span className={`risk-gauge risk-${report.risk_assessment?.risk_level?.toLowerCase() || 'medium'}`}>
                {report.risk_assessment?.risk_level === 'High' ? '🔴 High Risk' : report.risk_assessment?.risk_level === 'Low' ? '🟢 Low Risk' : '🟡 Medium Risk'}
              </span>
            </div>
            <div className="risk-warnings">
              <h3>Key Risk Factors:</h3>
              <ul>
                {report.risk_assessment?.warnings?.slice(0, 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          </section>

          {/* Feature 5: Valuation Agent */}
          <section className="card-static agent-card" id="agent-valuation">
            <div className="agent-header">
              <span className="agent-avatar">💰</span>
              <h2>Valuation Agent</h2>
            </div>
            <div className="valuation-details">
              <p className="val-status"><strong>{report.valuation?.valuation_status}</strong></p>
              <p className="val-reason">{report.valuation?.reasoning}</p>
              <p className="val-estimate">Fair Price Estimate: <span>{report.valuation?.fair_price_estimate}</span></p>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export default ResearchReport
