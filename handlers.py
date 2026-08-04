import asyncio
import ast
import logging
import os
import time
import uuid
# ميو 
from aiogram import Router, F, Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, MessageEntity,
    InputRichMessage, ReplyParameters,
)

from compose import build_disc
from processor import get_duration, render_vinyl
import config
import limits
import texts as texts_module
from texts import (
    STAGE_PREPARING,
    STAGE_DOWNLOADING_AUDIO,
    STAGE_DOWNLOADING_THUMBNAIL,
    STAGE_BUILDING_DISC,
    STAGE_RENDERING_VIDEO,
    STAGE_UPLOADING_VIDEO,
    LOG_PROGRESS_UPDATE_FAILED,
    LOG_DELETE_FAILED_FMT,
    LOG_DOWNLOAD_RETRY_FAILED_FMT,
    LOG_NO_DETAIL_MESSAGE,
    LOG_QUEUE_PROCESS_FAILED,
    LOG_PROCESS_JOB_FAILED,
    LOG_SEND_ERROR_FAILED,
    LOG_FILE_TOO_LARGE,
    ERR_NO_THUMBNAIL_AVAILABLE,
    ERR_OUTPUT_NOT_CREATED,
    MSG_AUDIO_RECEIVED,
    MSG_DURATION_TOO_LONG_FMT,
    MSG_PROCESSING_ERROR_FMT,
    MSG_DEV_CHOOSE_TEMPLATE,
    MSG_VINYL_COLOR_INFO,
    MSG_START_HELP,
    MSG_TEMPLATE_FILES_MISSING,
    MSG_NO_THUMBNAIL_PROMPT,
    MSG_JOB_QUEUED,
    MSG_QUEUE_CANCELED_EDIT,
    MSG_QUEUE_CANCELED_ANSWER,
    MSG_SEND_IMAGE_NOW,
    MSG_NO_PENDING_AUDIO,
    MSG_AUDIO_EXPIRED,
    MSG_IMAGE_RECEIVED,
    MSG_DEV_ONLY_OPTION,
    MSG_VINYL_CHOICE_SAVED_EDIT,
    MSG_VINYL_CHOICE_SAVED_ANSWER,
    MSG_SPEED_SAVED_ANSWER,
    MSG_WRONG_TYPE,
    MSG_DEV_SEND_MENU_IMAGE,
    MSG_DEV_MENU_IMAGE_SAVED,
    BTN_DEV_SET_MENU_IMAGE,
    BTN_ADD_IMAGE,
    BTN_CANCEL,
    BTN_VINYL_PINK,
    BTN_VINYL_DEFAULT,
    BTN_VINYL_YELLOW,
    BTN_VINYL_BLUE,
    BTN_VINYL_COLOR_MENU,
    BTN_VINYL_BLACK,
    BTN_VINYL_GREEN,
    BTN_BACK,
    BTN_VINYL_RED,
    SPEED_LABEL_FULL,
    SPEED_LABEL_8RPM,
    SPEED_LABEL_33RPM,
    SPEED_LABEL_45RPM,
    MSG_CHOOSE_MODE,
    BTN_QUICK_CREATE,
    BTN_CUSTOMIZE,
    MSG_WIZ_CHOOSE_COLOR,
    MSG_WIZ_CHOOSE_SPEED,
    MSG_WIZ_CHOOSE_IMAGE,
    BTN_WIZ_SKIP_IMAGE,
    MSG_WIZ_NO_IMAGE_TO_SKIP,
    MSG_WIZ_CHOOSE_SEGMENT,
    MSG_WIZ_STARTING,
    MSG_WIZ_EXPIRED,
    BTN_WIZ_SEGMENT_FMT,
    MSG_QUICK_NEED_IMAGE,
    MSG_LIMIT_REACHED_FMT,
    BTN_BUY_STARS,
    MSG_INVOICE_TITLE,
    MSG_INVOICE_DESCRIPTION_FMT,
    MSG_INVOICE_LABEL,
    MSG_INVOICE_PAYLOAD_PREFIX,
    MSG_PAYMENT_SUCCESS_FMT,
    LOG_PAYMENT_RECORDED,
    MSG_NEW_SUBSCRIBER_ADMIN_FMT,
)
import math

logger = logging.getLogger(__name__)
router = Router()

job_queue: asyncio.Queue[dict] = asyncio.Queue()
developer_job_queue: asyncio.Queue[dict] = asyncio.Queue()
worker_task: asyncio.Task | None = None
pending_images: dict[int, dict] = {}
pending_audio: dict[int, dict] = {}
user_rotation_seconds: dict[int, float | None] = {}
user_pending_jobs: dict[int, set[str]] = {}
tracked_jobs: dict[str, dict] = {}
canceled_job_ids: set[str] = set()
developer_vinyl_choice: dict[int, str] = {}
wizard_state: dict[int, dict] = {}
WIZARD_TTL_SECONDS = 600

developer_menu_image_file_id: str | None = None
awaiting_menu_image: set[int] = set()
awaiting_whitelist_add: set[int] = set()

# --- محرر النصوص (لوحة المطور) ---
TEXTS_PER_PAGE = 5
TEXTS_FILE_PATH = os.path.join(config.BASE_DIR, "texts.py")
dev_text_edit_page: dict[int, int] = {}
awaiting_text_value: dict[int, str] = {}

HOURGLASS_FRAMES = ["⏳", "⌛"]
PROGRESS_BAR_WIDTH = 12
STATUS_UPDATE_INTERVAL_SECONDS = 2.2


# ============================================================
# دعم إيموجي بريميوم (Telegram Premium Custom Emoji)
# ============================================================
# عشان تفعّل إيموجي بريميوم حقيقي، حط بهالقاموس: "الإيموجي العادي" -> "custom_emoji_id"
# ملاحظة مهمة: هذا الحساب (البوت أو المستخدم اللي سحب الـ ID) لازم يملك
# اشتراك Telegram Premium وقت الحصول على الـ custom_emoji_id (عادة عبر Bot API
# getForumTopicIconStickers / أو سحبه من رسالة قديمة فيها نفس الإيموجي البريميوم
# عبر MessageEntity من نوع custom_emoji). المستخدمون بدون Premium يشوفون
# الإيموجي العادي البديل تلقائيًا من تليكرام، فما راح ينكسر الشكل عندهم.
#
# مثال (عدّل القيم بمعرفات حقيقية):
# PREMIUM_EMOJI_IDS: dict[str, str] = {
#     "⏳": "5223763545975583911",
#     "⌛": "5223670277566716401",
#     "✅": "5215787375673504530",
#     "❌": "5210952531676504517",
# }
PREMIUM_EMOJI_IDS: dict[str, str] = {}

USE_PREMIUM_EMOJI = bool(PREMIUM_EMOJI_IDS)


def _utf16_len(ch: str) -> int:
    """طول المحرف بوحدات UTF-16 (المطلوب لحساب offset/length بكيانات تليكرام)."""
    return len(ch.encode("utf-16-le")) // 2


def build_premium_entities(text: str) -> list[MessageEntity] | None:
    """
    يبني قائمة MessageEntity من نوع custom_emoji لأي إيموجي بالنص موجود بقاموس
    PREMIUM_EMOJI_IDS. يرجع None لو ما فيه إيموجي بريميوم مفعّل، حتى ما نغيّر
    سلوك الرسائل الحالية بشيء.
    """
    if not PREMIUM_EMOJI_IDS:
        return None

    entities: list[MessageEntity] = []
    offset = 0
    for ch in text:
        length = _utf16_len(ch)
        emoji_id = PREMIUM_EMOJI_IDS.get(ch)
        if emoji_id:
            entities.append(MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=length,
                custom_emoji_id=emoji_id,
            ))
        offset += length

    return entities or None


async def reply_with_premium_emoji(message: Message, text: str, **kwargs) -> Message:
    """نفس message.reply لكن يضيف كيانات الإيموجي البريميوم تلقائيًا إن وجدت."""
    entities = build_premium_entities(text)
    if entities:
        return await message.reply(text, entities=entities, **kwargs)
    return await message.reply(text, **kwargs)


async def edit_text_with_premium_emoji(message: Message, text: str, **kwargs) -> Message:
    """نفس message.edit_text لكن يضيف كيانات الإيموجي البريميوم تلقائيًا إن وجدت."""
    entities = build_premium_entities(text)
    if entities:
        return await message.edit_text(text, entities=entities, **kwargs)
    return await message.edit_text(text, **kwargs)


# ============================================================
# دعم الرسائل الغنية (Rich Messages) — Bot API 10.1+
# ============================================================
# ميزة Rich Messages منفصلة تمامًا عن sendMessage العادية (اللي تستخدم
# parse_mode="HTML" الحالي بالمشروع). تُرسل عبر bot.send_rich_message مع
# InputRichMessage(content=..., format="html"|"markdown"), وتدعم بنية أغنى
# بكثير (جداول، قوائم، تفاصيل قابلة للطي، اقتباسات...). تتطلب aiogram >= 3.30.
def escape_rich_html(text: str) -> str:
    """
    يهرب رموز HTML الخاصة (&, <, >) قبل إرسال نص كـ Rich Message بصيغة html.
    استخدمها فقط لو النص "عادي" وما فيه وسوم Rich Message مقصودة بداخله؛
    لو النص فيه وسوم Rich Message حقيقية (مثل <b> أو <details>) لا تستخدمها،
    لأنها بتهرب الوسوم نفسها وتخلّيها تظهر كنص خام بدل ما تُفسَّر.
    """
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


async def send_rich_message(bot: Bot, chat_id: int, html_content: str,
                             reply_to_message_id: int | None = None,
                             reply_markup: InlineKeyboardMarkup | None = None) -> Message:
    """
    يرسل رسالة عبر ميزة Rich Messages الجديدة (sendRichMessage، Bot API 10.1+).
    html_content: نص HTML جاهز — إما وسوم Rich Message مقصودة، أو نص عادي
    (لازم يكون مُهرَّب مسبقًا عبر escape_rich_html لو فيه رموز <, >, & غير مقصودة).

    ملاحظة: لو النسخة المثبتة من aiogram أقدم من 3.30 وما تدعم sendRichMessage
    بعد، أو صار أي خطأ أثناء الإرسال، نرجع تلقائيًا لرسالة عادية (sendMessage)
    حتى ما ينكسر البوت.
    """
    reply_params = ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
    try:
        return await bot.send_rich_message(
            chat_id=chat_id,
            content=InputRichMessage(content=html_content, format="html"),
            reply_parameters=reply_params,
            reply_markup=reply_markup,
        )
    except AttributeError:
        # نسخة aiogram قديمة ما تدعم sendRichMessage بعد
        logger.warning("sendRichMessage غير مدعوم بهالنسخة من aiogram، الرجوع لرسالة عادية")
    except Exception:
        logger.exception("فشل إرسال Rich Message، الرجوع لرسالة عادية")

    return await bot.send_message(chat_id=chat_id, text=html_content, reply_markup=reply_markup)


async def reply_rich(message: Message, bot: Bot, html_content: str,
                      reply_markup: InlineKeyboardMarkup | None = None) -> Message:
    """اختصار: يرد على رسالة معيّنة بـ Rich Message (مع رجوع تلقائي لرسالة عادية عند الفشل)."""
    return await send_rich_message(
        bot, message.chat.id, html_content,
        reply_to_message_id=message.message_id,
        reply_markup=reply_markup,
    )


def render_progress_bar(percent: float, width: int = PROGRESS_BAR_WIDTH) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100))
    return "▓" * filled + "░" * (width - filled)


class StatusAnimator:
    """يحدّث رسالة الحالة بالتليكرام بشكل دوري: ساعة رملية متحركة + نص/شريط تقدّم."""

    def __init__(self, message: Message):
        self.message = message
        self.stage_text = STAGE_PREPARING
        self.percent: float | None = None
        self._frame = 0
        self._last_rendered: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def set_stage(self, stage_text: str, percent: float | None = None) -> None:
        self.stage_text = stage_text
        self.percent = percent

    def _render(self) -> str:
        hourglass = HOURGLASS_FRAMES[self._frame % len(HOURGLASS_FRAMES)]
        if self.percent is not None:
            bar = render_progress_bar(self.percent)
            return f"{hourglass} {self.stage_text}\n{bar}  {int(self.percent)}%"
        dots = "." * ((self._frame % 3) + 1)
        return f"{hourglass} {self.stage_text}{dots}"

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            self._frame += 1
            text = self._render()
            if text != self._last_rendered:
                try:
                    entities = build_premium_entities(text)
                    if entities:
                        await self.message.edit_text(text, entities=entities)
                    else:
                        await self.message.edit_text(text)
                    self._last_rendered = text
                except TelegramBadRequest:
                    pass
                except Exception:
                    logger.exception(LOG_PROGRESS_UPDATE_FAILED)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=STATUS_UPDATE_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            except Exception:
                pass


def tmp(name: str) -> str:
    path = os.path.join(config.TEMP_DIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def cleanup(*paths: str) -> None:
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError as e:
            logger.warning(LOG_DELETE_FAILED_FMT.format(p=p, e=e))


async def download_with_retries(bot: Bot, file_id: str, destination: str,
                                timeout_seconds: int, retries: int = 3) -> None:
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
                LOG_DOWNLOAD_RETRY_FAILED_FMT,
                attempt, retries, type(exc).__name__, exc or LOG_NO_DETAIL_MESSAGE,
            )
            if attempt < retries:
                await asyncio.sleep(2)
            else:
                raise
    if last_error is not None:
        raise last_error


async def start_job_worker(bot: Bot) -> None:
    global worker_task
    if worker_task is not None and not worker_task.done():
        return

    async def _worker() -> None:
        while True:
            queue = None
            try:
                job = developer_job_queue.get_nowait()
                queue = developer_job_queue
            except asyncio.QueueEmpty:
                try:
                    job = job_queue.get_nowait()
                    queue = job_queue
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)
                    continue

            try:
                job_id = job.get("job_id")
                if job_id in canceled_job_ids:
                    canceled_job_ids.discard(job_id)
                    tracked_jobs.pop(job_id, None)
                    user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
                    continue

                tracked_jobs[job_id] = job
                await process_job(bot, job)
            except Exception:
                logger.exception(LOG_QUEUE_PROCESS_FAILED)
            finally:
                tracked_jobs.pop(job_id, None)
                user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
                if queue is not None:
                    queue.task_done()

    worker_task = asyncio.create_task(_worker())


def get_user_rotation_seconds(user_id: int) -> float | None:
    return user_rotation_seconds.get(user_id, config.ROTATION_SECONDS)


def get_developer_vinyl_path(user_id: int) -> str:
    choice = developer_vinyl_choice.get(user_id)
    if choice == "pink":
        return config.VINYL_PINK_PATH
    if choice == "yellow":
        return config.VINYL_YELLOW_PATH
    if choice == "blue":
        return config.VINYL_BLUE_PATH
    if choice == "red":
        return config.VINYL_RED_PATH
    if choice == "green":
        return config.VINYL_GREEN_PATH
    return config.VINYL_PATH


def get_developer_shadow_path(user_id: int) -> str:
    choice = developer_vinyl_choice.get(user_id)
    if choice == "pink":
        return config.SHADOW_PINK_PATH
    if choice == "yellow":
        return config.SHADOW_YELLOW_PATH
    if choice == "blue":
        return config.SHADOW_BLUE_PATH
    if choice == "red":
        return config.SHADOW_RED_PATH
    if choice == "green":
        return config.SHADOW_GREEN_PATH
    return config.SHADOW_PATH


def get_job_priority(user_id: int) -> int:
    return 0 if user_id and user_id == config.DEVELOPER_ID else 1


def build_buy_stars_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=BTN_BUY_STARS.format(price=config.STARS_SUBSCRIPTION_PRICE),
            callback_data="buy_stars",
        )],
    ])


def enqueue_job(job: dict) -> None:
    uid = job.get("uid", 0)
    if uid != config.DEVELOPER_ID:
        limits.record_usage(uid)
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
            cleanup(*job.get("temp_paths", []))


async def process_job(bot: Bot, job: dict) -> None:
    message = job["message"]
    audio = job["audio"]
    uid = job["uid"]
    job_id = job["job_id"]

    audio_path = tmp(f"{uid}_{job_id}_audio.{audio.file_name.split('.')[-1] if audio.file_name else 'mp3'}")
    thumb_path = tmp(f"{uid}_{job_id}_thumb.jpg")
    disc_path = tmp(f"{uid}_{job_id}_disc.png")
    out_path = tmp(f"{uid}_{job_id}_out.mp4")
    job["temp_paths"] = [audio_path, thumb_path, disc_path, out_path]

    status = await reply_with_premium_emoji(message, MSG_AUDIO_RECEIVED)
    animator = StatusAnimator(status)
    animator.start()

    try:
        await bot.send_chat_action(message.chat.id, action=ChatAction.RECORD_VIDEO_NOTE)
        animator.set_stage(STAGE_DOWNLOADING_AUDIO)
        await download_with_retries(bot, audio.file_id, audio_path, timeout_seconds=300, retries=3)

        thumbnail_file_id = None
        if getattr(audio, "thumbnail", None) is not None:
            thumbnail_file_id = audio.thumbnail.file_id
        elif job.get("thumbnail_file_id"):
            thumbnail_file_id = job["thumbnail_file_id"]

        if thumbnail_file_id:
            animator.set_stage(STAGE_DOWNLOADING_THUMBNAIL)
            await download_with_retries(bot, thumbnail_file_id, thumb_path, timeout_seconds=60, retries=2)
        else:
            raise ValueError(ERR_NO_THUMBNAIL_AVAILABLE)

        duration = await get_duration(audio_path)
        if duration > config.MAX_DURATION_SECONDS and not job.get("segment_start"):
            await reply_with_premium_emoji(message, MSG_DURATION_TOO_LONG_FMT.format(duration=duration))

        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        animator.set_stage(STAGE_BUILDING_DISC)
        await asyncio.to_thread(
            build_disc, thumb_path, get_developer_vinyl_path(uid), disc_path,
            config.HOLE_RATIO, config.DISC_SIZE,
        )

        animator.set_stage(STAGE_RENDERING_VIDEO, percent=0)

        async def on_render_progress(percent: float) -> None:
            animator.set_stage(STAGE_RENDERING_VIDEO, percent=percent)

        await render_vinyl(
            disc_path, get_developer_shadow_path(uid), audio_path, out_path,
            rotation_seconds=get_user_rotation_seconds(uid),
            size=config.DISC_SIZE, fps=config.OUTPUT_FPS,
            max_duration=config.MAX_DURATION_SECONDS,
            start_offset=job.get("segment_start", 0.0),
            on_progress=on_render_progress,
        )
        if not os.path.exists(out_path):
            raise FileNotFoundError(ERR_OUTPUT_NOT_CREATED)

        animator.set_stage(STAGE_UPLOADING_VIDEO, percent=100)
        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        await message.reply_video_note(FSInputFile(out_path), length=config.DISC_SIZE)
    except Exception as e:
        logger.exception(LOG_PROCESS_JOB_FAILED)
        error_text = str(e) or repr(e) or e.__class__.__name__
        try:
            await reply_with_premium_emoji(message, MSG_PROCESSING_ERROR_FMT.format(error_text=error_text))
        except Exception:
            logger.exception(LOG_SEND_ERROR_FAILED)
    finally:
        await animator.stop()
        cleanup(audio_path, thumb_path, disc_path, out_path)
        try:
            await status.delete()
        except Exception:
            pass


def build_speed_keyboard(user_id: int) -> InlineKeyboardMarkup:
    current = get_user_rotation_seconds(user_id)
    labels = [
        (SPEED_LABEL_FULL, "full"),
        (SPEED_LABEL_8RPM, "8"),
        (SPEED_LABEL_33RPM, "33"),
        (SPEED_LABEL_45RPM, "45"),
    ]
    buttons = []
    for label, value in labels:
        if value == "full":
            selected = current in (None, 0)
        else:
            selected = current == (60 / float(value))
        mark = " ✅" if selected else ""
        buttons.append(InlineKeyboardButton(
            text=f"{label}{mark}",
            callback_data=f"speed:{value}",
            style="primary",
        ))
    buttons.append(InlineKeyboardButton(
        text=BTN_VINYL_COLOR_MENU,
        callback_data="vinyl_menu:open",
        style="primary",
    ))
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:4], [buttons[4]]])


def build_vinyl_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    current = developer_vinyl_choice.get(user_id)

    def label(text: str, value: str) -> str:
        is_selected = current == value or (current is None and value == "default")
        return f"{text} ✅" if is_selected else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label(BTN_VINYL_BLACK, "default"), callback_data="vinyl:default")],
        [
            InlineKeyboardButton(text=label(BTN_VINYL_PINK, "pink"), callback_data="vinyl:pink"),
            InlineKeyboardButton(text=label(BTN_VINYL_BLUE, "blue"), callback_data="vinyl:blue"),
        ],
        [
            InlineKeyboardButton(text=label(BTN_VINYL_YELLOW, "yellow"), callback_data="vinyl:yellow"),
            InlineKeyboardButton(text=label(BTN_VINYL_RED, "red"), callback_data="vinyl:red"),
        ],
        [InlineKeyboardButton(text=label(BTN_VINYL_GREEN, "green"), callback_data="vinyl:green")],
        [InlineKeyboardButton(text=BTN_BACK, callback_data="vinyl_menu:back")],

    ])


@router.message(F.text == "/dev")
async def on_dev(message: Message):
    if not message.from_user or message.from_user.id != config.DEVELOPER_ID:
        return
    await message.reply(MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())


def build_dev_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_VINYL_PINK, callback_data="vinyl:pink")],
        [InlineKeyboardButton(text=BTN_VINYL_DEFAULT, callback_data="vinyl:default")],
        [InlineKeyboardButton(text=BTN_VINYL_YELLOW, callback_data="vinyl:yellow")],
        [InlineKeyboardButton(text=BTN_VINYL_BLUE, callback_data="vinyl:blue")],
        [InlineKeyboardButton(text=BTN_VINYL_GREEN, callback_data="vinyl:green")],
        [InlineKeyboardButton(text=BTN_DEV_SET_MENU_IMAGE, callback_data="vinyl_menu_image:set")],
        [InlineKeyboardButton(text="✏️ تحرير النصوص", callback_data="dev_text:page:0")],
        [InlineKeyboardButton(text="🛡️ القائمة البيضاء", callback_data="dev_whitelist:open")],
    ])


def build_whitelist_keyboard() -> InlineKeyboardMarkup:
    ids = limits.list_whitelist()
    rows = [
        [InlineKeyboardButton(text=f"❌ إزالة {uid}", callback_data=f"dev_whitelist:remove:{uid}")]
        for uid in ids
    ]
    rows.append([InlineKeyboardButton(text="➕ إضافة مستخدم", callback_data="dev_whitelist:add")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="dev_whitelist:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _whitelist_text() -> str:
    ids = limits.list_whitelist()
    if not ids:
        return "🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\nلا يوجد أحد حاليًا."
    body = "\n".join(f"• {uid}" for uid in ids)
    return f"🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\n{body}"


# ============================================================
# محرر النصوص (لوحة المطور) — يعرض متغيرات texts.py بصفحات (5 بكل صفحة)
# ============================================================
def get_editable_text_names() -> list[str]:
    """يرجع أسماء كل المتغيرات النصية القابلة للتحرير بملف texts.py، مرتبة أبجديًا."""
    names = []
    for name in dir(texts_module):
        if name.startswith("_"):
            continue
        value = getattr(texts_module, name)
        if isinstance(value, str) and name.isupper():
            names.append(name)
    return sorted(names)


def build_text_list_keyboard(page: int) -> InlineKeyboardMarkup:
    names = get_editable_text_names()
    start = page * TEXTS_PER_PAGE
    page_names = names[start:start + TEXTS_PER_PAGE]

    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"dev_text:edit:{name}")]
        for name in page_names
    ]

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"dev_text:page:{page - 1}"))
    if start + TEXTS_PER_PAGE < len(names):
        nav_row.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"dev_text:page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="dev_text:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _text_list_header(page: int) -> str:
    names = get_editable_text_names()
    total = len(names)
    total_pages = max(1, math.ceil(total / TEXTS_PER_PAGE))
    return f"✏️ تحرير النصوص — صفحة {page + 1}/{total_pages} ({total} متغيّر):"


def update_text_variable(var_name: str, new_value: str) -> None:
    """
    يحدّث قيمة متغيّر نصي داخل ملف texts.py على القرص، بدون المساس بباقي الملف
    (يحافظ على الشكل الأصلي حتى لو القيمة موزّعة على أسطر متعددة). يحدّث كمان
    القيمة بالذاكرة الحالية (texts_module.VAR_NAME) حتى تنعكس فورًا على أي كود
    يقرأ القيمة عبر texts_module.VAR_NAME مباشرة.

    ملاحظة مهمة: الأماكن اللي سوّت `from texts import VAR_NAME` وقت إقلاع
    البوت (وهذا حال أغلب handlers.py) تحتفظ بالقيمة القديمة بالذاكرة لحد ما
    يعاد تشغيل البوت، رغم إن الملف على القرص والمتغيّر بموديول texts نفسه
    يكونان محدّثين فورًا.
    """
    with open(TEXTS_FILE_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == var_name:
                target_node = node
                break

    if target_node is None:
        raise ValueError(f"المتغيّر {var_name} غير موجود بملف texts.py")

    value_node = target_node.value
    start_line, start_col = value_node.lineno, value_node.col_offset
    end_line, end_col = value_node.end_lineno, value_node.end_col_offset

    lines = source.splitlines(keepends=True)
    new_literal = repr(new_value)

    if start_line == end_line:
        line = lines[start_line - 1]
        lines[start_line - 1] = line[:start_col] + new_literal + line[end_col:]
    else:
        first_line = lines[start_line - 1]
        last_line = lines[end_line - 1]
        merged = first_line[:start_col] + new_literal + last_line[end_col:]
        lines[start_line - 1:end_line] = [merged]

    new_source = "".join(lines)
    ast.parse(new_source)  # تحقق سريع إن الملف الناتج صالح بايثونيًا قبل الحفظ

    with open(TEXTS_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(new_source)

    setattr(texts_module, var_name, new_value)


@router.callback_query(F.data == "dev_whitelist:open")
async def on_dev_whitelist_open(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    await callback.message.edit_text(_whitelist_text(), reply_markup=build_whitelist_keyboard())
    await callback.answer()


@router.callback_query(F.data == "dev_whitelist:add")
async def on_dev_whitelist_add(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    awaiting_whitelist_add.add(callback.from_user.id)
    await callback.message.reply(
        "أرسل آيدي المستخدم (رقم) أو حوّل لي أي رسالة منه مباشرة."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dev_whitelist:remove:"))
async def on_dev_whitelist_remove(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    target_id = int(callback.data.split(":", 2)[2])
    limits.remove_whitelist(target_id)
    await callback.message.edit_text(_whitelist_text(), reply_markup=build_whitelist_keyboard())
    await callback.answer("تمت الإزالة ✅")


@router.callback_query(F.data == "dev_whitelist:back")
async def on_dev_whitelist_back(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    await callback.message.edit_text(MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())
    await callback.answer()


@router.message(lambda m: bool(m.from_user) and m.from_user.id in awaiting_whitelist_add)
async def on_whitelist_target_input(message: Message, bot: Bot):
    uid = message.from_user.id
    awaiting_whitelist_add.discard(uid)

    target_id = None
    if message.forward_from:
        target_id = message.forward_from.id
    elif message.text and message.text.strip().lstrip("-").isdigit():
        target_id = int(message.text.strip())

    if target_id is None:
        await message.reply(
            "ما قدرت أفهم آيدي المستخدم. أرسل رقم آيدي صحيح، أو حوّل رسالة منه "
            "(بشرط إعدادات الخصوصية عنده تسمح بإظهار هويته بالتحويل)."
        )
        return

    limits.add_whitelist(target_id)
    await message.reply(f"✅ تمت إضافة {target_id} للقائمة البيضاء.\n\n{_whitelist_text()}", reply_markup=build_whitelist_keyboard())


@router.callback_query(F.data == "vinyl_menu_image:set")
async def on_dev_set_menu_image(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    awaiting_menu_image.add(callback.from_user.id)
    await callback.message.reply(MSG_DEV_SEND_MENU_IMAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("dev_text:page:"))
async def on_dev_text_page(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    page = int(callback.data.split(":", 2)[2])
    dev_text_edit_page[callback.from_user.id] = page
    await callback.message.edit_text(_text_list_header(page), reply_markup=build_text_list_keyboard(page))
    await callback.answer()


@router.callback_query(F.data.startswith("dev_text:edit:"))
async def on_dev_text_edit(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    var_name = callback.data.split(":", 2)[2]
    current_value = getattr(texts_module, var_name, None)
    if current_value is None:
        await callback.answer("⚠️ المتغيّر غير موجود", show_alert=True)
        return

    awaiting_text_value[callback.from_user.id] = var_name
    preview = current_value if len(current_value) <= 500 else current_value[:500] + "…"
    await callback.message.reply(
        f"📝 القيمة الحالية لـ <code>{var_name}</code>:\n\n{preview}\n\n"
        "أرسل النص الجديد الآن ليحل محلها، أو أرسل /cancel_edit للإلغاء."
    )
    await callback.answer()


@router.callback_query(F.data == "dev_text:back")
async def on_dev_text_back(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    awaiting_text_value.pop(callback.from_user.id, None)
    await callback.message.edit_text(MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())
    await callback.answer()


@router.message(F.text == "/cancel_edit")
async def on_cancel_text_edit(message: Message):
    uid = message.from_user.id if message.from_user else 0
    if uid in awaiting_text_value:
        awaiting_text_value.pop(uid, None)
        await message.reply("❌ تم إلغاء التحرير.")


@router.message(lambda m: bool(m.from_user)
                and m.from_user.id == config.DEVELOPER_ID
                and m.from_user.id in awaiting_text_value)
async def on_text_value_input(message: Message, bot: Bot):
    uid = message.from_user.id
    var_name = awaiting_text_value.pop(uid)
    new_value = message.text or ""

    try:
        update_text_variable(var_name, new_value)
    except Exception as e:
        logger.exception("فشل تحديث ملف texts.py")
        await message.reply(f"❌ فشل الحفظ: {e}")
        return

    await message.reply(
        f"✅ تم حفظ <code>{var_name}</code> بنجاح.\n"
        "⚠️ التغيير مفعّل فورًا لأي كود يستخدم <code>texts_module.VAR_NAME</code> مباشرة، "
        "أما الأماكن اللي استوردت المتغيّر بالاسم مباشرة (from texts import ...) "
        "فتحتاج <b>إعادة تشغيل البوت</b> حتى يظهر فيها التغيير.",
        reply_markup=build_dev_keyboard(),
    )


@router.message(F.text.in_({"/start", "/help"}))
async def on_start(message: Message):
    await message.reply(
        MSG_START_HELP,
        reply_markup=build_speed_keyboard(message.from_user.id if message.from_user else 0),
    )

@router.callback_query(F.data == "vinyl_menu:open")
async def on_vinyl_menu_open(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id:
        await callback.message.delete()
        await callback.message.answer_photo(
            developer_menu_image_file_id,
            caption=MSG_VINYL_COLOR_INFO,
            reply_markup=build_vinyl_color_keyboard(user_id),
        )
    else:
        await callback.message.edit_text(MSG_VINYL_COLOR_INFO, reply_markup=build_vinyl_color_keyboard(user_id))
    await callback.answer()


@router.callback_query(F.data == "vinyl_menu:back")
async def on_vinyl_menu_back(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id:
        await callback.message.delete()
        await callback.message.answer(MSG_START_HELP, reply_markup=build_speed_keyboard(user_id))
    else:
        await callback.message.edit_text(MSG_START_HELP, reply_markup=build_speed_keyboard(user_id))
    await callback.answer()

@router.message(F.audio)
async def on_audio(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0
    audio = message.audio

    if uid != config.DEVELOPER_ID and not limits.can_create(uid):
        hours = max(1, math.ceil(limits.get_reset_seconds(uid) / 3600))
        await message.reply(
            MSG_LIMIT_REACHED_FMT.format(
                limit=limits.get_daily_limit(uid),
                hours=hours,
                premium_limit=config.PREMIUM_DAILY_LIMIT,
                price=config.STARS_SUBSCRIPTION_PRICE,
            ),
            reply_markup=build_buy_stars_keyboard(),
        )
        return

    if audio.file_size and audio.file_size > config.MAX_TELEGRAM_AUDIO_SIZE_BYTES:
        logger.info(LOG_FILE_TOO_LARGE)

    pending_audio[uid] = {
        "audio": audio,
        "message": message,
        "expires_at": time.time() + WIZARD_TTL_SECONDS,
        "job_id": uuid.uuid4().hex,
        "uid": uid,
    }
    wizard_state.pop(uid, None)
    pending_images.pop(uid, None)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_QUICK_CREATE, callback_data="mode:quick")],
        [InlineKeyboardButton(text=BTN_CUSTOMIZE, callback_data="mode:custom")],
        [InlineKeyboardButton(text=BTN_CANCEL, callback_data="cancel_queue")],
    ])
    await message.reply(MSG_CHOOSE_MODE, reply_markup=keyboard)


def _get_pending_audio_or_none(uid: int) -> dict | None:
    pending = pending_audio.get(uid)
    if not pending or time.time() > pending["expires_at"]:
        pending_audio.pop(uid, None)
        wizard_state.pop(uid, None)
        return None
    return pending


async def _launch_job(bot: Bot, uid: int, job: dict) -> None:
    await start_job_worker(bot)
    tracked_jobs[job["job_id"]] = job
    user_pending_jobs.setdefault(uid, set()).add(job["job_id"])
    enqueue_job(job)


@router.callback_query(F.data == "mode:quick")
async def on_mode_quick(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    pending = _get_pending_audio_or_none(uid)
    if not pending:
        await callback.answer(MSG_WIZ_EXPIRED, show_alert=True)
        return

    audio = pending["audio"]
    if audio.thumbnail:
        pending_audio.pop(uid, None)
        job = dict(pending)
        job["segment_start"] = 0.0
        await edit_text_with_premium_emoji(callback.message, MSG_JOB_QUEUED)
        await _launch_job(bot, uid, job)
    else:
        pending_images[uid] = {"quick_mode": True, "audio_message_id": pending["message"].message_id}
        await callback.message.edit_text(MSG_QUICK_NEED_IMAGE)
    await callback.answer()


@router.callback_query(F.data == "mode:custom")
async def on_mode_custom(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    pending = _get_pending_audio_or_none(uid)
    if not pending:
        await callback.answer(MSG_WIZ_EXPIRED, show_alert=True)
        return
    wizard_state[uid] = {}
    await callback.message.edit_text(MSG_WIZ_CHOOSE_COLOR, reply_markup=build_wiz_color_keyboard())
    await callback.answer()


def build_wiz_color_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_VINYL_BLACK, callback_data="wiz_color:default")],
        [
            InlineKeyboardButton(text=BTN_VINYL_PINK, callback_data="wiz_color:pink"),
            InlineKeyboardButton(text=BTN_VINYL_BLUE, callback_data="wiz_color:blue"),
        ],
        [
            InlineKeyboardButton(text=BTN_VINYL_YELLOW, callback_data="wiz_color:yellow"),
            InlineKeyboardButton(text=BTN_VINYL_RED, callback_data="wiz_color:red"),
        ],
        [InlineKeyboardButton(text=BTN_VINYL_GREEN, callback_data="wiz_color:green")],
    ])


def build_wiz_speed_keyboard() -> InlineKeyboardMarkup:
    labels = [
        (SPEED_LABEL_FULL, "full"),
        (SPEED_LABEL_8RPM, "8"),
        (SPEED_LABEL_33RPM, "33"),
        (SPEED_LABEL_45RPM, "45"),
    ]
    buttons = [InlineKeyboardButton(text=label, callback_data=f"wiz_speed:{value}") for label, value in labels]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:]])


def build_wiz_image_keyboard(has_thumbnail: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_thumbnail:
        rows.append([InlineKeyboardButton(text=BTN_WIZ_SKIP_IMAGE, callback_data="wiz_image:skip")])
    rows.append([InlineKeyboardButton(text=BTN_CANCEL, callback_data="cancel_queue")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wiz_segment_keyboard(total_duration: float) -> InlineKeyboardMarkup:
    minutes_count = max(1, math.ceil(total_duration / 60))
    buttons = []
    for i in range(minutes_count):
        start = i * 60
        if start >= total_duration:
            break
        buttons.append(InlineKeyboardButton(text=BTN_WIZ_SEGMENT_FMT.format(n=i + 1), callback_data=f"wiz_segment:{start}"))
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("wiz_color:"))
async def on_wiz_color(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    state = wizard_state.get(uid)
    if state is None or not _get_pending_audio_or_none(uid):
        await callback.answer(MSG_WIZ_EXPIRED, show_alert=True)
        return
    choice = callback.data.split(":", 1)[1]
    if choice in ("pink", "blue", "yellow", "red"):
        developer_vinyl_choice[uid] = choice
    else:
        developer_vinyl_choice.pop(uid, None)
    await callback.message.edit_text(MSG_WIZ_CHOOSE_SPEED, reply_markup=build_wiz_speed_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("wiz_speed:"))
async def on_wiz_speed(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    state = wizard_state.get(uid)
    pending = _get_pending_audio_or_none(uid)
    if state is None or not pending:
        await callback.answer(MSG_WIZ_EXPIRED, show_alert=True)
        return
    value = callback.data.split(":", 1)[1]
    user_rotation_seconds[uid] = 0.0 if value == "full" else 60 / float(value)

    has_thumb = bool(pending["audio"].thumbnail)
    await callback.message.edit_text(MSG_WIZ_CHOOSE_IMAGE, reply_markup=build_wiz_image_keyboard(has_thumb))
    await callback.answer()


@router.callback_query(F.data == "wiz_image:skip")
async def on_wiz_image_skip(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    pending = _get_pending_audio_or_none(uid)
    state = wizard_state.get(uid)
    if state is None or not pending:
        await callback.answer(MSG_WIZ_EXPIRED, show_alert=True)
        return
    if not pending["audio"].thumbnail:
        await callback.answer(MSG_WIZ_NO_IMAGE_TO_SKIP, show_alert=True)
        return
    await _wiz_advance_to_segment_or_finish(bot, uid, callback.message, callback.message.edit_text)
    await callback.answer()


async def _wiz_advance_to_segment_or_finish(bot: Bot, uid: int, target_message: Message, send_func) -> None:
    pending = pending_audio.get(uid)
    if not pending:
        return
    audio = pending["audio"]
    total_duration = audio.duration or 0

    if total_duration <= config.MAX_DURATION_SECONDS:
        await _finish_wizard(bot, uid, send_func, segment_start=0.0)
        return

    await send_func(MSG_WIZ_CHOOSE_SEGMENT, reply_markup=build_wiz_segment_keyboard(total_duration))


@router.callback_query(F.data.startswith("wiz_segment:"))
async def on_wiz_segment(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    start_seconds = float(callback.data.split(":", 1)[1])
    await _finish_wizard(bot, uid, callback.message.edit_text, segment_start=start_seconds)
    await callback.answer()


async def _finish_wizard(bot: Bot, uid: int, send_func, segment_start: float) -> None:
    pending = pending_audio.pop(uid, None)
    wizard_state.pop(uid, None)
    if not pending:
        await send_func(MSG_WIZ_EXPIRED)
        return

    job = dict(pending)
    job["uid"] = uid
    job["segment_start"] = segment_start

    entities = build_premium_entities(MSG_WIZ_STARTING)
    if entities:
        await send_func(MSG_WIZ_STARTING, entities=entities)
    else:
        await send_func(MSG_WIZ_STARTING)
    await _launch_job(bot, uid, job)


@router.callback_query(F.data == "cancel_queue")
async def on_cancel_queue(callback, bot: Bot):
    cancel_user_jobs(callback.from_user.id if callback.from_user else 0)
    await callback.message.edit_text(MSG_QUEUE_CANCELED_EDIT)
    await callback.answer(MSG_QUEUE_CANCELED_ANSWER)


@router.callback_query(F.data == "add_image")
async def on_add_image(callback, bot: Bot):
    await callback.message.reply(MSG_SEND_IMAGE_NOW)
    pending_images[callback.from_user.id] = {"waiting_for_image": True}
    await callback.answer()


@router.message(F.photo)
async def on_photo_for_audio(message: Message, bot: Bot):
    global developer_menu_image_file_id
    uid = message.from_user.id if message.from_user else 0
    if uid == config.DEVELOPER_ID and uid in awaiting_menu_image:
        awaiting_menu_image.discard(uid)
        developer_menu_image_file_id = message.photo[-1].file_id
        await message.reply(MSG_DEV_MENU_IMAGE_SAVED)
        return

    # صورة أثناء معالج التخصيص (wizard): تُستخدم كصورة غلاف جديدة ثم ننتقل لخطوة تحديد الجزء
    if uid in wizard_state:
        pending_entry = _get_pending_audio_or_none(uid)
        if not pending_entry:
            await message.reply(MSG_AUDIO_EXPIRED)
            return
        photo = message.photo[-1]
        pending_entry["thumbnail_file_id"] = photo.file_id
        await reply_with_premium_emoji(message, MSG_IMAGE_RECEIVED)
        await _wiz_advance_to_segment_or_finish(bot, uid, message, message.reply)
        return

    pending = pending_images.get(message.from_user.id)
    if not pending:
        return

    # صورة أثناء "إنشاء سريع" لملف بدون صورة مصغرة: ننشئ فورًا بالإعدادات الافتراضية
    if pending.get("quick_mode"):
        photo = message.photo[-1]
        pending_entry = _get_pending_audio_or_none(uid)
        if not pending_entry:
            pending_images.pop(uid, None)
            await message.reply(MSG_AUDIO_EXPIRED)
            return

        pending_audio.pop(uid, None)
        pending_images.pop(uid, None)

        job = dict(pending_entry)
        job["thumbnail_file_id"] = photo.file_id
        job["uid"] = uid
        job["segment_start"] = 0.0

        await reply_with_premium_emoji(message, MSG_IMAGE_RECEIVED)
        await _launch_job(bot, uid, job)
        return

    if pending.get("waiting_for_image"):
        photo = message.photo[-1]
        pending_entry = pending_audio.get(message.from_user.id)
        if not pending_entry:
            await message.reply(MSG_NO_PENDING_AUDIO)
            return

        if time.time() > pending_entry["expires_at"]:
            pending_audio.pop(message.from_user.id, None)
            pending_images.pop(message.from_user.id, None)
            await message.reply(MSG_AUDIO_EXPIRED)
            return

        pending_images[message.from_user.id] = {"photo_file_id": photo.file_id, "audio_message_id": pending.get("audio_message_id")}

        audio = pending_entry["audio"]
        job = pending_entry
        job["thumbnail_file_id"] = photo.file_id
        job["message"] = pending_entry["message"]
        job["uid"] = message.from_user.id if message.from_user else 0
        job["job_id"] = pending_entry["job_id"]
        job["segment_start"] = 0.0

        pending_audio.pop(message.from_user.id, None)
        pending_images.pop(message.from_user.id, None)

        await start_job_worker(bot)
        await reply_with_premium_emoji(message, MSG_IMAGE_RECEIVED)
        enqueue_job(job)
        return


@router.callback_query(F.data.startswith("vinyl:"))
async def on_vinyl_choice(callback, bot: Bot):
    choice = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    if choice in ("pink", "blue", "yellow", "red", "green"):
        developer_vinyl_choice[user_id] = choice
    else:
        developer_vinyl_choice.pop(user_id, None)
    await callback.message.edit_reply_markup(reply_markup=build_vinyl_color_keyboard(user_id))
    await callback.answer(MSG_VINYL_CHOICE_SAVED_ANSWER)


@router.callback_query(F.data.startswith("speed:"))
async def on_speed_selected(callback, bot: Bot):
    data = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    if data == "full":
        user_rotation_seconds[user_id] = 0.0
    else:
        user_rotation_seconds[user_id] = 60 / float(data)
    await callback.message.edit_reply_markup(reply_markup=build_speed_keyboard(user_id))
    await callback.answer(MSG_SPEED_SAVED_ANSWER)


@router.message(F.video | F.voice | F.document)
async def on_wrong_type(message: Message):
    await message.reply(MSG_WRONG_TYPE)


@router.callback_query(F.data == "buy_stars")
async def on_buy_stars(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=MSG_INVOICE_TITLE,
        description=MSG_INVOICE_DESCRIPTION_FMT.format(limit=config.PREMIUM_DAILY_LIMIT),
        payload=f"{MSG_INVOICE_PAYLOAD_PREFIX}_{uid}_{int(time.time())}",
        provider_token="",  # فارغ إجباريًا لمدفوعات نجوم تليكرام (XTR)
        currency="XTR",
        prices=[LabeledPrice(label=MSG_INVOICE_LABEL, amount=config.STARS_SUBSCRIPTION_PRICE)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0
    limits.activate_subscription(uid, config.STARS_SUBSCRIPTION_DAYS)
    logger.info(LOG_PAYMENT_RECORDED, uid)
    await reply_with_premium_emoji(message, MSG_PAYMENT_SUCCESS_FMT.format(limit=config.PREMIUM_DAILY_LIMIT))

    if config.DEVELOPER_ID:
        user = message.from_user
        try:
            await bot.send_message(
                config.DEVELOPER_ID,
                MSG_NEW_SUBSCRIBER_ADMIN_FMT.format(
                    full_name=user.full_name if user else "-",
                    username=f"@{user.username}" if user and user.username else "-",
                    user_id=uid,
                    amount=message.successful_payment.total_amount,
                    days=config.STARS_SUBSCRIPTION_DAYS,
                    limit=config.PREMIUM_DAILY_LIMIT,
                ),
            )
        except Exception:
            logger.exception("فشل إرسال إشعار المشترك الجديد للمطور")
