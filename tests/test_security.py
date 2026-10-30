import asyncio
import uuid
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from redis.asyncio import Redis
from starlette.requests import Request

from app.core.config import Settings, settings
from app.core.rate_limit import RateLimiter
from app.core.security import create_access_token, verify_password


def test_production_config_rejects_unsafe_defaults():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT="production")
    production = Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET_KEY="a" * 40,
                          DATABASE_URL=None, DB_PASSWORD="random-test-database-password-123",
                          COOKIE_SECURE=True, CORS_ORIGINS="https://stocks.example.com",
                          TRUSTED_HOSTS="stocks.example.com,localhost", FRONTEND_URL="https://stocks.example.com")
    assert production.CORS_ORIGINS == ["https://stocks.example.com"]


def test_database_url_and_escaped_password():
    assert Settings(_env_file=None, DATABASE_URL="postgresql+asyncpg://custom/db").async_database_url.endswith("custom/db")
    from sqlalchemy.engine import make_url
    config = Settings(_env_file=None, DATABASE_URL=None, DB_PASSWORD="a@:/%password")
    assert make_url(config.async_database_url).password == "a@:/%password"


def test_invalid_password_hash_returns_false():
    assert verify_password("password", "invalid-hash") is False


async def test_invalid_and_missing_bearer_tokens_return_401(client):
    assert (await client.get("/app/analysis/stocks")).status_code == 401
    token = create_access_token("not-a-uuid")
    assert (await client.get("/app/analysis/stocks", headers={"Authorization": f"Bearer {token}"})).status_code == 401
    missing_exp = jwt.encode({"sub": str(uuid.uuid4()), "type": "access"}, settings.JWT_SECRET_KEY, algorithm="HS256")
    assert (await client.get("/app/analysis/stocks", headers={"Authorization": f"Bearer {missing_exp}"})).status_code == 401


async def test_origin_and_host_guards(client):
    response = await client.post("/auth/logout", headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert response.headers["X-Request-ID"]
    assert (await client.get("/health/live", headers={"Host": "untrusted.example"})).status_code == 400


async def test_rate_limit_is_exact_and_atomic_under_concurrency():
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    path = f"/test-limit-{uuid.uuid4()}"
    request = Request({"type": "http", "method": "GET", "path": path, "headers": [], "client": ("127.0.0.1", 1)})
    limiter = RateLimiter(5, 60)
    async def attempt():
        try:
            await limiter(request)
            return 200
        except HTTPException as exc:
            assert exc.headers["Retry-After"] == "60"
            return exc.status_code
    try:
        with patch("app.core.rate_limit.get_redis_client", return_value=redis):
            results = await asyncio.gather(*(attempt() for _ in range(20)))
        assert results.count(200) == 5
        assert results.count(429) == 15
    finally:
        await redis.aclose()


async def test_inactive_user_cannot_login_or_refresh(client, db_session):
    from sqlalchemy import select
    from app.models.user import User
    await client.post("/auth/register", json={"email": "inactive@example.com", "name": "Inactive", "password": "password123"})
    login = await client.post("/auth/login", json={"email": "inactive@example.com", "password": "password123"})
    assert login.status_code == 200
    user = (await db_session.execute(select(User).where(User.email == "inactive@example.com"))).scalar_one()
    user.is_active = False
    await db_session.commit()
    assert (await client.post("/auth/login", json={"email": "inactive@example.com", "password": "password123"})).status_code == 401
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_authenticated_research_workflow_and_user_isolation(client, research_store):
    async def login(email):
        await client.post("/auth/register", json={"email": email, "name": "Researcher", "password": "password123"})
        response = await client.post("/auth/login", json={"email": email, "password": "password123"})
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    first = await login("first@example.com")
    dates = (await client.get("/app/analysis/stocks/RELIANCE/dates", headers=first)).json()
    prediction = await client.post("/app/analysis/predict", headers=first, json={"symbol": "RELIANCE", "as_of": dates[1]})
    assert prediction.status_code == 200
    prediction_id = prediction.json()["id"]
    assert (await client.post(f"/app/analysis/history/{prediction_id}/reveal", headers=first)).json()["available"]
    second = await login("second@example.com")
    assert (await client.get("/app/analysis/history", headers=second)).json() == []
    assert (await client.post(f"/app/analysis/history/{prediction_id}/reveal", headers=second)).status_code == 404
    assert len((await client.get("/app/analysis/history", headers=first)).json()) == 1
