import logging
import sys

import structlog


def configure_logging(json_logs: bool = True) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        formatter = structlog.processors.JSONRenderer()
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=shared + [formatter],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
