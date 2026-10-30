"""Local research app: no broker account, PostgreSQL or Redis needed."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.http import HTTPMiddleware

from app.analysis.routes import router, stream_router
from app.analysis.store import ROOT, get_store
from app.analysis.automation import run_automation_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(get_store().bootstrap)
    worker = asyncio.create_task(run_automation_worker())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Indian Stock AI Analyzer — Local Research", lifespan=lifespan)
app.add_middleware(HTTPMiddleware, allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                                                  "http://localhost:8000", "http://127.0.0.1:8000",
                                                  "http://127.0.0.1:8011"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])
app.include_router(router, prefix="/app")
app.include_router(stream_router, prefix="/app/analysis")


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "local", "database": "SQLite", "broker_required": False}


@app.get("/app/analysis/config")
async def configuration():
    return {"mode": "local", "authentication_required": False, "interval": "1d", "google_oauth_enabled": False}


DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    from fastapi import HTTPException
    if path.startswith(("app/", "auth/", "api/")):
        raise HTTPException(status_code=404, detail="Endpoint not available in local research mode.")
    if not DIST.is_dir():
        raise HTTPException(status_code=404, detail="Build the frontend with npm run build first.")
    candidate = (DIST / path).resolve()
    if candidate.is_relative_to(DIST.resolve()) and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(DIST / "index.html")
