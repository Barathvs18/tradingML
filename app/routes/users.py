import uuid
from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_current_user
from app.db.mongo import update_user
from app.models.user import User
from app.schemas.app import UserProfileResponse, UserProfileUpdate
from app.core.rate_limit import RateLimiter

router = APIRouter(prefix="/user", tags=["users"])

@router.get("/{user_id}", response_model=UserProfileResponse, dependencies=[Depends(RateLimiter(60, 60))])
async def get_user_profile(user_id: uuid.UUID, current_user: User = Depends(get_current_user)):
    if str(current_user.id) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to access this profile")
    return current_user

@router.patch("/{user_id}", response_model=UserProfileResponse, dependencies=[Depends(RateLimiter(60, 60))])
async def update_user_profile(
    user_id: uuid.UUID, 
    update_data: UserProfileUpdate, 
    current_user: User = Depends(get_current_user)
):
    if str(current_user.id) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to modify this profile")
        
    current_user.name = update_data.name
    await update_user(current_user)
    
    return current_user
