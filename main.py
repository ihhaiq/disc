import asyncio
import logging
import os
import time
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramRetryAfter
import config
from handlers import router, load_custom_texts_into_memory
from help_builder import router as help_router          # ← جديد
from texts import LOG_BOT_RUNNING, LOG_USING_LOCAL_BOT_API, LOG_TEMP_CLEANUP_STARTUP_FMT

logger = logging.getLogger(__name__)


def cleanup_temp_dir_on_startup() -> None:
    """
    يمسح كل محتويات TEMP_DIR عند بدء تشغيل البوت.

    السبب: لو البوت انطفى فجأة (crash / redeploy) وبنفس اللحظة فيه Jobs شغالة،
    الملفات المؤقتة الخاصة بها (صوت/صورة/قرص/فيديو) تظل موجودة على القرص للأبد
    لأن التنظيف الطبيعي (cleanup() في handlers.py) يصير فقط داخل نفس العملية
    عبر finally. بما إنه ما فيه أي Job يمكن يكون شغّال فعليًا لحظة بدء التشغيل
    (الطابور بالذاكرة يبدأ فاضي من جديد)، أي ملف موجود بـ TEMP_DIR الآن هو
    بقايا من تشغيلة سابقة ويُعتبر آمن حذفه بالكامل.
    """
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
                import shutil
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            logger.exception("فشل حذف ملف مؤقت قديم: %s", path)

    if removed:
        logger.info(LOG_TEMP_CLEANUP_STARTUP_FMT, removed)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    cleanup_temp_dir_on_startup()

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
    # لا نخلي فشل هذا الاستدعاء يطيح بكل البوت: لو تليكرام رجّع flood control
    # (مثلاً بسبب ريستارتات متكررة بفترة قصيرة)، البرنامج كان ينهار بالكامل،
    # و Railway يعيد التشغيل فورًا فيرتطم بنفس الحظر من جديد بحلقة لا نهائية.
    # هنا نكتفي بتسجيل تحذير والمتابعة مباشرة لبدء الـ polling، لأن
    # drop_pending_updates مجرد تنظيف اختياري مو ضروري لعمل البوت.
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except TelegramRetryAfter as exc:
        logger.warning(
            "تعذّر حذف الـ webhook بسبب flood control (retry after %s ثانية)، "
            "متابعة بدون حذفه",
            exc.retry_after,
        )
    except Exception:
        logger.exception("تعذّر حذف الـ webhook، متابعة تشغيل البوت بدون هذي الخطوة")
    logging.info(LOG_BOT_RUNNING)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
