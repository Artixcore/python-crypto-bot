from crypto_bot.logging_setup import configure_logging
from crypto_bot.telegram_bot.bot import build_application


def main() -> None:
    configure_logging(json_logs=False)
    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
