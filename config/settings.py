from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    backend_api_key: str = "b86a9bd915faca17a7f7bd0bf5707163b971473b8f117725f9e9b040d93588e7"
    allowed_origins: list[str] = ["http://localhost:4200"]
    sec_subscription_key: str = "5544171ad4944dde9454d20054233891"
    google_spreadsheet_id: str = "1gc98SMT2mJOaKZC15JWxflZk_GASAW_1m72_Ex8CnFQ"
    google_service_account_json: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
