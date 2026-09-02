import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramRetryAfter
import config
from handlers import router, load_custom_texts_into_memory, start_cleanup_task
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


async def _run_with_flood_retry(coro_factory, label: str, max_wait_seconds: int = 900):
    """
    ينفّذ عملية تتصل بتليكرام (get_me/delete_webhook/...) وينتظر فعليًا
    مدة flood control اللي يطلبها تليكرام (TelegramRetryAfter.retry_after)
    بنفس العملية الحالية، بدل ما نتجاهل الخطأ أو نخلي البرنامج ينهار.

    السبب: تجاهل الخطأ والمتابعة فورًا كان يخلي استدعاء لاحق (زي get_me
    داخل dp.start_polling) يرتطم بنفس نوع الحظر على ميثود مختلف، وأي
    كراش يخلي Railway يعيد تشغيل الحاوية فورًا، فيصير استدعاء جديد يضرب
    نفس القفل من جديد بحلقة لا نهائية تسوء أكثر بدل ما تتحسن. الانتظار
    هنا (max_wait_seconds كسقف أمان) هو الحل الوحيد اللي يكسر الحلقة فعليًا.
    """
    while True:
        try:
            return await coro_factory()
        except TelegramRetryAfter as exc:
            wait_seconds = min(exc.retry_after + 2, max_wait_seconds)
            logger.warning(
                "⏳ %s: flood control من تليكرام، ننتظر %s ثانية بنفس العملية ثم نعيد المحاولة",
                label, wait_seconds,
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

    # مهمة خلفية تنظّف دوريًا أي حالة مؤقتة بالذاكرة (pending_audio/wizard_state/
    # pending_confirm/channel_reply_index) انتهت صلاحيتها ولم تُنظَّف تلقائيًا
    # (المستخدم بدأ ولم يكمل التدفّق) — تمنع تسرّب الذاكرة على المدى الطويل.
    start_cleanup_task()

    await _run_with_flood_retry(
        lambda: bot.delete_webhook(drop_pending_updates=True), "حذف الـ webhook",
    )
    # نجيب معلومات البوت (get_me) مرة واحدة هنا صراحة ومع انتظار فعلي لأي
    # flood control، عشان aiogram يخزّنها بالكاش (bot._me) ولا يعيد
    # استدعاء GetMe من جديد داخل dp.start_polling() ويرتطم بنفس الحظر.
    await _run_with_flood_retry(bot.get_me, "جلب معلومات البوت (get_me)")

    logging.info(LOG_BOT_RUNNING)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
