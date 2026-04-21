from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from crypto_bot.config.settings import AppSettings, load_settings
from crypto_bot.dashboard.snapshot import build_snapshot
from crypto_bot.data.binance_client import BinanceSpotClient

logger = structlog.get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _make_client(settings: AppSettings) -> BinanceSpotClient:
    return BinanceSpotClient(
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    client = _make_client(settings)
    ex = client.exchange
    logger.info("dashboard_loading_markets")
    try:
        ex.load_markets()
    except Exception as e:
        logger.warning("dashboard_load_markets_failed", error=str(e))
    app.state.settings = settings
    app.state.exchange = ex
    yield


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_exchange(request: Request) -> Any:
    return request.app.state.exchange


def create_app() -> FastAPI:
    app = FastAPI(title="Crypto Bot Dashboard", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index(
        request: Request,
        settings: Annotated[AppSettings, Depends(get_settings)],
    ) -> Any:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "refresh_sec": settings.dashboard_refresh_sec,
                "host": settings.dashboard_host,
                "port": settings.dashboard_port,
            },
        )

    @app.get("/api/snapshot")
    async def api_snapshot(
        exchange: Annotated[Any, Depends(get_exchange)],
        settings: Annotated[AppSettings, Depends(get_settings)],
    ) -> dict[str, Any]:
        symbols = settings.dashboard_symbol_list()
        return build_snapshot(exchange, symbols)

    return app
