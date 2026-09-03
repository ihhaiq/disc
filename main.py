import asyncio
import logging
import os
import shutil
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramRetryAfter

import config
from handlers import router, start_cleanup_task
from help_builder import router as help_router
from services.localization import load_custom_texts_into_memory
from texts import LOG_BOT_RUNNING, LOG_USING_LOCAL_BOT_API, LOG_TEMP_CLEANUP_STARTUP_FMT

logger = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")


def cleanup_temp_dir_on_startup() -> None:
    """Remove temporary files left by an interrupted previous run."""
    if not os.path.isdir(config.TEMP_DIR):
        return

    removed = 0
    for name in os.listdir(config.TEMP_DIR):
        path = os.path.join(config.TEMP_DIR, name)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                removed += 1
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            logger.exception("فشل حذف ملف مؤقت قديم: %s", path)

    if removed:
        logger.info(LOG_TEMP_CLEANUP_STARTUP_FMT, removed)


async def _run_with_flood_retry(
    coro_factory: Callable[[], Awaitable[ResultT]],
    label: str,
    max_wait_seconds: int = 900,
) -> ResultT:
    """Retry a Telegram request after the requested flood-control delay."""
    while True:
        try:
            return await coro_factory()
        except TelegramRetryAfter as exc:
            wait_seconds = min(exc.retry_after + 2, max_wait_seconds)
            logger.warning(
                "⏳ %s: flood control من تليكرام، ننتظر %s ثانية ثم نعيد المحاولة",
                label,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
        except Exception:
            logger.exception("%s: فشل بخطأ غير متوقع (مو flood control)", label)
            raise


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    cleanup_temp_dir_on_startup()

    load_custom_texts_into_memory()
    session = None
    if config.USE_LOCAL_BOT_API:
        logging.info(LOG_USING_LOCAL_BOT_API, config.LOCAL_BOT_API_URL)
        local_server = TelegramAPIServer.from_base(config.LOCAL_BOT_API_URL, is_local=True)
        session = AiohttpSession(api=local_server)
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"), session=session)
    dp = Dispatcher()
    dp.include_router(help_router)
    dp.include_router(router)

    start_cleanup_task()

    await _run_with_flood_retry(
        lambda: bot.delete_webhook(drop_pending_updates=True),
        "حذف الـ webhook",
    )
    await _run_with_flood_retry(bot.get_me, "جلب معلومات البوت (get_me)")

    logging.info(LOG_BOT_RUNNING)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
