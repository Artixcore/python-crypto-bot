import os

import structlog

from crypto_bot.logging_setup import configure_logging
from crypto_bot.telegram_bot.bot import build_application

logger = structlog.get_logger(__name__)


def main() -> None:
    configure_logging(json_logs=False)
    logger.info("telegram_process_start", cwd=os.getcwd())
    app = build_application()
    app.run_polling(drop_pending_updates=True, bootstrap_retries=3)


if __name__ == "__main__":
    main()
