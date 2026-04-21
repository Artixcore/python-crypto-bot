from enum import Enum
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingProfile(str, Enum):
    DEV = "dev"
    PAPER = "paper"
    LIVE = "live"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRYPTO_BOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile: TradingProfile = TradingProfile.DEV
    live_confirm: str = "no"
    ml_model_path: Path | None = None
    ml_shadow: bool = False

    data_dir: Path = Path("data/cache")
    journal_path: Path = Path("data/journal/trades.db")

    binance_api_key: str = ""
    binance_api_secret: str = ""

    dry_run: bool = False
    kill_switch: bool = False

    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8765
    dashboard_symbols: str = "BTC/USDT,ETH/USDT"
    dashboard_refresh_sec: int = 8

    @field_validator("live_confirm", mode="before")
    @classmethod
    def lower_confirm(cls, v: str) -> str:
        return str(v).strip().lower()

    @field_validator("ml_shadow", "dry_run", "kill_switch", mode="before")
    @classmethod
    def bool_env(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    def live_allowed(self) -> bool:
        return (
            self.profile == TradingProfile.LIVE
            and self.live_confirm == "yes"
            and bool(self.binance_api_key)
            and bool(self.binance_api_secret)
        )

    def dashboard_symbol_list(self) -> list[str]:
        return [s.strip() for s in self.dashboard_symbols.split(",") if s.strip()]


def load_settings() -> AppSettings:
    return AppSettings()
