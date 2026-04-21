from enum import Enum
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from crypto_bot.universe import normalize_symbol_list


def _find_env_file() -> Path | None:
    """Locate `.env` next to project root (walks up from this package)."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


_ENV_FILE = _find_env_file()


def resolved_env_file_path() -> Path | None:
    """Absolute path to `.env` if found next to the repo; else ``None`` (env vars only)."""
    return _ENV_FILE


class TradingProfile(str, Enum):
    DEV = "dev"
    PAPER = "paper"
    LIVE = "live"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRYPTO_BOT_",
        # Prefer repo `.env` even when the process cwd is elsewhere (common on Windows / IDEs).
        env_file=_ENV_FILE if _ENV_FILE is not None else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile: TradingProfile = TradingProfile.DEV
    live_confirm: str = "no"
    ml_model_path: Path | None = None
    ml_shadow: bool = False
    ml_enabled: bool = False

    data_dir: Path = Path("data/cache")
    journal_path: Path = Path("data/journal/trades.db")

    binance_api_key: str = ""
    binance_api_secret: str = ""

    dry_run: bool = False
    kill_switch: bool = False

    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_trading_enabled: bool = False

    snapshot_symbols: str = "BTC/USDT,SOL/USDT"

    position_size_pct_of_equity: float = 2.0
    ma_fast_period: int = 12
    ma_slow_period: int = 26
    rsi_period: int = 14
    rsi_buy_max: float = 45.0
    rsi_exit_min: float = 70.0

    @field_validator("live_confirm", mode="before")
    @classmethod
    def lower_confirm(cls, v: str) -> str:
        return str(v).strip().lower()

    @field_validator("ml_shadow", "dry_run", "kill_switch", "ml_enabled", "telegram_trading_enabled", mode="before")
    @classmethod
    def bool_env(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    @model_validator(mode="after")
    def normalize_snapshot_symbols(self) -> AppSettings:
        joined = ",".join(normalize_symbol_list(self.snapshot_symbols))
        object.__setattr__(self, "snapshot_symbols", joined)
        return self

    def live_allowed(self) -> bool:
        return (
            self.profile == TradingProfile.LIVE
            and self.live_confirm == "yes"
            and bool(self.binance_api_key)
            and bool(self.binance_api_secret)
        )

    def snapshot_symbol_list(self) -> list[str]:
        return normalize_symbol_list(self.snapshot_symbols)


def load_settings() -> AppSettings:
    return AppSettings()
