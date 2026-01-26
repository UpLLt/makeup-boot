"""Configuration loader."""
import os
from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from environment."""

    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")

    db_host: str = Field("127.0.0.1", env="DB_HOST")
    db_port: int = Field(3306, env="DB_PORT")
    db_user: str = Field("root", env="DB_USER")
    db_password: str = Field("root", env="DB_PASSWORD")
    db_name: str = Field("makeup_boot", env="DB_NAME")

    makeup_api_base_url: str = Field("http://localhost:8080", env="MAKEUP_API_BASE_URL")
    makeup_api_timeout: int = Field(10, env="MAKEUP_API_TIMEOUT")
    makeup_api_max_retries: int = Field(3, env="MAKEUP_API_MAX_RETRIES")

    daily_user_count: int = Field(10, env="DAILY_USER_COUNT")
    concurrency_per_slot: int = Field(5, env="CONCURRENCY_PER_SLOT")
    slot_minutes: int = Field(10, env="SLOT_MINUTES")

    default_face_image_url: str = Field("https://example.com/face.jpg", env="DEFAULT_FACE_IMAGE_URL")

    openai_base_url: str = Field("https://api.openai.com/v1", env="OPENAI_BASE_URL")
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")

    # Cloudflare R2 配置
    cf_r2_endpoint: str = Field(default="", env="CF_R2_ENDPOINT")
    cf_r2_bucket: str = Field(default="", env="CF_R2_BUCKET")
    cf_r2_access_key_id: str = Field(default="", env="CF_R2_ACCESS_KEY_ID")
    cf_r2_secret_access_key: str = Field(default="", env="CF_R2_SECRET_ACCESS_KEY")
    cf_r2_domain: str = Field(default="img.healthpalfit.com", env="CF_R2_DOMAIN")

    class Config:
        # 支持通过 ENV_FILE 指定要加载的 env 文件，方便在本地/正式环境来回切换
        # - 默认：项目根目录 .env
        # - 可选：ENV_FILE=.env.local / .env.prod 等
        env_file = os.getenv("ENV_FILE") or str(Path(__file__).parent.parent / ".env")
        env_file_encoding = "utf-8"
        # 允许从环境变量和 .env 文件读取配置
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()

