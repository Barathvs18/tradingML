from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# --- Stock Schemas ---

class StockBase(BaseModel):
    symbol: str
    name: str
    exchange: str

class StockSearchResponse(BaseModel):
    items: List[StockBase]
    total: int

class StockDetail(StockBase):
    first_ts: Optional[datetime]
    last_ts: Optional[datetime]
    candle_count: int

# --- Candle Schemas ---

class CandleAgg(BaseModel):
    time: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: int

# --- Algorithm Schemas ---

class AlgorithmInfo(BaseModel):
    key: str
    name: str
    category: str
    description: str
    lookback_minutes: int
    default_params: Dict[str, Any]
    source: str = "reference"

class CategoryGroup(BaseModel):
    category: str
    algorithms: List[AlgorithmInfo]

# --- User Profile Schemas ---

class UserProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value

class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
