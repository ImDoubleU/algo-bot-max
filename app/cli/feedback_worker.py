from __future__ import annotations

import argparse
import asyncio
import logging

import app.db.base  # noqa: F401
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.feedback_worker import process_due_feedback

logger = logging.getLogger(__name__)


async def run(*, once: bool) -> None:
    settings = get_settings()
    while True:
        try:
            async with AsyncSessionLocal() as db:
                generated = await process_due_feedback(db)
            if generated:
                logger.info("Сформировано автоматических ОС: %s", generated)
        except Exception:
            logger.exception("Ошибка обработки автоматических ОС")
        if once:
            return
        await asyncio.sleep(settings.feedback_worker_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Автоматическая подготовка ОС преподавателям")
    parser.add_argument("--once", action="store_true", help="Выполнить один проход")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
    if not get_settings().feedback_worker_enabled:
        logger.info("Feedback worker отключен настройкой FEEDBACK_WORKER_ENABLED")
        return
    asyncio.run(run(once=args.once))


if __name__ == "__main__":
    main()
