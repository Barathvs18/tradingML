# Production operations

The current production deployment is the Vercel and Render setup described in
[DEPLOY_VERCEL_RENDER.md](DEPLOY_VERCEL_RENDER.md). The API stores accounts,
refresh sessions, stocks and minute candles in MongoDB. Supply `MONGODB_URL` as a
secret in Render; never commit the connection string. The Render Key Value service
stores caches, OAuth exchange codes and distributed rate limits. SQLite research
uploads, strategy state and prediction histories use the Render persistent disk.

## Required production configuration

Render sets `ENVIRONMENT=production`, `COOKIE_SECURE=true`, a generated
`JWT_SECRET_KEY`, and `ROOT_PATH=/api` from `render.yaml`. Set `MONGODB_URL`,
`FRONTEND_URL`, `CORS_ORIGINS`, and `TRUSTED_HOSTS` in the Render dashboard. The
frontend URL and CORS origin must be the exact Vercel HTTPS origin. Trusted hosts
must include the Vercel and Render hostnames. Add Render's outbound access to your
MongoDB provider's network allowlist.

Vercel rewrites `/api/*` to the Render API origin. Its destination is configured
in `frontend/vercel.json`; replace the placeholder with the actual Render
hostname after the service has been created.

## Persistence and scaling

Keep one API instance. SQLite research storage and the automation scheduler are
single-instance components. The persistent disk mounted at `/var/data` stores
research uploads, strategy data, paper portfolio state, and prediction history.
MongoDB stores users, refresh token records, stock metadata, and candles. Back up
the MongoDB database using your MongoDB provider's backup facility, and separately
back up the Render persistent disk. Redis-compatible Key Value data is ephemeral.

The bundled daily market history ends in April 2021. The application does not
fetch live prices or submit broker orders. Current intraday analysis requires a
licensed data feed and fresh candle ingestion.

## Health and verification

- `GET /api/health/live` checks API process liveness.
- `GET /api/health` checks MongoDB, Redis-compatible Key Value and research disk.
- After deployment, register a user, sign in, import a CSV, reload, and confirm
  that the dataset and history remain available.

Before deployment, run the Python research suite and frontend checks from
`README.md`. The legacy PostgreSQL integration test scaffold is no longer used by
the MongoDB-backed application and must not be used as a deployment gate.
