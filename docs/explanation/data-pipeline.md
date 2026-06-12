# Data Pipeline: End-to-End Data Flow

This document explains how data flows through the system: from external APIs
into SQLite, from the database through the API layer to the React frontend,
and how each layer handles failures.

## 1. Overview

```
External APIs ──→ Collectors ──→ SQLite DB ──→ FastAPI ──→ React UI
                     ↑                              ↑
               Scheduler (APScheduler)          Cache layer
```

The system has **5 data collection layers**, each with a different cadence:

| Layer | Cadence | What | Source |
|---|---|---|---|
| L0: Real-time | Every 15 min | Stock prices, PE_TTM, market cap | Tencent / Naver / yfinance / akshare |
| L1: Industry | Every 6/18 hr | Industry indicators (14 sources) | Web scraping + fallback data |
| L2: Financial | Every 7/19 hr | Income statement data | yfinance (via refresh_company_data) |
| L3: Macro | On trigger | GDP, CPI, unemployment, yield curve | FRED API |
| L4: Historical | One-time (backfill) | 3-year adjusted prices | Tencent K-line / yfinance / akshare |

## 2. Price Data Pipeline

This is the most latency-sensitive pipeline, serving the Dashboard price charts
and Portfolio tracking.

```

                    ┌─────────────────────────────────────┐
                    │        get_price_history_cached     │
                    │         (price_data.py:937)          │
                    └─────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                        ▼
            Live fetch (priority)      Cache read (fallback)
                    │                        │
         ┌──────────┼──────────┐              │
         ▼          ▼          ▼              │
    Tencent    akshare    yfinance             │
    K-line     (A/HK)    (global)             │
         │          │          │              │
         └──────────┴──────────┴──────┬───────┘
                                      ▼
                              _write_to_cache()
                              (overwrite=False)
                                      │
                                      ▼
                              PriceCache table
                              (SQLite, per ticker)
                                      │
                              backfill_market_data()
                                      │
                                      ▼
                              MarketData table
                              (SQLite, per company_id)
```

**Key design decisions:**

- **"Live first, cache second"**: Every API call tries the live source first.
  On success, it writes to cache. On failure, it reads from cache. This ensures
  data is always as fresh as possible.
- **`overwrite=False`** (default for `_write_to_cache`): Protects first-successful
  data from being overwritten by a later, potentially rate-limited, partial response.
- **Incremental backfill** (`incremental_backfill_prices`): On every scheduled
  company refresh, checks each ticker's latest cache date and fetches only the
  gap. If a ticker has no data, falls back to a full 3-year fetch.

**Data source priorities per market:**

| Market | Priority 1 | Priority 2 | Priority 3 |
|---|---|---|---|
| US stocks | Tencent API | yfinance | Cache |
| A-shares | akshare | yfinance | Cache |
| Hong Kong | akshare (HK stocks) | yfinance | Cache |
| Korea | FinanceDataReader | yfinance | Cache |

## 3. Industry Data Pipeline

The industry collectors instrument key supply-chain indicators. They use a
`BaseCollector` base class that provides idempotency (dedup by date) and
auto-change-computation.

```

            ┌─────────────────────────────────────┐
            │    auto_collect_and_analyze()        │
            │    (scheduler.py, 6:00 / 18:00)      │
            └─────────────────────────────────────┘
                         │
                         ▼
            ┌─────────────────────────┐
            │  collect_all(db)        │
            │  (industry_collector)   │
            └─────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         TSMC IR    TrendForce   WSTS/SIA    ... (20+ collectors)
              │          │          │
              ▼          ▼          ▼
         hardcoded   hardcoded   hardcoded
         fallback    fallback    fallback
              │          │          │
              └──────────┴──────────┘
                         │
                         ▼
            IndicatorObservation table
                         │
                         ▼
            TimelineEvent created
                         │
                         ▼
            batch_analyze_industry_impact()
            (DeepSeek AI → industry/chain/company impact)
```

**Note**: Most collectors attempt live web scraping first. When scraping fails
(typical for Chinese government sites and some corporate IR pages), they fall
back to hardcoded known values (e.g., Q2 2026 estimates). The `safe_collect()`
wrapper ensures NO collector crash propagates to the scheduler.

## 4. Financial Data Pipeline

```
    ┌────────────────────────────────────┐
    │  refresh_company_financials()      │
    │  (scheduler.py, 7:00 / 19:00)     │
    └────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    Tencent    yfinance     akshare
    (price)    (revenue,    (A-share
               net income,   price)
               PE, mcap)
        │           │           │
        └───────────┴───────────┘
                    │
                    ▼
          StockInfoCache table
          (data_json: {revenue_b, pe_ttm, ...})
                    │
                    ▼
             Financial table
          (per company, per fiscal_year)
```

Revenue data (`revenue_b` in `StockInfoCache.data_json`) is stored in units of
亿 (100M = 100 million USD). When served via the API, it is divided by 10 to
convert to B (billions USD = 十亿). The frontend multiplies by 10 for display
in `亿` units.

## 5. Macro Data Pipeline

```
    ┌────────────────────────────────────┐
    │      macro_collector.py            │
    │      (data_pipeline/)              │
    └────────────────────────────────────┘
                    │
                    ▼
              FRED API
              (50+ series:
               GDP, CPI, UNRATE,
               DGS10, DGS2, ...)
                    │
                    ▼
           KeyIndicator + IndicatorObservation
           (same tables as industry data)
```

The macro collector is **not on a schedule** — it must be triggered manually
or via a one-off script. It writes into the same `KeyIndicator`/`IndicatorObservation`
tables used by industry collectors, so the AI analysis pipeline applies to
macro indicators as well.

## 6. Cache Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        SQLite Database                        │
│                                                              │
│  PriceCache          StockInfoCache      IndicatorObservation │
│  ┌──────────┐       ┌──────────┐       ┌──────────────────┐  │
│  │ ticker   │       │ ticker   │       │ indicator_id     │  │
│  │ date     │       │ data_json│       │ date             │  │
│  │ price    │       │ (JSON)   │       │ value            │  │
│  │ volume   │       └──────────┘       │ analysis (AI)    │  │
│  │ source   │                          └──────────────────┘  │
│  └──────────┘                                                │
│                                                              │
│  MarketData (denormalized for fast chart queries)            │
│  ┌─────────────────────────────────────┐                     │
│  │ company_id │ date │ stock_price     │                     │
│  │ volume     │ market_cap             │                     │
│  └─────────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

## 7. Failure Modes and Recovery

| Failure | Symptom | Recovery |
|---|---|---|
| yfinance rate limit | `All data sources exhausted for TICKER` | Next scheduled refresh retries automatically |
| akshare disconnected | `RemoteDisconnected` | Next refresh retries; cache serves stale data |
| DeepSeek 402 (no balance) | `Insufficient Balance` | Recharge DeepSeek account, retry by calling batch-analyze endpoint |
| Tencent API timeout | All Tencent calls fail | Falls through to yfinance → cache |
| Collector scrape fails | Hardcoded fallback values used | No action needed; data is approximate |
| FRED key missing | Macro indicators empty | Set `FRED_API_KEY` env var and re-trigger |

## Related

- [Data sources explanation](data-sources.md) — external API details by source
- [Architecture overview](architecture.md) — system components and design principles
- [Deployment guide](../how-to/deploy.md) — production deployment with Zeabur
