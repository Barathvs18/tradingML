# Deploy with Vercel and Render

This deployment hosts the React frontend on Vercel and the authenticated FastAPI
application, MongoDB, Redis-compatible Key Value, and persistent research
SQLite database on Render. Vercel forwards `/api/*` to Render so browser
requests and secure refresh cookies stay on the Vercel origin.

## 1. Deploy the API and data services on Render

1. Push this repository to GitHub.
2. In Render, create a **Blueprint** from that repository. The blueprint is
   `stock_prediction_api/render.yaml` (select the repository root that contains
   the `stock_prediction_api` folder).
3. Select the same region for the web service and Key Value. MongoDB Atlas is
   configured with your connection string.
4. Render asks for the values marked `sync: false`. Leave Google OAuth values
   empty unless you have configured a Google OAuth web client. Set:

   - `FRONTEND_URL`: your Vercel production URL, for example
     `https://algopredict.vercel.app`.
   - `CORS_ORIGINS`: the same exact HTTPS origin (no trailing slash).
   - `TRUSTED_HOSTS`: the Vercel hostname and Render API hostname, comma
     separated, for example `algopredict.vercel.app,algopredict-api.onrender.com`.
   - `MONGODB_URL`: your MongoDB Atlas connection string. Save it as a Render
     secret environment value, not in Git. Configure Atlas Network Access to
     accept Render connections.
   - `GOOGLE_REDIRECT_URI` (if enabling Google):
     `https://algopredict.vercel.app/api/auth/oauth/google/callback`.

5. Deploy and wait for Render health check `/api/health` to return HTTP 200.
   Copy the web service's actual `onrender.com` hostname.

The web service needs a paid Render plan for its persistent disk. Research data,
uploaded CSVs, models and prediction history are stored on the 5 GB disk mounted
at `/var/data`. MongoDB stores accounts, sessions, stocks and minute candles.
Render Key Value holds caches and rate limits. Keep one API instance because the
research SQLite store and automation scheduler are single-instance components.

## 2. Configure and deploy the frontend on Vercel

1. Create a Vercel project from the same repository.
2. Set the **Root Directory** to `stock_prediction_api/frontend`.
3. Use Vercel's Vite framework preset, with build command `npm run build` and
   output directory `dist`.
4. In `stock_prediction_api/frontend/vercel.json`, replace
   `https://YOUR-RENDER-SERVICE.onrender.com` with the Render hostname copied
   above. Commit and push the change.
5. Deploy. Add the final Vercel production domain to Render's `FRONTEND_URL`,
   `CORS_ORIGINS`, and `TRUSTED_HOSTS` if it differs from the initial URL, then
   redeploy the Render service.

The Vercel project must include `vercel.json` from the frontend root. Its
`/api/:path*` rewrite proxies API calls to Render; the remaining routes serve
the React SPA for client-side navigation.

## 3. Verify

- Open `https://YOUR_VERCEL_DOMAIN/` and create a user account.
- Sign in, open Analyze, then check History and Model Performance.
- Importing a CSV should report success; reload and confirm the dataset remains.
  - Verify `https://YOUR_VERCEL_DOMAIN/api/health` returns status `ok` with
  `db`, `redis`, and `research` set to `ok`.
- Verify Render's `/api/health/live` endpoint for process liveness.

The bundled daily market history ends in April 2021. This deployment does not
provide live market prices or place broker orders. Intraday analysis requires
fresh licensed minute-candle ingestion to be useful for current signals.
