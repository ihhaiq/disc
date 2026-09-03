import asyncio
import logging
import math
import os
import time
import uuid

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

import config
import keyboard as keyboards
import limits
import texts as texts_module
from routers.developer import awaiting_menu_image
from routers.developer import router as developer_router
from routers.developer_texts import router as developer_text_router
from routers.language import create_language_router
from routers.payments import create_payment_router
from routers.start import create_start_router
from routers.wizard import WizardHooks, WizardRuntime, create_wizard_router
from services.contexts import channel_key as _channel_key
from services.contexts import group_key as _group_key
from services.contexts import is_group_context as _is_group_context
from services.contexts import is_shared_context as _is_shared_context
from services.contexts import split_context_suffix as _split_channel_suffix
from services.ephemeral import EphemeralMessenger
from services.job_processor import JobProcessor, compute_job_timeout_seconds, release_job_usage
from services.localization import get_user_lang, tr
from services.messaging import (
    edit_text_variable,
    get_text_rich_content,
    reply_text_variable,
    reply_with_premium_emoji,
    send_text_variable,
)
from services.vinyl_settings import VinylSettings
from services.wizard_preview import WizardPreviewService
from vinyl_catalog import VINYL_STYLES

logger = logging.getLogger(__name__)
router = Router()

job_queue: asyncio.Queue[dict] = asyncio.Queue()
developer_job_queue: asyncio.Queue[dict] = asyncio.Queue()
worker_tasks: list[asyncio.Task] = []
queue_order: list[str] = []
pending_images: dict[object, dict] = {}
pending_audio: dict[object, dict] = {}
user_pending_jobs: dict[int, set[str]] = {}
tracked_jobs: dict[str, dict] = {}
canceled_job_ids: set[str] = set()
channel_reply_index: dict[tuple[int, int], str] = {}
vinyl_settings = VinylSettings()
ephemeral = EphemeralMessenger(pending_audio)
WIZARD_TTL_SECONDS = 600
CLEANUP_INTERVAL_SECONDS = 10 * 60
cleanup_task: asyncio.Task | None = None
developer_menu_image_file_id: str | None = None

VALID_VINYL_COLOR_VALUES: frozenset[str] = frozenset(style.key for style in VINYL_STYLES)


def _group_pending_key_for_user(chat_id: int, user_id: int) -> str | None:
    candidates = []
    now = time.time()
    for key, pending in pending_audio.items():
        if not _is_group_context(key):
            continue
        original = pending.get("message")
        if original is None or original.chat.id != chat_id:
            continue
        if not original.from_user or original.from_user.id != user_id:
            continue
        if now > pending.get("expires_at", 0):
            continue
        candidates.append((original.message_id, key))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


async def _is_channel_controller(bot: Bot, chat_id: int, user_id: int) -> bool:
    if not user_id:
        return False
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def resolve_callback_uid(callback, bot: Bot) -> tuple[str, object, int | None] | None:
    base, chat_id, message_id = _split_channel_suffix(callback.data)
    if chat_id is not None:
        presser_id = callback.from_user.id if callback.from_user else 0
        chat_type = callback.message.chat.type if callback.message else None

        if chat_type in ("group", "supergroup"):
            key = _group_key(chat_id, message_id)
            pending = pending_audio.get(key)
            original_sender_id = None
            if pending:
                original_message = pending.get("message")
                if original_message is not None and original_message.from_user:
                    original_sender_id = original_message.from_user.id
            is_owner = original_sender_id is not None and presser_id == original_sender_id
            if not is_owner and not await _is_channel_controller(bot, chat_id, presser_id):
                await callback.answer(texts_module.MSG_CHANNEL_ADMIN_ONLY, show_alert=True)
                return None
            return base, key, chat_id

        if not await _is_channel_controller(bot, chat_id, presser_id):
            await callback.answer(texts_module.MSG_CHANNEL_ADMIN_ONLY, show_alert=True)
            return None
        return base, _channel_key(chat_id, message_id), chat_id

    return base, (callback.from_user.id if callback.from_user else 0), None


async def notify_missing_channel_permission(
    bot: Bot, chat_id: int, chat_title: str, reason: str
) -> None:
    text = (
        f"⚠️ البوت ينقصه صلاحية داخل القناة «{chat_title}»:\n{reason}\n\n"
        "رجاءً امنح البوت الصلاحية المطلوبة من إعدادات إدارة القناة، وبعدها "
        "بيشتغل تلقائيًا بدون أي خطوة إضافية."
    )
    try:
        admins = await bot.get_chat_administrators(chat_id)
    except Exception:
        logger.exception("فشل جلب قائمة أدمن القناة لإشعارهم بنقص الصلاحيات")
        admins = []

    admins_sorted = sorted(admins, key=lambda member: 0 if member.status == "creator" else 1)
    for admin in admins_sorted:
        if admin.user.is_bot:
            continue
        try:
            await bot.send_message(admin.user.id, text)
            return
        except Exception:
            continue

    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("تعذّر إشعار أي طرف بنقص الصلاحيات بالقناة %s", chat_id)


def tmp(name: str) -> str:
    path = os.path.join(config.TEMP_DIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def cleanup(*paths: str) -> None:
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            logger.warning(texts_module.LOG_DELETE_FAILED_FMT.format(p=path, e=exc))


DOWNLOAD_BACKOFF_BASE_SECONDS = 1.5
DOWNLOAD_BACKOFF_MAX_SECONDS = 20.0


async def download_with_retries(
    bot: Bot,
    file_id: str,
    destination: str,
    timeout_seconds: int,
    retries: int = 3,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        if os.path.exists(destination):
            os.remove(destination)
        try:
            await bot.download(
                file_id,
                destination=destination,
                timeout=timeout_seconds,
                chunk_size=64 * 1024,
            )
            return
        except Exception as exc:
            last_error = exc
            logger.warning(
                texts_module.LOG_DOWNLOAD_RETRY_FAILED_FMT,
                attempt,
                retries,
                type(exc).__name__,
                exc or texts_module.LOG_NO_DETAIL_MESSAGE,
            )
            if attempt < retries:
                backoff = min(
                    DOWNLOAD_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)),
                    DOWNLOAD_BACKOFF_MAX_SECONDS,
                )
                await asyncio.sleep(backoff)
            else:
                raise
    if last_error is not None:
        raise last_error


def get_queue_position(job_id: str) -> int:
    try:
        return queue_order.index(job_id) + 1
    except ValueError:
        return 0


def _queue_position_text(uid, job_id: str) -> str | None:
    display_uid = uid if isinstance(uid, int) else 0
    position = get_queue_position(job_id)
    if position <= 0:
        return None
    if position == 1:
        return tr("MSG_QUEUE_POSITION_NEXT", display_uid)
    return tr("MSG_QUEUE_POSITION_FMT", display_uid).format(position=position)


async def notify_queue_position(bot: Bot, chat_id: int, uid, job_id: str) -> None:
    if _is_shared_context(uid):
        return
    text = _queue_position_text(uid, job_id)
    if text is None:
        return
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("فشل إرسال رسالة موقع الطابور")


def _cleanup_expired_pending_audio() -> int:
    now = time.time()
    removed = 0
    for key in list(pending_audio):
        entry = pending_audio.get(key)
        if entry is None or now > entry.get("expires_at", 0):
            pending_audio.pop(key, None)
            wizard.reset(key)
            if isinstance(key, int):
                pending_images.pop(key, None)
            removed += 1
    return removed


def _cleanup_orphaned_channel_reply_index() -> int:
    removed = 0
    for reply_key, mapped_key in list(channel_reply_index.items()):
        if mapped_key not in pending_audio:
            channel_reply_index.pop(reply_key, None)
            removed += 1
    return removed


async def _periodic_cleanup_loop() -> None:
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            audio_removed = _cleanup_expired_pending_audio()
            wizard_removed = wizard.cleanup_orphaned()
            confirms_removed = wizard.cleanup_expired_confirm()
            replies_removed = _cleanup_orphaned_channel_reply_index()
            total = audio_removed + wizard_removed + confirms_removed + replies_removed
            if total:
                logger.info(
                    "🧹 تنظيف دوري للحالة المؤقتة: pending_audio=%s wizard_state=%s "
                    "pending_confirm=%s channel_reply_index=%s (مجموع=%s)",
                    audio_removed,
                    wizard_removed,
                    confirms_removed,
                    replies_removed,
                    total,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("فشل التنظيف الدوري للحالة المؤقتة")


def start_cleanup_task() -> None:
    global cleanup_task
    if cleanup_task is None or cleanup_task.done():
        cleanup_task = asyncio.create_task(_periodic_cleanup_loop())


async def start_job_worker(bot: Bot) -> None:
    global worker_tasks
    worker_tasks = [task for task in worker_tasks if not task.done()]
    needed = max(1, config.MAX_CONCURRENT_JOBS) - len(worker_tasks)
    for _ in range(needed):
        worker_tasks.append(asyncio.create_task(_job_worker_loop(bot)))


async def _get_next_job() -> tuple[dict, asyncio.Queue]:
    while True:
        if not developer_job_queue.empty():
            return developer_job_queue.get_nowait(), developer_job_queue
        if not job_queue.empty():
            return job_queue.get_nowait(), job_queue

        dev_task = asyncio.create_task(developer_job_queue.get())
        normal_task = asyncio.create_task(job_queue.get())
        pending_tasks = set()
        try:
            done, pending_tasks = await asyncio.wait(
                {dev_task, normal_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in pending_tasks:
                task.cancel()
            for task in pending_tasks:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        if dev_task in done and not dev_task.cancelled():
            job = dev_task.result()
            if normal_task in done and not normal_task.cancelled():
                job_queue.put_nowait(normal_task.result())
            return job, developer_job_queue

        if normal_task in done and not normal_task.cancelled():
            return normal_task.result(), job_queue


async def _job_worker_loop(bot: Bot) -> None:
    while True:
        job, queue = await _get_next_job()
        job_id = job.get("job_id")
        if job_id in queue_order:
            queue_order.remove(job_id)

        try:
            if job_id in canceled_job_ids:
                canceled_job_ids.discard(job_id)
                tracked_jobs.pop(job_id, None)
                user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
                continue

            tracked_jobs[job_id] = job
            timeout = compute_job_timeout_seconds(
                getattr(job.get("audio"), "file_size", None)
            )
            try:
                await asyncio.wait_for(job_processor.process(bot, job), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(texts_module.LOG_JOB_TIMEOUT)
        except Exception:
            logger.exception(texts_module.LOG_QUEUE_PROCESS_FAILED)
        finally:
            release_job_usage(job)
            tracked_jobs.pop(job_id, None)
            user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
            queue.task_done()


def user_has_premium_access(user_id: int) -> bool:
    if user_id and user_id == config.DEVELOPER_ID:
        return True
    if limits.is_whitelisted(user_id):
        return True
    return limits.is_premium(user_id)


def _customize_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return keyboards.build_customize_keyboard(
        user_id,
        vinyl_settings.get_rotation_seconds(user_id),
    )


def _vinyl_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return keyboards.build_vinyl_color_keyboard(
        user_id,
        current_choice=vinyl_settings.get_choice(user_id),
        has_premium=user_has_premium_access(user_id),
    )


def get_job_priority(user_id: int) -> int:
    return 0 if user_id and user_id == config.DEVELOPER_ID else 1


def enqueue_job(job: dict) -> None:
    uid = job.get("uid", 0)
    queue_order.append(job["job_id"])
    if get_job_priority(uid) == 0:
        developer_job_queue.put_nowait(job)
    else:
        job_queue.put_nowait(job)


def cancel_user_jobs(user_id: int) -> None:
    pending_ids = user_pending_jobs.pop(user_id, set())
    for job_id in list(pending_ids):
        canceled_job_ids.add(job_id)
        job = tracked_jobs.pop(job_id, None)
        if job:
            release_job_usage(job)
            cleanup(*job.get("temp_paths", []))
        if job_id in queue_order:
            queue_order.remove(job_id)


@router.callback_query(F.data == "customize:open")
async def on_customize_open(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    text = (
        "⚙️ Customize your disc settings:"
        if get_user_lang(user_id) == "en"
        else "⚙️ تخصيص إعدادات القرص:"
    )
    await callback.message.edit_text(text, reply_markup=_customize_keyboard(user_id))
    await callback.answer()


@router.callback_query(F.data == "customize:back")
async def on_customize_back(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    me = await bot.get_me()
    await edit_text_variable(
        callback.message,
        bot,
        "MSG_START_HELP",
        user_id,
        reply_markup=keyboards.build_start_keyboard(user_id, me.username),
    )
    await callback.answer()


@router.callback_query(F.data == "vinyl_menu:open")
async def on_vinyl_menu_open(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id and not get_text_rich_content(
        "MSG_VINYL_COLOR_INFO", user_id
    ):
        await callback.message.delete()
        await callback.message.answer_photo(
            developer_menu_image_file_id,
            caption=tr("MSG_VINYL_COLOR_INFO", user_id),
            reply_markup=_vinyl_color_keyboard(user_id),
        )
    elif developer_menu_image_file_id:
        await callback.message.delete()
        await send_text_variable(
            bot,
            callback.message.chat.id,
            "MSG_VINYL_COLOR_INFO",
            user_id,
            reply_markup=_vinyl_color_keyboard(user_id),
        )
    else:
        await edit_text_variable(
            callback.message,
            bot,
            "MSG_VINYL_COLOR_INFO",
            user_id,
            reply_markup=_vinyl_color_keyboard(user_id),
        )
    await callback.answer()


@router.callback_query(F.data == "vinyl_menu:back")
async def on_vinyl_menu_back(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id:
        await callback.message.delete()
        await send_text_variable(
            bot,
            callback.message.chat.id,
            "MSG_START_HELP",
            user_id,
            reply_markup=_customize_keyboard(user_id),
        )
    else:
        text = (
            "⚙️ Customize your disc settings:"
            if get_user_lang(user_id) == "en"
            else "⚙️ تخصيص إعدادات القرص:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=_customize_keyboard(user_id),
        )
    await callback.answer()


@router.channel_post(F.audio)
async def on_channel_audio(message: Message, bot: Bot):
    chat_id = message.chat.id
    key = _channel_key(chat_id, message.message_id)
    pending_audio[key] = {
        "audio": message.audio,
        "message": message,
        "expires_at": time.time() + WIZARD_TTL_SECONDS,
        "job_id": uuid.uuid4().hex,
        "uid": key,
        "channel_msg_ids": [],
    }
    wizard.reset(key)

    keyboard = keyboards.build_mode_keyboard(
        key,
        chat_id=chat_id,
        message_id=message.message_id,
    )
    try:
        prompt = await reply_text_variable(
            message,
            bot,
            "MSG_CHOOSE_MODE",
            key,
            reply_markup=keyboard,
        )
    except TelegramBadRequest as exc:
        pending_audio.pop(key, None)
        if "rights" in str(exc).lower() or "administrator" in str(exc).lower():
            await notify_missing_channel_permission(
                bot,
                chat_id,
                message.chat.title or "القناة",
                "إرسال الرسائل وأزرار Inline بالقناة (صلاحية Post Messages).",
            )
        else:
            logger.exception("فشل إرسال رسالة اختيار الوضع بالقناة")
        return

    channel_reply_index[(chat_id, prompt.message_id)] = key
    pending_audio[key]["channel_msg_ids"].append(prompt.message_id)
    pending_audio[key]["channel_prompt_message_id"] = prompt.message_id


@router.message(F.audio)
async def on_audio(message: Message, bot: Bot):
    owner_id = message.from_user.id if message.from_user else 0
    is_group = message.chat.type in ("group", "supergroup")
    context_key = _group_key(message.chat.id, message.message_id) if is_group else owner_id
    audio = message.audio

    if owner_id != config.DEVELOPER_ID and not limits.can_create(owner_id):
        await _send_limit_reached(message, bot, owner_id, is_group=is_group)
        return

    if audio.file_size and audio.file_size > config.MAX_TELEGRAM_AUDIO_SIZE_BYTES:
        logger.info(texts_module.LOG_FILE_TOO_LARGE)
        too_large_text = tr("MSG_AUDIO_TOO_LARGE_FMT", owner_id).format(
            max_size_mb=config.MAX_TELEGRAM_AUDIO_SIZE_BYTES / (1024 * 1024)
        )
        if is_group:
            await ephemeral.send_text(
                bot,
                message.chat.id,
                owner_id,
                too_large_text,
            )
        else:
            await reply_with_premium_emoji(message, too_large_text)
        return

    pending_audio[context_key] = {
        "audio": audio,
        "message": message,
        "expires_at": time.time() + WIZARD_TTL_SECONDS,
        "job_id": uuid.uuid4().hex,
        "uid": owner_id,
        "owner_user_id": owner_id,
    }
    wizard.reset(context_key)
    pending_images.pop(context_key, None)

    if is_group:
        group_keyboard = keyboards.build_mode_keyboard(
            owner_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
        sent = await ephemeral.send_text(
            bot,
            message.chat.id,
            owner_id,
            tr("MSG_CHOOSE_MODE", owner_id),
            reply_markup=group_keyboard,
        )
        pending_audio[context_key]["ephemeral_message_id"] = sent.ephemeral_message_id
    else:
        await reply_text_variable(
            message,
            bot,
            "MSG_CHOOSE_MODE",
            owner_id,
            reply_markup=keyboards.build_mode_keyboard(owner_id),
        )


def _get_pending_audio_or_none(context_key) -> dict | None:
    pending = pending_audio.get(context_key)
    if not pending or time.time() > pending["expires_at"]:
        pending_audio.pop(context_key, None)
        wizard.reset(context_key)
        return None
    return pending


async def _send_limit_reached(
    message: Message,
    bot: Bot,
    owner_id: int,
    *,
    is_group: bool,
) -> None:
    hours = max(1, math.ceil(limits.get_reset_seconds(owner_id) / 3600))
    format_kwargs = {
        "limit": limits.get_daily_limit(owner_id),
        "hours": hours,
        "premium_limit": config.PREMIUM_DAILY_LIMIT,
        "price": config.STARS_SUBSCRIPTION_PRICE,
    }
    if is_group:
        await ephemeral.send_text(
            bot,
            message.chat.id,
            owner_id,
            tr("MSG_LIMIT_REACHED_FMT", owner_id).format(**format_kwargs),
            reply_markup=keyboards.build_buy_stars_keyboard(owner_id),
        )
        return
    await reply_text_variable(
        message,
        bot,
        "MSG_LIMIT_REACHED_FMT",
        owner_id,
        reply_markup=keyboards.build_buy_stars_keyboard(owner_id),
        **format_kwargs,
    )


async def _launch_job(bot: Bot, uid, job: dict) -> bool:
    await start_job_worker(bot)
    owner_id = job.get("owner_user_id", job.get("uid", uid))
    should_charge = (
        isinstance(owner_id, int)
        and owner_id != config.DEVELOPER_ID
        and not limits.is_whitelisted(owner_id)
        and not job.get("is_preview")
    )
    if should_charge and not limits.reserve_usage(owner_id):
        message = job.get("message")
        if message is not None:
            await _send_limit_reached(
                message,
                bot,
                owner_id,
                is_group=message.chat.type in ("group", "supergroup"),
            )
        return False
    if should_charge:
        job["usage_reserved_for"] = owner_id
    if _is_group_context(job.get("context_key", uid)):
        job["uid"] = owner_id
    tracked_jobs[job["job_id"]] = job
    user_pending_jobs.setdefault(owner_id, set()).add(job["job_id"])
    enqueue_job(job)
    context_key = job.get("context_key", uid)
    message = job.get("message")
    if message is not None:
        await notify_queue_position(
            bot,
            message.chat.id,
            context_key,
            job["job_id"],
        )
    return True


@router.callback_query(F.data.startswith("mode:quick"))
async def on_mode_quick(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    _, context_key, channel_chat_id = resolved
    pending = _get_pending_audio_or_none(context_key)
    if not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", context_key), show_alert=True)
        return

    audio = pending["audio"]
    if audio.thumbnail:
        job = dict(pending)
        job["context_key"] = context_key
        if _is_group_context(context_key):
            job["uid"] = pending.get("owner_user_id", context_key)
            job["status_ephemeral_message_id"] = ephemeral.message_id(pending)
        else:
            await ephemeral.edit_wizard_text_variable(
                bot,
                context_key,
                callback.message,
                "MSG_JOB_QUEUED",
            )
        pending_audio.pop(context_key, None)
        job["segment_start"] = 0.0
        await _launch_job(bot, job["uid"], job)
    elif channel_chat_id is not None:
        pending["awaiting_reply_image"] = True
        await ephemeral.edit_wizard_text(
            bot,
            context_key,
            callback.message,
            texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY,
        )
    else:
        pending_images[context_key] = {
            "quick_mode": True,
            "audio_message_id": pending["message"].message_id,
        }
        await ephemeral.edit_wizard_text_variable(
            bot,
            context_key,
            callback.message,
            "MSG_QUICK_NEED_IMAGE",
        )
    await callback.answer()


def _channel_ctx(context_key) -> tuple[int | None, int | None]:
    if not _is_shared_context(context_key):
        return None, None
    rest = context_key[1:]
    chat_str, _, message_str = rest.partition(":")
    try:
        return int(chat_str), int(message_str)
    except ValueError:
        return None, None


@router.callback_query(F.data.startswith("cancel_queue"))
async def on_cancel_queue(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    _, context_key, _channel_chat_id = resolved
    pending = pending_audio.get(context_key)
    owner_id = pending.get("owner_user_id", context_key) if pending else context_key
    cancel_user_jobs(owner_id)
    if _is_group_context(context_key):
        message_id = ephemeral.message_id(pending)
        if message_id is not None:
            try:
                await ephemeral.delete_text(
                    bot,
                    callback.message.chat.id,
                    owner_id,
                    message_id,
                )
            except Exception:
                pass
    else:
        await edit_text_variable(
            callback.message,
            bot,
            "MSG_QUEUE_CANCELED_EDIT",
            context_key,
        )
    pending_audio.pop(context_key, None)
    wizard.cancel(context_key)
    await callback.answer(tr("MSG_QUEUE_CANCELED_ANSWER", context_key))


@router.channel_post(F.photo)
async def on_channel_photo_reply(message: Message, bot: Bot):
    if not message.reply_to_message:
        return
    chat_id = message.chat.id
    key = channel_reply_index.get((chat_id, message.reply_to_message.message_id))
    if key is None:
        return

    pending = _get_pending_audio_or_none(key)
    if not pending:
        return

    pending["thumbnail_file_id"] = message.photo[-1].file_id
    pending.setdefault("channel_msg_ids", []).append(message.message_id)

    if pending.pop("awaiting_reply_image", False) and not wizard.has_active(key):
        pending_audio.pop(key, None)
        job = dict(pending)
        job["context_key"] = key
        job["segment_start"] = 0.0
        await _launch_job(bot, key, job)
        return

    await wizard.advance_to_segment_or_finish(bot, key, message.reply)


@router.message(F.photo)
async def on_photo_for_audio(message: Message, bot: Bot):
    global developer_menu_image_file_id
    owner_id = message.from_user.id if message.from_user else 0
    group_context = (
        _group_pending_key_for_user(message.chat.id, owner_id)
        if message.chat.type in ("group", "supergroup")
        else None
    )
    context_key = group_context or owner_id

    if owner_id == config.DEVELOPER_ID and owner_id in awaiting_menu_image:
        awaiting_menu_image.discard(owner_id)
        developer_menu_image_file_id = message.photo[-1].file_id
        await message.reply(texts_module.MSG_DEV_MENU_IMAGE_SAVED)
        return

    if await wizard.handle_photo(message, bot, context_key):
        return

    pending = pending_images.get(context_key)
    if not pending or not pending.get("quick_mode"):
        return

    pending_entry = _get_pending_audio_or_none(context_key)
    if not pending_entry:
        pending_images.pop(context_key, None)
        await reply_text_variable(
            message,
            bot,
            "MSG_AUDIO_EXPIRED",
            context_key,
        )
        return

    job = dict(pending_entry)
    job["thumbnail_file_id"] = message.photo[-1].file_id
    job["uid"] = pending_entry.get("owner_user_id", context_key)
    job["context_key"] = context_key
    job["segment_start"] = 0.0

    if not _is_group_context(context_key):
        await reply_text_variable(
            message,
            bot,
            "MSG_IMAGE_RECEIVED",
            context_key,
        )
    else:
        original = job.get("message")
        if original is not None:
            await ephemeral.edit_wizard_text_variable(
                bot,
                context_key,
                original,
                "MSG_IMAGE_RECEIVED",
            )

    pending_audio.pop(context_key, None)
    pending_images.pop(context_key, None)
    await _launch_job(bot, job["uid"], job)


@router.callback_query(F.data.startswith("vinyl:"))
async def on_vinyl_choice(callback, bot: Bot):
    choice = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    if choice in VALID_VINYL_COLOR_VALUES:
        if limits.is_premium_color(choice) and not user_has_premium_access(user_id):
            await callback.answer(
                tr("MSG_COLOR_PREMIUM_ONLY", user_id),
                show_alert=True,
            )
            await callback.message.reply(
                tr("MSG_COLOR_PREMIUM_ONLY", user_id),
                reply_markup=keyboards.build_buy_stars_keyboard(user_id),
            )
            return
        vinyl_settings.set_choice(user_id, choice)
    else:
        vinyl_settings.set_choice(user_id, None)
    await callback.message.edit_reply_markup(
        reply_markup=_vinyl_color_keyboard(user_id)
    )
    await callback.answer(tr("MSG_VINYL_CHOICE_SAVED_ANSWER", user_id))


@router.callback_query(F.data.startswith("speed:"))
async def on_speed_selected(callback, bot: Bot):
    user_id = callback.from_user.id
    vinyl_settings.set_rotation_value(
        user_id,
        callback.data.split(":", 1)[1],
    )
    await callback.message.edit_reply_markup(
        reply_markup=_customize_keyboard(user_id)
    )
    await callback.answer(tr("MSG_SPEED_SAVED_ANSWER", user_id))


preview_service = WizardPreviewService(
    vinyl_settings=vinyl_settings,
    download_with_retries=download_with_retries,
    temp_path=tmp,
    cleanup=cleanup,
)

job_processor = JobProcessor(
    ephemeral=ephemeral,
    vinyl_settings=vinyl_settings,
    channel_reply_index=channel_reply_index,
    temp_path=tmp,
    cleanup=cleanup,
    download_with_retries=download_with_retries,
    notify_missing_channel_permission=notify_missing_channel_permission,
)

wizard = WizardRuntime(
    pending_audio=pending_audio,
    vinyl_settings=vinyl_settings,
    ephemeral=ephemeral,
    preview_service=preview_service,
    hooks=WizardHooks(
        resolve_callback_uid=resolve_callback_uid,
        get_pending_audio=_get_pending_audio_or_none,
        reply_text_variable=reply_text_variable,
        launch_job=_launch_job,
        channel_ctx=_channel_ctx,
        user_has_premium_access=user_has_premium_access,
    ),
    valid_vinyl_colors=VALID_VINYL_COLOR_VALUES,
    ttl_seconds=WIZARD_TTL_SECONDS,
)

router.include_router(create_wizard_router(wizard))
router.include_router(developer_router)
router.include_router(developer_text_router)
router.include_router(
    create_language_router(
        edit_text_variable,
        _vinyl_color_keyboard,
        _customize_keyboard,
        keyboards.build_start_keyboard,
    )
)
router.include_router(
    create_start_router(reply_text_variable, keyboards.build_start_keyboard)
)
router.include_router(create_payment_router(reply_text_variable))
