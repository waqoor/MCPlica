"""Configure safe logging before RQ configures its worker and scheduler loggers."""

import sys

from rq.cli.cli import main

from app.core.config import get_settings
from app.core.logging import configure_logging


def run() -> None:
    settings = get_settings()
    service = sys.argv[1]
    configure_logging(
        settings.log_level,
        json_logs=settings.is_production,
        service=service,
        directory=settings.log_directory,
        max_bytes=settings.log_max_file_bytes,
    )
    main(args=["worker", *sys.argv[2:]])


if __name__ == "__main__":
    run()
