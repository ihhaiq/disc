import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
import config
from handlers import router, load_custom_texts_into_memory
from help_builder import router as help_router          # ← جديد
from texts import LOG_BOT_RUNNING, LOG_USING_LOCAL_BOT_API


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    # تحميل النصوص المخصصة من JSON الدائم
    load_custom_texts_into_memory()
    session = None
    if config.USE_LOCAL_BOT_API:
        logging.info(LOG_USING_LOCAL_BOT_API, config.LOCAL_BOT_API_URL)
        local_server = TelegramAPIServer.from_base(config.LOCAL_BOT_API_URL, is_local=True)
        session = AiohttpSession(api=local_server)
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"), session=session)
    dp = Dispatcher()
    dp.include_router(help_router)   # ← جديد، لازم قبل router العام
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info(LOG_BOT_RUNNING)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
