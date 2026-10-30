import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
async def registered_user(client, request):
    if request.node.name != "test_register":
        response = await client.post("/auth/register", json={"email": "test@example.com", "name": "Test User", "password": "password123"})
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "name": "Test User",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data
    assert "password_hash" not in data

@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "name": "Test User 2",
        "password": "password123"
    })
    assert response.status_code == 400
    assert "Email already registered" in response.text

@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in response.cookies

@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient):
    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    # 1. Login to get token
    login_resp = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert "refresh_token" in login_resp.cookies
    refresh_cookie = login_resp.cookies["refresh_token"]
    
    # 2. Call refresh
    refresh_resp = await client.post("/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in refresh_resp.cookies
    new_refresh_cookie = refresh_resp.cookies["refresh_token"]
    
    # The new token should be different
    assert refresh_cookie != new_refresh_cookie

@pytest.mark.asyncio
async def test_refresh_token_reuse_detection(client: AsyncClient):
    # 1. Login to get token
    login_resp = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    first_refresh = login_resp.cookies["refresh_token"]
    
    # 2. Use it once
    refresh_resp_1 = await client.post("/auth/refresh", cookies={"refresh_token": first_refresh})
    assert refresh_resp_1.status_code == 200
    
    # 3. Use it again (reuse detection should trigger)
    refresh_resp_2 = await client.post("/auth/refresh", cookies={"refresh_token": first_refresh})
    assert refresh_resp_2.status_code == 401
    assert "Token reuse detected" in refresh_resp_2.text
