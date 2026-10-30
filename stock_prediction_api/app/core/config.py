from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator, Field
from typing import List, Any
from urllib.parse import urlparse

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "algopredict"
    TRUSTED_HOSTS: Any = ["localhost", "127.0.0.1", "test", "testserver"]
    REDIS_URL: str = "redis://localhost:6379/0"
    
    JWT_SECRET_KEY: str = "supersecretkey"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)
    # Local development uses HTTP; production deployments should set this to true.
    COOKIE_SECURE: bool = False
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/oauth/google/callback"
    FRONTEND_URL: str = "http://localhost:3000"
    
    CORS_ORIGINS: Any = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", "TRUSTED_HOSTS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            # Could be comma-separated or JSON array
            if v.startswith("["):
                import json
                return json.loads(v)
            return [i.strip() for i in v.split(",") if i.strip()]
        return v
    
    MODELS_DIR: str = "./models"
    DATA_DIR: str = "./data"

    @model_validator(mode="after")
    def validate_production(self):
        if self.JWT_ALGORITHM not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be an HMAC signing algorithm.")
        if self.ENVIRONMENT not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test or production.")
        if self.ENVIRONMENT == "production":
            if len(self.JWT_SECRET_KEY) < 32 or self.JWT_SECRET_KEY.startswith(("replace-", "generate_", "change-")):
                raise ValueError("Production requires a random JWT_SECRET_KEY of at least 32 characters.")
            if not self.MONGODB_URL or urlparse(self.MONGODB_URL).scheme not in {"mongodb", "mongodb+srv"}:
                raise ValueError("Production requires a MongoDB MONGODB_URL.")
            if not self.COOKIE_SECURE:
                raise ValueError("Production requires COOKIE_SECURE=true.")
            if not self.CORS_ORIGINS or any(not origin.startswith("https://") or "*" in origin for origin in self.CORS_ORIGINS):
                raise ValueError("Production CORS_ORIGINS must contain explicit HTTPS origins.")
            if not self.TRUSTED_HOSTS or "*" in self.TRUSTED_HOSTS:
                raise ValueError("Production requires explicit TRUSTED_HOSTS.")
            if not self.FRONTEND_URL.startswith("https://"):
                raise ValueError("Production FRONTEND_URL must use HTTPS.")
        return self
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
