import pytest
import pytest_asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.main import app
from app.db.base import Base
from app.deps import get_db
from app.core.rate_limit import RateLimiter
from app.core.redis import close_redis_client
from app.analysis.routes import analysis_limit
from app.analysis.store import AnalysisStore, get_store, ROOT

# Provide a specific testing database URL, preferably an asyncpg one
# In a real environment, you'd want to drop/create a test DB here.
# For simplicity, we assume TEST_DB_URL is provided, or fallback to default
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    raise RuntimeError("Set TEST_DATABASE_URL to an isolated PostgreSQL database ending in _test.")
if not make_url(TEST_DB_URL).database.endswith("_test"):
    raise RuntimeError("Refusing to reset a database whose name does not end in _test.")

# Re-use engine per test session to avoid overhead
# pytest-asyncio may allocate a distinct event loop for each test. A pooled
# asyncpg connection is bound to its creating loop, so tests need fresh ones.
engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=AsyncSession)

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_test_db():
    test_url = make_url(str(TEST_DB_URL))
    if not test_url.database or not test_url.database.replace("_", "").isalnum():
        raise ValueError("TEST_DB_URL must use an alphanumeric database name.")
    admin_engine = create_async_engine(test_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_url.database})
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    await admin_engine.dispose()
    async with engine.begin() as conn:
        # Note: In a real TimescaleDB test setup, you should execute create_hypertable manually 
        # or run Alembic migrations instead of create_all. For unit tests here, create_all works for basic schemas 
        # minus the timescaledb specific features if the extension is not installed. 
        # We drop all tables for clean slate.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(setup_test_db) -> AsyncSession:
    async with TestingSessionLocal() as session:
        await session.execute(text("TRUNCATE users, stocks, candles, refresh_tokens RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    # Business-flow tests opt out explicitly; dedicated tests exercise real Redis limits.
    async def no_limit(self, request: Request):
        return None
    async def no_analysis_limit():
        return None
    app.dependency_overrides[analysis_limit] = no_analysis_limit
    
    transport = ASGITransport(app=app)
    try:
        with patch.object(RateLimiter, "__call__", no_limit):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        await close_redis_client()


@pytest.fixture
def research_store():
    with tempfile.TemporaryDirectory() as directory:
        store = AnalysisStore(Path(directory) / "research.sqlite3")
        store.import_csv("RELIANCE", (ROOT / "data/indian_daily/RELIANCE.csv").read_bytes())
        previous = app.dependency_overrides.get(get_store)
        app.dependency_overrides[get_store] = lambda: store
        yield store
        if previous is None:
            app.dependency_overrides.pop(get_store, None)
        else:
            app.dependency_overrides[get_store] = previous
