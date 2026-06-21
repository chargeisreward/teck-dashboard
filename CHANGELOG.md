# Changelog

## 2026-06-12

### Added
- **Persistent volume support**: `zeabur.yaml` added to document volume configuration.
  `/data` now survives redeploys (requires Dashboard volume mount).
- **2025 revenue column** in Companies page (`Companies.jsx`): shows real-time 2025
  revenue from yfinance/Tencent, right-aligned with comma formatting.
- **Incremental price backfill** (`backfill_3y_prices.incremental_backfill_prices`):
  daily scheduler automatically fills gaps in historical price data without
  overwriting existing data.
- **Follow backup protection**: `startup_migration.py` now restores Follow data
  from `FOLLOW_BACKUP` environment variable, protecting user preferences across
  redeploys without persistent volume.
- **13 ticker backfill**: WDC, SNDK, AMKR, ASMIY, ATEYY, DELL, HPE, SIEGY, SMCI,
  SMI, TOELY, MPNGY, XIACF now have 3-year price history in `market_data`.
- `data_get.md`: comprehensive data sourcing documentation (60 KB).

### Fixed
- **"合计营收" title unit conversion**: was dividing by 100 instead of 10000.
  Displayed ~$423 trillion; now correctly shows ~$4.3 trillion.
- **Follow data lost on redeploy**: root cause was `/data` not mounted as persistent
  volume in Zeabur. Workaround: env var backup + automatic restore.
- **IndustryChain 1100-day default**: dead code path using magic number 1100.
  Standardized to 90 days (consistent with other pages).

### Changed
- **`_write_to_cache` signature**: new `overwrite=False` parameter. Default behavior
  changed from upsert to append-only, protecting first-successful data.
- **`scheduler.refresh_company_financials`**: now calls `incremental_backfill_prices`
  before `backfill_market_data` to fill price gaps each cycle.
- **`Dockerfile`**: added `VOLUME /data` declaration.
- **Frontend chart window**: `api.js` default days restored to 90 (was accidentally
  changed to 1100).
- **Env vars**: `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, `FRED_API_KEY` injected
  into Zeabur service via CLI (were missing after initial deploy).

### Database
- Seed database updated: 5.0 MB → 6.7 MB
- `market_data`: 28,368 → 36,960 rows
- `price_cache`: 34,821 rows (13 tickers added)
- Follows: NVDA, GOOGL, TSM, WDC, SNDK, ASML (6 companies)
