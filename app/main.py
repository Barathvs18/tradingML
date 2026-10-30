import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from app.core.http import HTTPMiddleware
from app.core.rate_limit import RateLimiter
from app.core.config import settings
from app.core.redis import close_redis_client, get_redis_client
from app.routes import auth, stocks, algorithms, users, predict
from app.db.mongo import connect_mongo, close_mongo, get_database
from app.analysis.routes import router as analysis_router, stream_router as analysis_stream_router, analysis_owner, analysis_limit
from app.analysis.store import get_store
from app.analysis.automation import run_automation_worker
from app.deps import get_current_user
from app.models.user import User
import asyncio

from app.algorithms.registry import load_manifest_registry
from app.algorithms.pretrained import load_all_pretrained, LOADED_MODELS
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_mongo()
    # Redis is retained for ephemeral caches and distributed request limits.
    await (await get_redis_client()).ping()
    
    # 3. Load Pretrained Models
    try:
        load_all_pretrained()
        load_manifest_registry()
        logger.info(f"Loaded {len(LOADED_MODELS)} pretrained models.")
    except Exception as e:
        logger.error(f"FATAL: Failed to load pretrained models: {e}")
        raise e

    await asyncio.to_thread(get_store().bootstrap)
    automation_worker = asyncio.create_task(run_automation_worker())
    try:
        yield
    finally:
        automation_worker.cancel()
        try:
            await automation_worker
        except asyncio.CancelledError:
            pass
        await close_redis_client()
        await close_mongo()

root_path = os.environ.get("ROOT_PATH", "")

app = FastAPI(title="Stock Prediction API", lifespan=lifespan, root_path=root_path,
              docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
              redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
              openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Cache", "Retry-After"],
)
app.add_middleware(HTTPMiddleware, allowed_origins=settings.CORS_ORIGINS)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

app.include_router(auth.router)
app.include_router(stocks.router, prefix="/app")
app.include_router(algorithms.router, prefix="/app")
app.include_router(users.router, prefix="/app")
app.include_router(predict.router, prefix="/app")


async def authenticated_analysis_owner(user: User = Depends(get_current_user)) -> str:
    return str(user.id)


app.dependency_overrides[analysis_owner] = authenticated_analysis_owner
app.include_router(analysis_router, prefix="/app", dependencies=[Depends(RateLimiter(60, 60))])
app.include_router(analysis_stream_router, prefix="/app/analysis")

async def authenticated_analysis_limit(request: Request):
    if request.url.path.endswith("/import"):
        await RateLimiter(3, 300)(request)
    elif request.url.path.endswith("/predict"):
        await RateLimiter(20, 60)(request)


app.dependency_overrides[analysis_limit] = authenticated_analysis_limit


@app.get("/app/analysis/config")
async def analysis_configuration():
    return {"mode": "authenticated", "authentication_required": True, "interval": "1d",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)}


@app.get("/health/live")
async def liveness():
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    health_status = {"status": "ok", "db": "unknown", "redis": "unknown", "research": "unknown"}
    
    # Check DB
    try:
        await get_database().command("ping")
        health_status["db"] = "ok"
    except Exception:
        health_status["db"] = "unavailable"
        health_status["status"] = "degraded"
        
    # Check Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        health_status["redis"] = "ok"
    except Exception:
        health_status["redis"] = "unavailable"
        health_status["status"] = "degraded"
        
    try:
        await asyncio.to_thread(get_store().health)
        health_status["research"] = "ok"
    except Exception:
        health_status["research"] = "unavailable"
        health_status["status"] = "degraded"
    return JSONResponse(health_status, status_code=200 if health_status["status"] == "ok" else 503)
