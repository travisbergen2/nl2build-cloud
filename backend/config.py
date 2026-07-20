from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration"""

    database_url: str = "postgresql://nl2build:nl2build@localhost:5432/nl2build"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "nl2build-artifacts"

    openai_api_key: Optional[str] = None
    llm_model: str = "gpt-4-turbo-preview"

    kms_provider: str = "mock"

    app_name: str = "NL2Build Cloud"
    app_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
