import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

import config
from handlers import router
from texts import LOG_BOT_RUNNING


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info(LOG_BOT_RUNNING)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())