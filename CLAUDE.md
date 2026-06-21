# CLAUDE.md — Teck Dashboard Project Guide

## Data Source Priority

### Price / Market Data (Stock prices, PE, market cap)
1. **Tencent Finance API** (腾讯财经) — Primary for US/ADR stocks
2. **Naver API** — Primary for Korean stocks (SK Hynix, Samsung)
3. **yfinance** — Fallback for global stocks, limited rate (3s delay)
4. **akshare** — Fallback for Chinese A-shares (SMIC 688981)

No mock/random/synthetic data allowed. All prices must be adjusted for dividends/splits (复权).

### Financial Data (Revenue, PE, financial reports)
1. **Wind (万得)** — Only source for high-quality financial data. Usage-limited — batch wisely.
2. No fallback — if Wind unavailable, skip rather than use lower-quality sources for financials.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + SQLite (`backend/main.py`)
- **Frontend**: React 19 + Vite 8 + Recharts (`frontend/src/`)
- **Scheduler**: APScheduler in `backend/scheduler.py` — daily 6/14/22 collects, 7/19 refreshes prices
- **Collectors**: Industry data collectors in `backend/industry_collector/sources/`
- **AI**: MiniMax-M3 in `backend/ai_analysis.py`
- **Docker**: Multi-stage build, single `Dockerfile`, Zeabur deployment

## Key Files

- `backend/main.py` — All API endpoints
- `backend/models.py` — DB models
- `backend/schemas.py` — Pydantic schemas
- `backend/price_data.py` — Price fetching with fallback chain
- `backend/refresh_company_data.py` — Company data refresh logic
- `backend/industry_collector/__init__.py` — Collector registry
- `backend/indicator_map.py` — Indicator → ticker mapping
- `backend/backfill_market_data.py` — MarketData table backfill from PriceCache

## DB Tables

- **PriceCache** — Historical price time series (per ticker, raw)
- **MarketData** — Historical prices mapped to company_id (for charts)
- **StockInfoCache** — Current price/PE/mcap JSON blobs (per ticker)
- **Financial** — Company financials (fiscal_year, revenue, pe_ttm)
- **IndicatorObservation** — Industry indicator observations (from collectors)

## Important Rules

- No mock/synthetic/seed data
- Use Wind only for financial data (not prices)
- Price priority: Tencent → Naver → yfinance → akshare
- Prefer editing existing files; avoid unnecessary new files
