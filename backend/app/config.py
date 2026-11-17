from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    gov_api_resource_id: str = "053cea08-09bc-40ec-8f7a-156f0677aff3"
    redis_cache_ttl_seconds: int = 86400

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
