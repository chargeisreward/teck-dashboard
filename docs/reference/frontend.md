# Frontend Reference

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 19 (Vite 8) |
| Routing | React Router 7 (`BrowserRouter`) |
| Charts | Recharts 3 (`LineChart`, `BarChart`, `AreaChart`) |
| HTTP | Native `fetch` via `api.js` |
| Build | Vite 8 (`vite build` → `frontend/dist/`) |
| Package | npm, managed via `frontend/package.json` |

## Project Structure

```
frontend/src/
├── api.js                     # All API client functions (50+)
├── App.jsx                    # Router + navigation sidebar
├── main.jsx                   # Entry point
├── index.css                  # Global styles (CSS variables)
├── data/
│   └── techGlossaryData.js    # Static tech glossary content
├── components/
│   ├── PriceTicker.jsx        # Live price display card
│   ├── HotStocksPanel.jsx     # A-share top gainers/losers
│   └── tech-glossary/
│       ├── LayerNav.jsx       # Tech stack sidebar navigation
│       └── LayerCard.jsx      # Tech layer detail cards
└── pages/
    ├── Dashboard.jsx          # Market overview (home)
    ├── PortfolioPage.jsx      # Portfolio tracking
    ├── IndustryChain.jsx      # Industry chain deep-dive
    ├── Companies.jsx          # Full company database
    ├── IndustryIntelligence.jsx  # Cross-section indicators
    ├── JudgmentLog.jsx        # Sequence timeline view
    ├── IndustryData.jsx       # Indicator data browser
    ├── CompanyData.jsx        # Company data browser
    ├── InvestmentPlan.jsx     # TSM+EWY allocation plan
    ├── TechGlossary.jsx       # AI tech stack encyclopedia
    ├── Scoring.jsx            # Quantitative scoring system
    ├── KeyIndicators.jsx      # Key market indicators
    └── Forecast.jsx           # Earnings forecast view
```

## Routing

Defined in `App.jsx`. Routes use `react-router-dom` with `NavLink` for active
state styling.

| Path | Component | Nav label |
|---|---|---|
| `/` | `Dashboard` | 市场概览 |
| `/portfolio` | `PortfolioPage` | 跟踪组合 |
| `/industry-chain` | `IndustryChain` | 产业链 |
| `/tech-glossary` | `TechGlossary` | 技术栈 |
| `/companies` | `Companies` | 龙头公司 |
| `/investment-plan` | `InvestmentPlan` | 配置方案 |
| `/industry-intelligence` | `IndustryIntelligence` | 产业情报-截面 |
| `/industry-intelligence/sequence` | `JudgmentLog` | 产业情报-序时 |
| `/industry-data` | `IndustryData` | 数据浏览-产业 |
| `/company-data` | `CompanyData` | 数据浏览-公司 |
| `/storage` | `TechGlossary` (re-map) | — |
| `*` | Redirect to `/` | — |

**Lazy-loaded routes** (via `React.lazy`): `TechGlossary`, `LayerNav`, `LayerCard`

## API Client Pattern

All API calls are centralized in `api.js`. Each function calls `fetchJSON(url)`,
which wraps `fetch()` with JSON parsing and error handling.

```js
const API_BASE = "/api";

function fetchJSON(url) {
  return fetch(url).then((r) => {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  });
}
// Two functions per endpoint: one that calls it, one for convenience
export function getCompanies() {
  return fetchJSON(`${API_BASE}/companies`);
}
```

The Vite dev server proxies `/api` to `http://localhost:8002`:

```js
// vite.config.js
server: { port: 5173, proxy: { "/api": { target: "http://localhost:8002", changeOrigin: true } } }
```

## Data Flow

```
User action → React component → api.js → fetch → Vite proxy → FastAPI
                                                              ↓
                                                         SQLAlchemy → SQLite
                                                              ↓
                                                     External API (Tencent/yfinance/Naver/akshare)
```

## State Management

No external state library. Each page manages its own state with `useState` and
`useEffect` hooks. Shared state (follows list) is fetched independently by each
page that needs it.

## Styling

Global CSS variables in `index.css`:

| Variable | Purpose |
|---|---|
| `--bg` | Page background |
| `--card-bg` | Card/surface background |
| `--text` | Primary text |
| `--text-secondary` | Muted text |
| `--border` | Borders and dividers |
| `--accent-blue` | Interactive / primary action |

Components use inline styles for layout and the `.card`, `.badge`, `.filter-bar`,
`.table-container` CSS classes for shared patterns.

## Charts

All charts use Recharts 3 with `ResponsiveContainer` for responsive sizing.

| Chart type | Used in | Data |
|---|---|---|
| `LineChart` | Dashboard, IndustryChain, IndustryIntelligence, PortfolioPage, InvestmentPlan | Price trends, normalized returns, indicator history |
| `BarChart` | Dashboard, IndustryChain, Scoring | Market cap, market share comparison, score rankings |
| `AreaChart` | InvestmentPlan | Price trend with gradient fill |
| `BarChart` (horizontal) | Scoring | Composite score ranking |

## Performance

- **15-minute auto-refresh**: Dashboard
- **5-minute auto-refresh**: IndustryChain details
- **Lazy loading**: TechGlossary page (large component tree)
- **Inline styles**: No CSS-in-JS library, avoids runtime style injection

## Related

- [API Reference](api.md) — all backend endpoints
- [Architecture overview](../explanation/architecture.md) — system data flow
- [Configuration Reference](configuration.md) — environment variables
