"""Configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "ATREIDES_", "env_file": ".env"}

    # Kalshi
    kalshi_api_base: str = "https://demo-api.kalshi.co/trade-api/v2"
    kalshi_key_id: str = ""
    kalshi_private_key_path: str = ""

    # Polymarket (future)
    polymarket_api_base: str = "https://clob.polymarket.com"
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_api_passphrase: str = ""

    # Risk
    max_position_per_market: int = 10  # dollars
    max_total_exposure: int = 50
    max_daily_loss: int = 20

    # Data
    data_dir: str = "data"
    poll_interval: float = 5.0  # seconds

    @property
    def is_demo(self) -> bool:
        return "demo" in self.kalshi_api_base


settings = Settings()
