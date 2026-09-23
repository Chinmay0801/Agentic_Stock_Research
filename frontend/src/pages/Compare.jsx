import { useState } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE } from '../services/api'
import './Dashboard.css'
import './Compare.css'

// Quick picks, grouped by market — comparisons only run within one market.
const PRESETS = [
  { market: '🇮🇳 India (NSE)', pairs: [['TCS', 'INFY'], ['RELIANCE', 'HDFCBANK'], ['WIPRO', 'HCLTECH']] },
  { market: '🇺🇸 United States', pairs: [['AAPL', 'MSFT'], ['NVDA', 'AMD'], ['GOOGL', 'META']] },
]

// Values that are already formatted strings, or need a unit appended.
const SUFFIXED = {
  'revenue_growth': '%', 'earnings_growth': '%', 'profit_margin': '%',
  'return_on_equity': '%', 'dividend_yield': '%', 'volatility': '%',
}

function formatCell(row, side, currency) {
  const value = row[side]
  if (value === null || value === undefined) return '—'
  if (row.key === 'price') return `${currency}${value}`
  if (SUFFIXED[row.key]) return `${value}${SUFFIXED[row.key]}`
  return String(value)
}

function Compare() {
  const [ticker1, setTicker1] = useState('TCS')
  const [ticker2, setTicker2] = useState('INFY')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const runComparison = async (e, a = null, b = null) => {
    if (e) e.preventDefault()
    const left = (a || ticker1).trim()
    const right = (b || ticker2).trim()

    if (!left || !right) {
      setError('Enter two ticker symbols to compare.')
      return
    }

    setTicker1(left)
    setTicker2(right)
    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE}/api/research/compare/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker1: left, ticker2: right }),
      })
      const data = await response.json()

      if (!response.ok) {
        // Covers unknown tickers (404) and cross-market attempts (400).
        setError(data.detail || 'Comparison failed.')
        setResult(null)
      } else {
        setResult(data)
      }
    } catch {
      setError('Failed to connect to Django server. Is it running?')
      setResult(null)
    }

    setLoading(false)
  }

  return (
    <div className="dashboard fade-in compare-page">
      <Link to="/" className="back-link compare-back">← Back to Dashboard</Link>

      <header className="dashboard-header compare-header">
        <div className="header-content">
          <h1 className="compare-title">⚖️ Compare Stocks</h1>
          <p className="subtitle">
            Live side-by-side metrics. Both stocks must trade in the same market —
            Indian with Indian, US with US.
          </p>
        </div>
      </header>

      <section className="card compare-controls">
        <form onSubmit={runComparison} className="compare-form">
          <div className="input-group compare-input">
            <label>Stock 1</label>
            <input
              className="input-field"
              value={ticker1}
              onChange={(e) => setTicker1(e.target.value)}
              placeholder="e.g. TCS"
            />
          </div>
          <span className="compare-vs">VS</span>
          <div className="input-group compare-input">
            <label>Stock 2</label>
            <input
              className="input-field"
              value={ticker2}
              onChange={(e) => setTicker2(e.target.value)}
              placeholder="e.g. INFY"
            />
          </div>
          <button type="submit" className="btn btn-primary compare-submit" disabled={loading}>
            {loading ? 'Fetching…' : 'Compare'}
          </button>
        </form>

        <div className="compare-presets">
          {PRESETS.map((group) => (
            <div key={group.market} className="preset-group">
              <span className="preset-market">{group.market}</span>
              {group.pairs.map(([a, b]) => (
                <button
                  key={`${a}-${b}`}
                  type="button"
                  className="preset-chip"
                  onClick={() => runComparison(null, a, b)}
                  disabled={loading}
                >
                  {a} vs {b}
                </button>
              ))}
            </div>
          ))}
        </div>
      </section>

      {error && (
        <section className="card-static compare-error">
          <span className="compare-error-icon">⚠️</span>
          <p>{error}</p>
        </section>
      )}

      {loading && (
        <section className="card-static compare-loading">
          <div className="spinner"></div>
          <p>Fetching live data for both stocks…</p>
        </section>
      )}

      {result && !loading && (
        <>
          <section className="card-static compare-verdict-bar">
            <span className="badge badge-completed">{result.market} · {result.currency_code}</span>
            <p className="compare-verdict">{result.verdict}</p>
          </section>

          <section className="card-static compare-table-wrap">
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th className="col-left">
                    {result.left.symbol}
                    <span className="col-company">{result.left.company_name}</span>
                  </th>
                  <th className="col-right">
                    {result.right.symbol}
                    <span className="col-company">{result.right.company_name}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="metric-name">Exchange</td>
                  <td>{result.left.exchange || '—'}</td>
                  <td>{result.right.exchange || '—'}</td>
                </tr>
                <tr>
                  <td className="metric-name">Sector</td>
                  <td>{result.left.sector || '—'}</td>
                  <td>{result.right.sector || '—'}</td>
                </tr>
                {result.rows.map((row) => (
                  <tr key={row.key}>
                    <td className="metric-name">{row.label}</td>
                    <td className={row.better === 'left' ? 'cell-better' : ''}>
                      {formatCell(row, 'left', result.currency)}
                      {row.better === 'left' && <span className="better-tick">✓</span>}
                    </td>
                    <td className={row.better === 'right' ? 'cell-better' : ''}>
                      {formatCell(row, 'right', result.currency)}
                      {row.better === 'right' && <span className="better-tick">✓</span>}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td className="metric-name">Risk Level</td>
                  <td className={`risk-${result.left.risk.toLowerCase()}`}>{result.left.risk}</td>
                  <td className={`risk-${result.right.risk.toLowerCase()}`}>{result.right.risk}</td>
                </tr>
                <tr>
                  <td className="metric-name">Analyst Consensus</td>
                  <td><span className={`badge verdict-${result.left.recommendation.toLowerCase()}`}>{result.left.recommendation}</span></td>
                  <td><span className={`badge verdict-${result.right.recommendation.toLowerCase()}`}>{result.right.recommendation}</span></td>
                </tr>
              </tbody>
            </table>
            <p className="compare-footnote">
              ✓ marks the stronger value. Price and market cap aren't scored — bigger
              isn't better. Data from Yahoo Finance; not investment advice.
            </p>
          </section>
        </>
      )}
    </div>
  )
}

export default Compare
