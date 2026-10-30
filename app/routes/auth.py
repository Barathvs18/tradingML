from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import asyncio
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from pymongo.errors import DuplicateKeyError
from app.deps import get_current_user
from app.schemas.auth import RegisterRequest, LoginRequest, Token, OAuthExchangeRequest
from app.schemas.user import UserOut
from app.models.user import User
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token as new_refresh_token
from app.core.rate_limit import RateLimiter
from app.core.config import settings
from app.core.redis import get_redis_client
from app.db.mongo import get_database, find_user_by_email, find_user_by_id, insert_user, create_refresh_token as save_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

async def create_session(user_id, response: Response) -> str:
    access_token = create_access_token(user_id)
    raw_refresh_token = new_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await save_refresh_token({"_id": secrets.token_hex(16), "user_id": str(user_id),
        "token_hash": hash_token(raw_refresh_token), "expires_at": expires_at,
        "revoked": False, "created_at": datetime.now(timezone.utc), "replaced_by": None})
    response.set_cookie(key="refresh_token", value=raw_refresh_token, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="strict",
                        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
    return access_token

@router.post("/register", response_model=UserOut, dependencies=[Depends(RateLimiter(3, 60))])
async def register(request: RegisterRequest):
    if await find_user_by_email(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = await asyncio.to_thread(get_password_hash, request.password)
    user = User(
        email=request.email,
        name=request.name,
        password_hash=hashed_password
    )
    try:
        await insert_user(user)
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Email already registered") from exc
    return user

@router.post("/login", response_model=Token, dependencies=[Depends(RateLimiter(5, 60))])
async def login(request: LoginRequest, response: Response):
    user = await find_user_by_email(request.email)
    
    if not user or not user.is_active or not await asyncio.to_thread(verify_password, request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
        
    access_token = await create_session(user.id, response)
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/oauth/google/start")
async def google_oauth_start():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    state = secrets.token_urlsafe(32)
    params = {"client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": settings.GOOGLE_REDIRECT_URI,
              "response_type": "code", "scope": "openid email profile", "state": state, "prompt": "select_account"}
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")
    response.set_cookie("oauth_state", state, httponly=True, secure=settings.COOKIE_SECURE, samesite="lax", max_age=600)
    return response

@router.get("/oauth/google/callback")
async def google_oauth_callback(request: Request, code: str | None = None, state: str | None = None):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google OAuth is not configured")
    if not code or not state or not secrets.compare_digest(state, request.cookies.get("oauth_state", "")):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET, "redirect_uri": settings.GOOGLE_REDIRECT_URI, "grant_type": "authorization_code"})
        if token_response.is_error:
            raise HTTPException(status_code=401, detail="Google authorization failed")
        profile_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token_response.json()['access_token']}"})
    profile = profile_response.json()
    if profile_response.is_error or not profile.get("email") or not profile.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google did not provide a verified email")
    email = profile["email"].strip().lower()
    user = await find_user_by_email(email)
    if user and not user.is_active:
        raise HTTPException(401, "Account is inactive")
    if not user:
        user = User(email=email, name=profile.get("name") or email.split("@")[0], password_hash=await asyncio.to_thread(get_password_hash, secrets.token_urlsafe(32)))
        try:
            await insert_user(user)
        except DuplicateKeyError:
            user = await find_user_by_email(email)
    redirect = RedirectResponse(f"{settings.FRONTEND_URL}/oauth/callback?{urlencode({'code': secrets.token_urlsafe(32)})}")
    login_code = redirect.headers["location"].split("code=")[1]
    access_token = await create_session(user.id, redirect)
    redis = await get_redis_client()
    await redis.setex(f"oauth_login:{login_code}", 60, access_token)
    redirect.delete_cookie("oauth_state")
    return redirect

@router.post("/oauth/exchange", response_model=Token, dependencies=[Depends(RateLimiter(10, 60))])
async def oauth_exchange(payload: OAuthExchangeRequest):
    code = payload.code
    token = await (await get_redis_client()).getdel(f"oauth_login:{code}")
    if not token:
        raise HTTPException(status_code=401, detail="OAuth login has expired")
    return {"access_token": token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token, dependencies=[Depends(RateLimiter(20, 60))])
async def refresh(request: Request, response: Response):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    token_hash = hash_token(raw_token)
    new_raw_refresh = new_refresh_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_id = secrets.token_hex(16)
    outcome, db_token = await rotate_refresh_token(token_hash, {"_id": new_id,
        "user_id": "",
        "token_hash": hash_token(new_raw_refresh), "expires_at": expires_at, "revoked": False,
        "created_at": now, "replaced_by": None}, now)
    if outcome == "missing": raise HTTPException(status_code=401, detail="Invalid refresh token")
    if outcome == "reuse": raise HTTPException(status_code=401, detail="Token reuse detected. All sessions revoked.")
    if outcome == "expired": raise HTTPException(status_code=401, detail="Refresh token expired")
    user = await find_user_by_id(db_token["user_id"])
    if user is None or not user.is_active:
        raise HTTPException(401, "Account is inactive")
        
    # Rotate token
    user_id = user.id
    
    access_token = create_access_token(user_id)
    
    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(request: Request, response: Response):
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        token_hash = hash_token(raw_token)
        await get_database().refresh_tokens.update_one({"token_hash": token_hash}, {"$set": {"revoked": True}})
        
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out successfully"}

@router.post("/logout-all")
async def logout_all(
    response: Response, 
    current_user: User = Depends(get_current_user),
):
    await get_database().refresh_tokens.update_many({"user_id": str(current_user.id)}, {"$set": {"revoked": True}})
    response.delete_cookie("refresh_token")
    return {"detail": "All sessions revoked"}
