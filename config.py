from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    app_name: str = "AI Photo Editor"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash-vision-exp"

    # 存储
    upload_dir: str = "uploads"
    output_dir: str = "outputs"

    # Redis（Celery 用）
    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()