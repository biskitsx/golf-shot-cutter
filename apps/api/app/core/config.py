from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_database: str = Field(alias="MONGODB_DATABASE")

    redis_url: str = Field(alias="REDIS_URL")

    r2_endpoint: str = Field(alias="R2_ENDPOINT")
    r2_access_key: str = Field(alias="R2_ACCESS_KEY")
    r2_secret_key: str = Field(alias="R2_SECRET_KEY")
    r2_bucket: str = Field(alias="R2_BUCKET")
    r2_region: str = Field(default="auto", alias="R2_REGION")

    jwt_secret: str = Field(min_length=32, alias="JWT_SECRET")
    jwt_issuer: str = Field(alias="JWT_ISSUER")
    jwt_ttl_seconds: int = Field(default=3600, alias="JWT_TTL_SECONDS")

    signed_url_ttl_seconds: int = Field(default=900, alias="SIGNED_URL_TTL_SECONDS")

    cors_origins: list[str] = Field(default_factory=list, alias="CORS_ORIGINS")
