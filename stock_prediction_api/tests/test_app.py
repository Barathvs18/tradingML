import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_algorithm_routes(client: AsyncClient):
    # Register and login to get token
    await client.post("/auth/register", json={
        "email": "testapp@example.com",
        "name": "App User",
        "password": "password123"
    })
    login_resp = await client.post("/auth/login", json={
        "email": "testapp@example.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Test algorithms list
    resp = await client.get("/app/algorithms", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0  # Should have categories
    
    # Check if Supertrend is there
    found = False
    for cat in data:
        for algo in cat["algorithms"]:
            if algo["key"] == "supertrend":
                found = True
    assert found
    
    # 2. Test algorithm detail
    resp = await client.get("/app/algorithms/supertrend", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "SuperTrend"
    
    # 3. Test unknown algorithm
    resp = await client.get("/app/algorithms/unknown_algo", headers=headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_user_routes(client: AsyncClient):
    # Create two users
    await client.post("/auth/register", json={"email": "u1@example.com", "name": "U1", "password": "password123"})
    await client.post("/auth/register", json={"email": "u2@example.com", "name": "U2", "password": "password123"})
    
    login1 = await client.post("/auth/login", json={"email": "u1@example.com", "password": "password123"})
    login2 = await client.post("/auth/login", json={"email": "u2@example.com", "password": "password123"})
    
    t1 = login1.json()["access_token"]
    t2 = login2.json()["access_token"]
    
    import jwt
    from app.core.config import settings
    # Decode to get IDs
    id1 = jwt.decode(t1, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])["sub"]
    id2 = jwt.decode(t2, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])["sub"]
    
    # Test valid access
    h1 = {"Authorization": f"Bearer {t1}"}
    resp = await client.get(f"/app/user/{id1}", headers=h1)
    assert resp.status_code == 200
    assert resp.json()["name"] == "U1"
    
    # Test invalid access (403)
    resp = await client.get(f"/app/user/{id2}", headers=h1)
    assert resp.status_code == 403
    
    # Test valid update
    resp = await client.patch(f"/app/user/{id1}", headers=h1, json={"name": "U1 Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "U1 Updated"
