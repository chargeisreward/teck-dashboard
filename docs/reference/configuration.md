# Configuration Reference

All configuration for the AI chip dashboard is done through environment variables.
No configuration files are used at runtime.

## Environment Variables

### Required

| Variable | Default | Used in | Purpose |
|---|---|---|---|
| `MINIMAX_API_KEY` | — | `ai_analysis.py:15` | Authentication for MiniMax API (AI analysis generation) |
| `FRED_API_KEY` | — | `data_pipeline/macro_collector.py:40` | Authentication for FRED (Federal Reserve) macro-economic data API |

### Optional

| Variable | Default | Used in | Purpose |
|---|---|---|---|
| `MINIMAX_BASE_URL` | `https://api.minimax.io/v1` | `ai_analysis.py:16` | Base URL for MiniMax OpenAI-compatible API |
| `MINIMAX_MODEL` | `MiniMax-M3` | `ai_analysis.py:17` | MiniMax model ID used for AI analysis |
| `DB_PATH` | `./teck_dashboard.db` | `database.py:6`, `entrypoint.sh:7` | SQLite database file path. In production (Docker): `/data/teck_dashboard.db` |
| `PORT` | `8080` | `entrypoint.sh:27` | HTTP listen port for uvicorn. Zeabur injects `PORT=8080` automatically |
| `PYTHON_VERSION` | `3.11.15` | Dockerfile (build arg) | Python runtime version for Docker builds |

### Zeabur-injected (read-only)

These variables are set automatically by the Zeabur platform and are available
inside the container at runtime. They should NOT be set manually.

| Variable | Purpose |
|---|---|
| `ZEABUR=1` | Indicator that the app runs inside Zeabur |
| `ZEABUR_PROJECT_ID` | Zeabur project UUID |
| `ZEABUR_SERVICE_ID` | Zeabur service UUID |
| `ZEABUR_ENVIRONMENT_ID` | Zeabur environment UUID |
| `ZEABUR_REGION` | Deployment region identifier |
| `ZEABUR_USER_ID` | Zeabur account UUID |
| `ZEABUR_WEB_URL` | Public URL of the deployed service |
| `ZEABUR_WEB_DOMAIN` | Public domain of the deployed service |
| `KUBERNETES_SERVICE_HOST` | Kubernetes cluster internal DNS |

### Legacy / Unused

| Variable | Notes |
|---|---|
| `WIND_API_KEY` | Defined in old `.env` templates, not read by current code |
| `WIND_BASE_URL` | Referenced in Wind skill configuration, not in the app itself |

## .env file (local development)

The `.env` file at the project root is loaded by the Docker build process and
available to the FastAPI app via `os.getenv()`. It is gitignored and should
never be committed.

Template: `.env.example`

```
MINIMAX_API_KEY=sk-your-key-here
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_MODEL=MiniMax-M3
```

## Docker build arguments

Defined in `Dockerfile`:

| Arg | Value | Purpose |
|---|---|---|
| `node:20-alpine` | Stage 1 base image | Frontend build environment |
| `python:3.11-slim` | Stage 2 base image | Backend runtime environment |
| `PORT` | `8080` | Container listen port |

## Zeabur service configuration

The optional `zeabur.yaml` file at the project root documents the intended
service configuration, but is **not auto-applied** to existing services.

```yaml
apiVersion: zeabur.com/v1
kind: Template
metadata:
  name: teck-dashboard
spec:
  services:
    - name: t
      spec:
        volumes:
          - id: data
            dir: /data
```

## Related

- [Deployment guide](../how-to/deploy.md) — Zeabur deployment walk-through
- [Database reference](database.md) — all tables and their schema
- [API reference](api.md) — all REST endpoints
