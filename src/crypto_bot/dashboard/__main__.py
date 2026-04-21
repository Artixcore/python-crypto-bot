import uvicorn

from crypto_bot.config.settings import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "crypto_bot.dashboard.app:create_app",
        factory=True,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
