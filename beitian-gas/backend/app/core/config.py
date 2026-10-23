from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")
    import_storage_dir: Path = Path(__file__).resolve().parents[3] / "work" / "imports"
    serve_frontend: bool = False
    web_dist_dir: Path = Path(__file__).resolve().parents[3] / 'frontend' / 'dist'
    database_url: str  # 必填，不内置数据库凭据
    cors_origins: list[str] = ["http://localhost:5173"]

@lru_cache
def get_settings() -> Settings:
    return Settings()
