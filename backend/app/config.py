from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    gov_api_resource_id: str = "053cea08-09bc-40ec-8f7a-156f0677aff3"          # vehicle registry (data.gov.il)
    gov_recalls_resource_id: str = "36bf1404-0be4-49d2-82dc-2f1ead4a8b93"      # vehicles with open recalls (data.gov.il, Ministry of Transport)
    gov_garages_resource_id: str = "bb68386a-a331-4bbc-b668-bba2766d517d"      # licensed garages (data.gov.il, Ministry of Transport)
    redis_cache_ttl_seconds: int = 86400

    # Security (see app/security.py). Empty key = writing records is disabled. CORS origins are the dashboard's own addresses.
    records_write_key: str | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    write_rate_per_minute: int = 60
    chat_rate_per_minute: int = 15
    garages_rate_per_minute: int = 90
    max_maintenance_per_plate: int = 300
    max_inspections_per_plate: int = 60

    # Generative AI (SRS FR-4). Without a key the chat answers deterministically from the structured data.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 25.0

    # Garage ratings and opening hours (OPTIONAL, Google Places API New). Without a key the section works with the official register only.
    google_places_api_key: str | None = None
    google_places_daily_limit: int = 30            # hard stop per day (30 x 31 < the 1,000 free calls a month of the SKU; check the current price list)

    ml_artifacts_dir: Path = Path(__file__).resolve().parent / "ml" / "artifacts"
    # Calendar year used to compute vehicle age (override only in tests / reproducible demos)
    reference_year: int | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
