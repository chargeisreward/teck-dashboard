# How to deploy the dashboard to Zeabur

Deploy the full-stack dashboard (FastAPI backend + React frontend) to Zeabur using the single Dockerfile, and configure persistent storage for the SQLite database.

## Prerequisites

- Zeabur CLI (`zeabur.exe`) downloaded and authenticated: `zeabur auth login`
- A Zeabur project already created (or create one with `zeabur project create`)
- `.env` file at the project root with:

  ```
  MINIMAX_API_KEY=your-minimax-api-key-here
  MINIMAX_BASE_URL=https://api.minimax.io/v1
  MINIMAX_MODEL=MiniMax-M3
  FRED_API_KEY=your-fred-key-here
  ```

## Step 1: Deploy via Dockerfile

Zeabur auto-detects the Dockerfile at the project root. Deploy from the project root:

```bash
zeabur deploy --project-id <project-id> --environment-id <env-id>
```

Or deploy to an existing service:

```bash
zeabur deploy --service-id <service-id> --environment-id <env-id>
```

The multi-stage Dockerfile will:
1. **Stage 1**: Build the frontend with `npm ci && npm run build`
2. **Stage 2**: Install Python deps (`pip install -r requirements.txt`), copy backend code, copy frontend `dist/` to `./static/`

## Step 2: Inject environment variables

The app requires these environment variables at runtime:

| Variable | Required? | Source |
|---|---|---|
| `MINIMAX_API_KEY` | Yes (for AI analysis) | .env file |
| `MINIMAX_BASE_URL` | Optional (defaults to `https://api.minimax.io/v1`) | .env file |
| `MINIMAX_MODEL` | Optional (defaults to `MiniMax-M3`) | .env file |
| `FRED_API_KEY` | Yes (for macro data) | .env file |
| `PORT` | Zeabur injects automatically | — |
| `DB_PATH` | Defaults to `/data/teck_dashboard.db` | Dockerfile |

Inject using the CLI:

```bash
zeabur variable env --service-id <id> --env-id <id> --file .env
```

The service needs a restart (or redeploy) for new env vars to take effect.

## Step 3: Mount a persistent volume

> ⚠️ Without a persistent volume, the SQLite database at `/data/teck_dashboard.db`
> **resets on every redeploy**, losing Follow data, price cache, and user changes.

**Dockerfile `VOLUME /data` does NOT work on Zeabur's Kubernetes platform.**
You must add a volume through the **Zeabur Dashboard**:

1. Open: `https://zeabur.com/projects/<project-id>/services/<service-id>?envID=<env-id>`
2. Click the **Volumes** tab
3. Click **Mount Volumes`
4. Volume ID: `data`
5. Mount Directory: `/data`
6. Save

On first mount, `/data` is empty. The `entrypoint.sh` script copies the seed database
(`/app/seed_db/teck_dashboard.seed`) into the volume automatically. On subsequent
deploys, the database persists across restarts.

## Step 4: Verify the deployment

```bash
curl https://<your-domain>.zeabur.app/api/dashboard/summary
```

Expected response: HTTP 200 with company/product counts.

Check the deployment logs:

```bash
zeabur deployment log --service-id <id> --env-id <env-id>
```

## Step 5: Trigger initial data backfill

After a fresh deploy, the database has only seed data. Trigger historical data collection:

```bash
# Backfill 3-year price history (runs ~2 min per ticker)
zeabur service exec --id <id> -- python3 -c "
from backfill_3y_prices import backfill_3y_prices, sync_market_data
backfill_3y_prices()
sync_market_data()
"
```

Scheduled tasks (industry collect at 6/18, price refresh every 15 min, company refresh
at 7/19) begin automatically after the first `init_scheduler()` call on app startup.

## Troubleshooting

**`502 Bad Gateway` on first deploy:**
The app runs startup migration synchronously. If it takes longer than Zeabur's health
check timeout, the load balancer returns 502. Wait 30s and retry.

**Database resets on redeploy:**
The `/data` volume is not mounted. Follow Step 3 above and re-deploy.

**MiniMax AI analysis fails:**
Check that `MINIMAX_API_KEY` is set:
```bash
zeabur variable list --id <id> --env-id <env-id>
```
Test the key: `curl https://api.minimax.io/v1/models -H "Authorization: Bearer $MINIMAX_API_KEY"`

## Related

- [Architecture overview](../explanation/architecture.md) — system design and data flow
- [Data source strategy](../explanation/data-sources.md) — external API integration
- [Configuration reference](../reference/configuration.md) — all environment variables
