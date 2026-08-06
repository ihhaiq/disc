import asyncio
import ast
import html
import logging
import os
import time
import uuid
import re
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
from texts import clean_html, text_to_bold, text_to_italic, text_to_code, text_to_underline, text_to_strikethrough
import custom_texts
import math
from texts import BTN_VINYL_BLOODY
logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# تحميل النصوص المخصصة عند البدء
# ============================================================
def load_custom_texts_into_memory() -> None:
    """
    تحميل جميع النصوص المخصصة من custom_texts.json إلى الذاكرة.
    يتم استدعاء هذه الدالة مرة واحدة عند بدء البوت.
    """
    custom_list = custom_texts.list_custom()
    if custom_list:
        logger.info(f"📝 تم تحميل {len(custom_list)} نص مخصص من JSON الدائم")
        for var_name, entry in custom_list.items():
            value = entry.get("value", "")
            if var_name.startswith("EN::"):
                en_key = var_name[len("EN::"):]
                texts_module.TEXTS_EN[en_key] = value
            else:
                setattr(texts_module, var_name, value)
            editor_name = entry.get("editor_name", "Unknown")
            updated_at = entry.get("updated_at", 0)
            import datetime
            time_str = datetime.datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S") if updated_at else "?"
            logger.info(f"  • {var_name} (محرّر: {editor_name}, آخر تعديل: {time_str})")
    else:
        logger.info("ℹ️ لا توجد نصوص مخصصة محفوظة حالياً")

job_queue: asyncio.Queue[dict] = asyncio.Queue()
developer_job_queue: asyncio.Queue[dict] = asyncio.Queue()
worker_task: asyncio.Task | None = None
pending_images: dict[int, dict] = {}
pending_audio: dict[int, dict] = {}
user_rotation_seconds: dict[int, float | None] = {}
user_language: dict[int, str] = {}  # "ar" (افتراضي) أو "en"
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
awaiting_text_value: dict[int, dict] = {}  # {"var_name": str, "lang": "ar"|"en"}

HOURGLASS_FRAMES = ["⏳", "⌛"]
PROGRESS_BAR_WIDTH = 12
STATUS_UPDATE_INTERVAL_SECONDS = 2.2


# ============================================================
# دعم إيموجي بريميوم (Telegram Premium Custom Emoji)
# ============================================================
PREMIUM_EMOJI_IDS: dict[str, str] = {}

USE_PREMIUM_EMOJI = bool(PREMIUM_EMOJI_IDS)


def _utf16_len(ch: str) -> int:
    """طول المحرف بوحدات UTF-16 (المطلوب لحساب offset/length بكيانات تليكرام)."""
    return len(ch.encode("utf-16-le")) // 2


# ============================================================
# نظام الإيموجي البريميوم الذكي — استخراج وإدارة تلقائية
# ============================================================
PREMIUM_EMOJI_REGEX = r'<tg-emoji\s+emoji-id=["\'](\d+)["\']\s*>(.+?)</tg-emoji>'


def extract_premium_emojis(text: str) -> dict[str, str]:
    """استخرج كل الإيموجي البريميوم من النص تلقائياً."""
    emojis = {}
    matches = re.finditer(PREMIUM_EMOJI_REGEX, text)
    for match in matches:
        emoji_id = match.group(1)
        emoji_char = match.group(2)
        emojis[emoji_char] = emoji_id
        logger.debug(f"✅ استخرج إيموجي بريميوم: {emoji_char} (ID: {emoji_id})")
    return emojis


def clean_premium_emoji_tags(text: str) -> str:
    """شيل tags الإيموجي البريميوم من النص (احتفظ بالإيموجي نفسه)."""
    return re.sub(PREMIUM_EMOJI_REGEX, r'\2', text)


def build_premium_entities_from_text(text: str) -> list[MessageEntity] | None:
    """ابني entities للإيموجي البريميوم من النص."""
    emojis_dict = extract_premium_emojis(text)
    
    if not emojis_dict:
        return None
    
    clean_text = clean_premium_emoji_tags(text)
    
    entities: list[MessageEntity] = []
    offset = 0
    
    for ch in clean_text:
        length = _utf16_len(ch)
        
        if ch in emojis_dict:
            emoji_id = emojis_dict[ch]
            entities.append(MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=length,
                custom_emoji_id=emoji_id,
            ))
            logger.debug(f"✅ أضفت entity: {ch} (offset={offset}, length={length}, id={emoji_id})")
        
        offset += length
    
    return entities if entities else None


def validate_premium_emoji_syntax(text: str) -> tuple[bool, str]:
    """تحقق من صحة صيغة الإيموجي البريميوم."""
    open_tags = len(re.findall(r'<tg-emoji', text))
    close_tags = len(re.findall(r'</tg-emoji>', text))
    
    if open_tags != close_tags:
        return False, f"❌ عدد tags غير متطابق: {open_tags} فتح و {close_tags} إغلاق"
    
    invalid_ids = re.findall(r'<tg-emoji\s+emoji-id=["\']([^"\']+)["\']', text)
    for emoji_id in invalid_ids:
        if not emoji_id.isdigit():
            return False, f"❌ emoji-id يجب أن يكون أرقام فقط: '{emoji_id}'"
    
    empty_tags = re.findall(r'<tg-emoji[^>]*>\s*</tg-emoji>', text)
    if empty_tags:
        return False, "❌ tag الإيموجي فارغ، ضع إيموجي أو نص بالداخل"
    
    return True, ""


# ============================================================
# دوال مساعدة لتنسيق النصوص — للمطور
# ============================================================
def fmt_bold(text: str) -> str:
    """تحويل نص إلى عريض: **النص** ← <b>النص</b>"""
    return text_to_bold(text)


def fmt_italic(text: str) -> str:
    """تحويل نص إلى مائل: *النص* ← <i>النص</i>"""
    return text_to_italic(text)


def fmt_code(text: str) -> str:
    """تحويل نص إلى كود: `النص` ← <code>النص</code>"""
    return text_to_code(text)


def fmt_underline(text: str) -> str:
    """تحويل نص إلى مسطر: __النص__ ← <u>النص</u>"""
    return text_to_underline(text)


def fmt_strikethrough(text: str) -> str:
    """تحويل نص إلى مشطوب: ~~النص~~ ← <s>النص</s>"""
    return text_to_strikethrough(text)


async def reply_with_premium_emoji(message: Message, text: str, **kwargs) -> Message:
    """
    أرسل رسالة مع دعم كامل للإيموجي البريميوم والـ HTML.
    
    يتولى تلقائياً:
    - استخراج أكواد الإيموجي البريميوم
    - تحويل HTML غير المدعوم
    - بناء entities صحيحة
    """
    # حوّل النص تلقائياً (تنظيف HTML)
    text = sanitize_and_convert_text(text)
    
    # استخرج الإيموجي البريميوم
    emojis_dict = extract_premium_emojis(text)
    
    if emojis_dict:
        # نظّف tags الإيموجي من النص
        clean_text = clean_premium_emoji_tags(text)
        
        # ابني entities للإيموجي
        entities = build_premium_entities_from_text(text)
        
        try:
            if entities:
                return await message.reply(clean_text, entities=entities, **kwargs)
            return await message.reply(clean_text, **kwargs)
        except TelegramBadRequest as e:
            logger.warning(f"فشل إرسال رسالة مع إيموجي بريميوم: {e}, سيتم الإرسال بدونها")
            return await message.reply(clean_text, **kwargs)
    
    # إذا ما فيه إيموجي بريميوم، أرسل عادي
    try:
        return await message.reply(text, **kwargs)
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            logger.warning("فشل تفسير HTML، سيُرسل كنص خام: %s", e)
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "entities"}
            return await message.reply(html.escape(text), **clean_kwargs)
        raise


async def edit_text_with_premium_emoji(message: Message, text: str, **kwargs) -> Message:
    """
    عدّل نص رسالة مع دعم الإيموجي البريميوم.
    """
    # حوّل النص تلقائياً
    text = sanitize_and_convert_text(text)
    
    # استخرج الإيموجي البريميوم
    emojis_dict = extract_premium_emojis(text)
    
    if emojis_dict:
        # نظّف tags الإيموجي
        clean_text = clean_premium_emoji_tags(text)
        
        # ابني entities
        entities = build_premium_entities_from_text(text)
        
        try:
            if entities:
                return await message.edit_text(clean_text, entities=entities, **kwargs)
            return await message.edit_text(clean_text, **kwargs)
        except TelegramBadRequest as e:
            logger.warning(f"فشل تعديل الرسالة مع إيموجي بريميوم: {e}")
            return await message.edit_text(clean_text, **kwargs)
    
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            logger.warning("فشل تفسير HTML في التعديل")
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "entities"}
            return await message.edit_text(html.escape(text), **clean_kwargs)
        raise


# ============================================================
# دعم الرسائل الغنية (Rich Messages) — Bot API 10.1+
# ============================================================
def escape_rich_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


async def send_rich_message(bot: Bot, chat_id: int, html_content: str,
                             reply_to_message_id: int | None = None,
                             reply_markup: InlineKeyboardMarkup | None = None) -> Message:
    reply_params = ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
    try:
        return await bot.send_rich_message(
            chat_id=chat_id,
            content=InputRichMessage(content=html_content, format="html"),
            reply_parameters=reply_params,
            reply_markup=reply_markup,
        )
    except AttributeError:
        logger.warning("sendRichMessage غير مدعوم بهالنسخة من aiogram، الرجوع لرسالة عادية")
    except Exception:
        logger.exception("فشل إرسال Rich Message، الرجوع لرسالة عادية")

    return await bot.send_message(chat_id=chat_id, text=html_content, reply_markup=reply_markup)


async def reply_rich(message: Message, bot: Bot, html_content: str,
                      reply_markup: InlineKeyboardMarkup | None = None) -> Message:
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
        self.stage_text = texts_module.STAGE_PREPARING
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
                    entities = build_premium_entities_from_text(text)
                    if entities:
                        await self.message.edit_text(text, entities=entities)
                    else:
                        await self.message.edit_text(text)
                    self._last_rendered = text
                except TelegramBadRequest:
                    pass
                except Exception:
                    logger.exception(texts_module.LOG_PROGRESS_UPDATE_FAILED)
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
            logger.warning(texts_module.LOG_DELETE_FAILED_FMT.format(p=p, e=e))


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
                texts_module.LOG_DOWNLOAD_RETRY_FAILED_FMT,
                attempt, retries, type(exc).__name__, exc or texts_module.LOG_NO_DETAIL_MESSAGE,
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
                logger.exception(texts_module.LOG_QUEUE_PROCESS_FAILED)
            finally:
                tracked_jobs.pop(job_id, None)
                user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
                if queue is not None:
                    queue.task_done()

    worker_task = asyncio.create_task(_worker())


def get_user_rotation_seconds(user_id: int) -> float | None:
    return user_rotation_seconds.get(user_id, config.ROTATION_SECONDS)


# ============================================================
# نظام اللغات (Language System)
# ============================================================
def get_user_lang(user_id: int) -> str:
    """يرجّع لغة المستخدم الحالية: 'ar' أو 'en' (الافتراضي عربي)."""
    return user_language.get(user_id, "ar")


def tr(var_name: str, user_id: int) -> str:
    """
    يرجّع النص المترجم حسب لغة المستخدم.
    - عربي (الافتراضي): من texts_module (يشمل أي تعديل مخصص من لوحة المطور)
    - إنجليزي: من TEXTS_EN، ولو غير موجودة فيها يرجع للعربي تلقائيًا
    """
    if get_user_lang(user_id) == "en":
        en_value = texts_module.TEXTS_EN.get(var_name)
        if en_value is not None:
            return en_value
    return getattr(texts_module, var_name, "")


def build_lang_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=texts_module.BTN_LANG,
        callback_data="lang:toggle",
        style="success",
    )


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
    if choice == "bloody" :
        return config.VINYL_BLOODY_PATH
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
    if choice == "bloody":
        return config.SHADOW_PINK_PATH
    return config.SHADOW_PATH


def get_job_priority(user_id: int) -> int:
    return 0 if user_id and user_id == config.DEVELOPER_ID else 1


def build_buy_stars_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=tr("BTN_BUY_STARS", user_id).format(price=config.STARS_SUBSCRIPTION_PRICE),
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

    status = await reply_with_premium_emoji(message, tr("MSG_AUDIO_RECEIVED", uid))
    animator = StatusAnimator(status)
    animator.start()

    try:
        await bot.send_chat_action(message.chat.id, action=ChatAction.RECORD_VIDEO_NOTE)
        animator.set_stage(tr("STAGE_DOWNLOADING_AUDIO", uid))
        await download_with_retries(bot, audio.file_id, audio_path, timeout_seconds=300, retries=3)

        thumbnail_file_id = None
        if getattr(audio, "thumbnail", None) is not None:
            thumbnail_file_id = audio.thumbnail.file_id
        elif job.get("thumbnail_file_id"):
            thumbnail_file_id = job["thumbnail_file_id"]

        if thumbnail_file_id:
            animator.set_stage(tr("STAGE_DOWNLOADING_THUMBNAIL", uid))
            await download_with_retries(bot, thumbnail_file_id, thumb_path, timeout_seconds=60, retries=2)
        else:
            raise ValueError(texts_module.ERR_NO_THUMBNAIL_AVAILABLE)

        duration = await get_duration(audio_path)
        if duration > config.MAX_DURATION_SECONDS and not job.get("segment_start"):
            await reply_with_premium_emoji(message, tr("MSG_DURATION_TOO_LONG_FMT", uid).format(duration=duration))

        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        animator.set_stage(tr("STAGE_BUILDING_DISC", uid))
        await asyncio.to_thread(
            build_disc, thumb_path, get_developer_vinyl_path(uid), disc_path,
            config.HOLE_RATIO, config.DISC_SIZE,
        )

        animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=0)

        async def on_render_progress(percent: float) -> None:
            animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=percent)

        await render_vinyl(
            disc_path, get_developer_shadow_path(uid), audio_path, out_path,
            rotation_seconds=get_user_rotation_seconds(uid),
            size=config.DISC_SIZE, fps=config.OUTPUT_FPS,
            max_duration=config.MAX_DURATION_SECONDS,
            start_offset=job.get("segment_start", 0.0),
            on_progress=on_render_progress,
        )
        if not os.path.exists(out_path):
            raise FileNotFoundError(texts_module.ERR_OUTPUT_NOT_CREATED)

        animator.set_stage(tr("STAGE_UPLOADING_VIDEO", uid), percent=100)
        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        await message.reply_video_note(FSInputFile(out_path), length=config.DISC_SIZE)
    except Exception as e:
        logger.exception(texts_module.LOG_PROCESS_JOB_FAILED)
        error_text = str(e) or repr(e) or e.__class__.__name__
        try:
            await reply_with_premium_emoji(message, tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text=error_text))
        except Exception:
            logger.exception(texts_module.LOG_SEND_ERROR_FAILED)
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
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
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
        text=tr("BTN_VINYL_COLOR_MENU", user_id),
        callback_data="vinyl_menu:open",
        style="danger",
    ))
    buttons.append(build_lang_button())
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:4], [buttons[4], buttons[5]]])


def build_vinyl_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    current = developer_vinyl_choice.get(user_id)

    def label(var_name: str, value: str) -> str:
        text = tr(var_name, user_id)
        is_selected = current == value or (current is None and value == "default")
        return f"{text} ✅" if is_selected else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label("BTN_VINYL_BLACK", "default"), callback_data="vinyl:default")],
        [
            InlineKeyboardButton(text=label("BTN_VINYL_PINK", "pink"), callback_data="vinyl:pink"),
            InlineKeyboardButton(text=label("BTN_VINYL_BLUE", "blue"), callback_data="vinyl:blue"),
        ],
        [
            InlineKeyboardButton(text=label("BTN_VINYL_YELLOW", "yellow"), callback_data="vinyl:yellow"),
            InlineKeyboardButton(text=label("BTN_VINYL_RED", "red"), callback_data="vinyl:red"),
        ],
        [
            InlineKeyboardButton(text=label("BTN_VINYL_GREEN", "green"), callback_data="vinyl:green"),
            InlineKeyboardButton(text=label("BTN_VINYL_BLOODY", "bloody"), callback_data="vinyl:bloody"),
        ],
        [InlineKeyboardButton(text=tr("BTN_BACK", user_id), callback_data="vinyl_menu:back")],

    ])


@router.message(F.text == "/dev")
async def on_dev(message: Message):
    if not message.from_user or message.from_user.id != config.DEVELOPER_ID:
        return
    await message.reply(texts_module.MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())


def build_dev_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts_module.BTN_VINYL_PINK, callback_data="vinyl:pink")],
        [InlineKeyboardButton(text=texts_module.BTN_VINYL_DEFAULT, callback_data="vinyl:default")],
        [InlineKeyboardButton(text=texts_module.BTN_VINYL_YELLOW, callback_data="vinyl:yellow")],
        [InlineKeyboardButton(text=texts_module.BTN_VINYL_BLUE, callback_data="vinyl:blue")],
        [InlineKeyboardButton(text=texts_module.BTN_VINYL_GREEN, callback_data="vinyl:green")],
        [InlineKeyboardButton(text=texts_module.BTN_DEV_SET_MENU_IMAGE, callback_data="vinyl_menu_image:set")],
        [InlineKeyboardButton(text="✏️ تحرير النصوص (عربي)", callback_data="dev_text:page:ar:0")],
        [InlineKeyboardButton(text="✏️ Edit Texts (English)", callback_data="dev_text:page:en:0")],
        [InlineKeyboardButton(text="🛡️ القائمة البيضاء", callback_data="dev_whitelist:open")],
    ])


def build_whitelist_keyboard() -> InlineKeyboardMarkup:
    ids = limits.list_whitelist()
    rows = [
        [InlineKeyboardButton(text=f"❌ إزالة {uid}", callback_data=f"dev_whitelist:remove:{uid}")]
        for uid in ids
    ]
    rows.append([InlineKeyboardButton(text="➕ إضافة مستخدم", callback_data="dev_whitelist:add")])
    rows.append([InlineKeyboardButton(text=texts_module.BTN_BACK, callback_data="dev_whitelist:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _whitelist_text() -> str:
    ids = limits.list_whitelist()
    if not ids:
        return "🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\nلا يوجد أحد حاليًا."
    body = "\n".join(f"• {uid}" for uid in ids)
    return f"🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\n{body}"


# ============================================================
# محرر النصوص (لوحة المطور) — يعرض متغيرات texts.py بصفحات (5 بكل صفحة)
# يدعم لغتين منفصلتين: "ar" (نصوص texts.py الأصلية) و "en" (قاموس TEXTS_EN)
# ============================================================
def get_editable_text_names(lang: str = "ar") -> list[str]:
    if lang == "en":
        return sorted(texts_module.TEXTS_EN.keys())
    names = []
    for name in dir(texts_module):
        if name.startswith("_"):
            continue
        value = getattr(texts_module, name)
        if isinstance(value, str) and name.isupper():
            names.append(name)
    return sorted(names)


def get_editable_text_value(var_name: str, lang: str) -> str | None:
    if lang == "en":
        return texts_module.TEXTS_EN.get(var_name)
    return getattr(texts_module, var_name, None)


def build_text_list_keyboard(page: int, lang: str = "ar") -> InlineKeyboardMarkup:
    names = get_editable_text_names(lang)
    start = page * TEXTS_PER_PAGE
    page_names = names[start:start + TEXTS_PER_PAGE]

    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"dev_text:edit:{lang}:{name}")]
        for name in page_names
    ]

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"dev_text:page:{lang}:{page - 1}"))
    if start + TEXTS_PER_PAGE < len(names):
        nav_row.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"dev_text:page:{lang}:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=texts_module.BTN_BACK, callback_data="dev_text:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _text_list_header(page: int, lang: str = "ar") -> str:
    names = get_editable_text_names(lang)
    total = len(names)
    total_pages = max(1, math.ceil(total / TEXTS_PER_PAGE))
    lang_label = "English" if lang == "en" else "عربي"
    return f"✏️ تحرير النصوص ({lang_label}) — صفحة {page + 1}/{total_pages} ({total} متغيّر):"


def process_text_markup(text: str) -> str:
    """
    معالجة النصوص المدخلة من المطور: تحويل صيغ خاصة لـ HTML Telegram
    
    الصيغ المدعومة:
    - **نص** أو __نص__ → <b>نص</b> (عريض)
    - *نص* أو _نص_ → <i>نص</i> (مائل)
    - `نص` → <code>نص</code> (كود)
    - ~~نص~~ → <s>نص</s> (مشطوب)
    - <<نص>> → <u>نص</u> (مسطر)
    - HTML الخام (مثل <h1>, <p>) يتم تنظيفه
    """
    # تحويل الصيغ الخاصة
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)  # **نص** → <b>
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)      # __نص__ → <b>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)      # *نص* → <i> (بحذر من **)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)        # _نص_ → <i>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)  # `نص` → <code>
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)      # ~~نص~~ → <s>
    text = re.sub(r'<<(.+?)>>', r'<u>\1</u>', text)      # <<نص>> → <u>
    
    # تنظيف HTML غير المدعوم
    text = texts_module.clean_html(text)
    
    return text


def update_text_variable(var_name: str, new_value: str, editor_id: int = 0,
                          editor_name: str = "", lang: str = "ar") -> None:
    """
    احفظ التعديل بـ JSON دائم (custom_texts.json) بدل تعديل texts.py مباشرة.
    - يحفظ فوراً بـ DATA_DIR (مربوط بـ Railway Volume)
    - يبقى بعد Restart/Redeploy
    - يحتفظ بمعلومات المحرّر والوقت
    - يدعم لغتين منفصلتين: "ar" (يعدّل texts.py) و "en" (يعدّل TEXTS_EN)
    """
    # معالجة النص (تحويل الصيغ الخاصة + تنظيف HTML)
    processed_value = process_text_markup(new_value)

    if lang == "en":
        # تحقق إن المتغيّر موجود أصلاً بقاموس TEXTS_EN
        if var_name not in texts_module.TEXTS_EN:
            raise ValueError(f"المتغيّر {var_name} غير موجود بقاموس TEXTS_EN")

        # احفظ بـ custom_texts.json بمفتاح مميز عشان ما يتعارض مع النسخة العربية
        custom_texts.set_custom(f"EN::{var_name}", processed_value, editor_id=editor_id, editor_name=editor_name)

        # حدّث الذاكرة الحالية أيضاً
        texts_module.TEXTS_EN[var_name] = processed_value
        return

    # تحقق إن المتغيّر موجود بـ texts.py
    if not hasattr(texts_module, var_name):
        raise ValueError(f"المتغيّر {var_name} غير موجود بملف texts.py")

    # احفظ بـ custom_texts.json (دائم ويبقى بعد Restart)
    custom_texts.set_custom(var_name, processed_value, editor_id=editor_id, editor_name=editor_name)

    # حدّث الذاكرة الحالية أيضاً (حتى لا تحتاج restart)
    setattr(texts_module, var_name, processed_value)


async def validate_html_text(bot: Bot, chat_id: int, text: str) -> str | None:
    """
    يتحقق إن النص صالح كـ HTML بمعايير تليكرام (وسوم مدعومة + tg-emoji بمعرفات
    صحيحة) عن طريق محاولة إرسال رسالة تجريبية صامتة ثم حذفها فورًا.
    يرجّع None لو تمام، أو نص الخطأ لو فيه مشكلة.
    """
    try:
        test_msg = await bot.send_message(chat_id, text, disable_notification=True)
        await test_msg.delete()
        return None
    except TelegramBadRequest as e:
        return str(e)


def sanitize_and_convert_text(text: str) -> str:
    """
    يأخذ أي نص (HTML خام أو نص عادي) ويحوّله إلى Telegram HTML صحيح.
    - إذا كان فيه tags HTML غير مدعومة ← يشيلها ويحتفظ بالمحتوى
    - إذا كان نص عادي بدون tags ← يرجعه كما هو
    - إذا كان فيه تعارضات HTML ← يصلحها تلقائياً
    """
    if not text:
        return ""
    
    # لو النص فيه tags HTML، حوّله إلى صيغة Telegram الصحيحة
    if '<' in text and '>' in text:
        return clean_html(text)
    
    # لو النص عادي بدون tags، أرجعه كما هو
    return text


async def safe_reply(message: Message, text: str, **kwargs) -> Message:
    """
    نفس message.reply لكن ذكي:
    - يحول HTML/نص خام تلقائياً إلى صيغة Telegram الصحيحة
    - لو صار خطأ "can't parse entities" ← يعاد المحاولة بنص خام
    """
    # حوّل النص تلقائياً أولاً
    text = sanitize_and_convert_text(text)
    
    try:
        return await message.reply(text, **kwargs)
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            logger.warning("فشل تفسير HTML بنص محفوظ مسبقًا، سيُرسل كنص خام: %s", e)
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "parse_mode"}
            return await message.reply(html.escape(text), parse_mode=None, **clean_kwargs)
        raise


@router.callback_query(F.data == "dev_whitelist:open")
async def on_dev_whitelist_open(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    await callback.message.edit_text(_whitelist_text(), reply_markup=build_whitelist_keyboard())
    await callback.answer()


@router.callback_query(F.data == "dev_whitelist:add")
async def on_dev_whitelist_add(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    awaiting_whitelist_add.add(callback.from_user.id)
    await callback.message.reply(
        "أرسل آيدي المستخدم (رقم) أو حوّل لي أي رسالة منه مباشرة."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dev_whitelist:remove:"))
async def on_dev_whitelist_remove(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    target_id = int(callback.data.split(":", 2)[2])
    limits.remove_whitelist(target_id)
    await callback.message.edit_text(_whitelist_text(), reply_markup=build_whitelist_keyboard())
    await callback.answer("تمت الإزالة ✅")


@router.callback_query(F.data == "dev_whitelist:back")
async def on_dev_whitelist_back(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    await callback.message.edit_text(texts_module.MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())
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
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    awaiting_menu_image.add(callback.from_user.id)
    await callback.message.reply(texts_module.MSG_DEV_SEND_MENU_IMAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("dev_text:page:"))
async def on_dev_text_page(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    _, _, lang, page_str = callback.data.split(":", 3)
    page = int(page_str)
    dev_text_edit_page[callback.from_user.id] = page
    await callback.message.edit_text(_text_list_header(page, lang), reply_markup=build_text_list_keyboard(page, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("dev_text:edit:"))
async def on_dev_text_edit(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    _, _, lang, var_name = callback.data.split(":", 3)
    current_value = get_editable_text_value(var_name, lang)
    if current_value is None:
        await callback.answer("⚠️ المتغيّر غير موجود", show_alert=True)
        return

    awaiting_text_value[callback.from_user.id] = {"var_name": var_name, "lang": lang}
    preview = current_value if len(current_value) <= 500 else current_value[:500] + "…"
    escaped_preview = html.escape(preview)
    await callback.message.reply(
        f"📝 القيمة الحالية لـ <code>{var_name}</code>:\n\n<code>{escaped_preview}</code>\n\n"
        "أرسل النص الجديد الآن ليحل محلها. لإيموجي بريميوم استخدم صيغة:\n"
        "<code>&lt;tg-emoji emoji-id='123'&gt;😀&lt;/tg-emoji&gt;</code>\n"
        "(بايدي رقمي صحيح ومحتوى fallback بالداخل) وسأتحقق منه قبل الحفظ.\n"
        "أو أرسل /cancel_edit للإلغاء."
    )
    await callback.answer()


@router.callback_query(F.data == "dev_text:back")
async def on_dev_text_back(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    awaiting_text_value.pop(callback.from_user.id, None)
    await callback.message.edit_text(texts_module.MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())
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
    pending = awaiting_text_value.pop(uid)
    var_name = pending["var_name"]
    lang = pending["lang"]
    new_value = message.text or ""

    # 1️⃣ تحقق من صيغة الإيموجي البريميوم
    is_valid_emoji, emoji_error = validate_premium_emoji_syntax(new_value)
    if not is_valid_emoji:
        awaiting_text_value[uid] = pending
        await message.reply(
            f"❌ خطأ في صيغة الإيموجي البريميوم:\n"
            f"<code>{html.escape(emoji_error)}</code>\n\n"
            "الصيغة الصحيحة:\n"
            "<code>&lt;tg-emoji emoji-id='123'&gt;🎶&lt;/tg-emoji&gt;</code>\n\n"
            "صحّح النص وأرسله مرة ثانية، أو أرسل /cancel_edit للإلغاء."
        )
        return

    # 2️⃣ تحقق من HTML العام
    html_error = await validate_html_text(bot, message.chat.id, new_value)
    if html_error:
        awaiting_text_value[uid] = pending
        await message.reply(
            "❌ النص فيه خطأ HTML ولن يُحفظ حتى يصير صحيحًا:\n"
            f"<code>{html.escape(html_error)}</code>\n\n"
            "صحّح النص وأرسله مرة ثانية، أو أرسل /cancel_edit للإلغاء."
        )
        return

    # 3️⃣ استخرج أكواد الإيموجي البريميوم تلقائياً
    emojis_found = extract_premium_emojis(new_value)
    
    try:
        # احفظ مع معلومات المحرّر
        user = message.from_user
        editor_name = user.first_name or user.username or f"User{uid}" if user else "Unknown"
        update_text_variable(var_name, new_value, editor_id=uid, editor_name=editor_name, lang=lang)
    except Exception as e:
        logger.exception("فشل حفظ النص المخصص")
        await message.reply(f"❌ فشل الحفظ:\n<code>{html.escape(str(e))}</code>")
        return

    # 4️⃣ رسالة النجاح مع معلومات الإيموجي
    emoji_info = ""
    if emojis_found:
        emoji_list = "\n".join([f"  • {emoji} (ID: {emoji_id})" for emoji, emoji_id in emojis_found.items()])
        emoji_info = f"\n\n🎯 الإيموجي البريميوم المكتشفة تلقائياً:\n{emoji_list}"

    lang_label = "English" if lang == "en" else "عربي"
    success_msg = (
        f"✅ تم حفظ <code>{var_name}</code> ({lang_label}) بنجاح بشكل <b>دائم</b>! 🎉\n"
        f"✨ التغيير مفعّل فوراً وسيبقى حتى بعد إعادة تشغيل البوت.\n"
        f"👤 محرّر: {editor_name} (ID: {uid})"
        f"{emoji_info}"
    )
    
    await message.reply(success_msg, reply_markup=build_dev_keyboard())


@router.message(F.text.in_({"/start", "/help"}))
async def on_start(message: Message):
    uid = message.from_user.id if message.from_user else 0
    await safe_reply(
        message,
        tr("MSG_START_HELP", uid),
        reply_markup=build_speed_keyboard(uid),
    )

@router.callback_query(F.data == "vinyl_menu:open")
async def on_vinyl_menu_open(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id:
        await callback.message.delete()
        await callback.message.answer_photo(
            developer_menu_image_file_id,
            caption=tr("MSG_VINYL_COLOR_INFO", user_id),
            reply_markup=build_vinyl_color_keyboard(user_id),
        )
    else:
        await callback.message.edit_text(tr("MSG_VINYL_COLOR_INFO", user_id), reply_markup=build_vinyl_color_keyboard(user_id))
    await callback.answer()


@router.callback_query(F.data == "vinyl_menu:back")
async def on_vinyl_menu_back(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id:
        await callback.message.delete()
        await callback.message.answer(tr("MSG_START_HELP", user_id), reply_markup=build_speed_keyboard(user_id))
    else:
        await callback.message.edit_text(tr("MSG_START_HELP", user_id), reply_markup=build_speed_keyboard(user_id))
    await callback.answer()


@router.callback_query(F.data == "lang:toggle")
async def on_lang_toggle(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    new_lang = "en" if get_user_lang(user_id) == "ar" else "ar"
    user_language[user_id] = new_lang

    # نعيد رسم الرسالة الحالية باللغة الجديدة (نتعامل مع رسالة البداية أو قائمة الألوان)
    current_markup = callback.message.reply_markup
    is_color_menu = bool(current_markup and any(
        btn.callback_data and btn.callback_data.startswith("vinyl:")
        for row in current_markup.inline_keyboard for btn in row
    ))
    try:
        if is_color_menu:
            await callback.message.edit_text(
                tr("MSG_VINYL_COLOR_INFO", user_id),
                reply_markup=build_vinyl_color_keyboard(user_id),
            )
        else:
            await callback.message.edit_text(
                tr("MSG_START_HELP", user_id),
                reply_markup=build_speed_keyboard(user_id),
            )
    except TelegramBadRequest:
        pass
    await callback.answer("✅ EN" if new_lang == "en" else "✅ AR")

@router.message(F.audio)
async def on_audio(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0
    audio = message.audio

    if uid != config.DEVELOPER_ID and not limits.can_create(uid):
        hours = max(1, math.ceil(limits.get_reset_seconds(uid) / 3600))
        await message.reply(
            tr("MSG_LIMIT_REACHED_FMT", uid).format(
                limit=limits.get_daily_limit(uid),
                hours=hours,
                premium_limit=config.PREMIUM_DAILY_LIMIT,
                price=config.STARS_SUBSCRIPTION_PRICE,
            ),
            reply_markup=build_buy_stars_keyboard(uid),
        )
        return

    if audio.file_size and audio.file_size > config.MAX_TELEGRAM_AUDIO_SIZE_BYTES:
        logger.info(texts_module.LOG_FILE_TOO_LARGE)

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
        [InlineKeyboardButton(text=tr("BTN_QUICK_CREATE", uid), callback_data="mode:quick")],
        [InlineKeyboardButton(text=tr("BTN_CUSTOMIZE", uid), callback_data="mode:custom")],
        [InlineKeyboardButton(text=tr("BTN_CANCEL", uid), callback_data="cancel_queue")],
    ])
    await message.reply(tr("MSG_CHOOSE_MODE", uid), reply_markup=keyboard)


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
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return

    audio = pending["audio"]
    if audio.thumbnail:
        pending_audio.pop(uid, None)
        job = dict(pending)
        job["segment_start"] = 0.0
        await edit_text_with_premium_emoji(callback.message, tr("MSG_JOB_QUEUED", uid))
        await _launch_job(bot, uid, job)
    else:
        pending_images[uid] = {"quick_mode": True, "audio_message_id": pending["message"].message_id}
        await callback.message.edit_text(tr("MSG_QUICK_NEED_IMAGE", uid))
    await callback.answer()


@router.callback_query(F.data == "mode:custom")
async def on_mode_custom(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    pending = _get_pending_audio_or_none(uid)
    if not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    wizard_state[uid] = {}
    await callback.message.edit_text(tr("MSG_WIZ_CHOOSE_COLOR", uid), reply_markup=build_wiz_color_keyboard(uid))
    await callback.answer()


def build_wiz_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr("BTN_VINYL_BLACK", user_id), callback_data="wiz_color:default")],
        [
            InlineKeyboardButton(text=tr("BTN_VINYL_PINK", user_id), callback_data="wiz_color:pink"),
            InlineKeyboardButton(text=tr("BTN_VINYL_BLUE", user_id), callback_data="wiz_color:blue"),
        ],
        [
            InlineKeyboardButton(text=tr("BTN_VINYL_YELLOW", user_id), callback_data="wiz_color:yellow"),
            InlineKeyboardButton(text=tr("BTN_VINYL_RED", user_id), callback_data="wiz_color:red"),
        ],
        [InlineKeyboardButton(text=tr("BTN_VINYL_GREEN", user_id), callback_data="wiz_color:green")],
    ])


def build_wiz_speed_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    labels = [
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = [InlineKeyboardButton(text=label, callback_data=f"wiz_speed:{value}") for label, value in labels]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:]])


def build_wiz_image_keyboard(has_thumbnail: bool, user_id: int = 0) -> InlineKeyboardMarkup:
    rows = []
    if has_thumbnail:
        rows.append([InlineKeyboardButton(text=tr("BTN_WIZ_SKIP_IMAGE", user_id), callback_data="wiz_image:skip")])
    rows.append([InlineKeyboardButton(text=tr("BTN_CANCEL", user_id), callback_data="cancel_queue")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wiz_segment_keyboard(total_duration: float, user_id: int = 0) -> InlineKeyboardMarkup:
    minutes_count = max(1, math.ceil(total_duration / 60))
    buttons = []
    for i in range(minutes_count):
        start = i * 60
        if start >= total_duration:
            break
        buttons.append(InlineKeyboardButton(text=tr("BTN_WIZ_SEGMENT_FMT", user_id).format(n=i + 1), callback_data=f"wiz_segment:{start}"))
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("wiz_color:"))
async def on_wiz_color(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    state = wizard_state.get(uid)
    if state is None or not _get_pending_audio_or_none(uid):
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    choice = callback.data.split(":", 1)[1]
    if choice in ("pink", "blue", "yellow", "red"):
        developer_vinyl_choice[uid] = choice
    else:
        developer_vinyl_choice.pop(uid, None)
    await callback.message.edit_text(tr("MSG_WIZ_CHOOSE_SPEED", uid), reply_markup=build_wiz_speed_keyboard(uid))
    await callback.answer()


@router.callback_query(F.data.startswith("wiz_speed:"))
async def on_wiz_speed(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    state = wizard_state.get(uid)
    pending = _get_pending_audio_or_none(uid)
    if state is None or not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    value = callback.data.split(":", 1)[1]
    user_rotation_seconds[uid] = 0.0 if value == "full" else 60 / float(value)

    has_thumb = bool(pending["audio"].thumbnail)
    await callback.message.edit_text(tr("MSG_WIZ_CHOOSE_IMAGE", uid), reply_markup=build_wiz_image_keyboard(has_thumb, uid))
    await callback.answer()


@router.callback_query(F.data == "wiz_image:skip")
async def on_wiz_image_skip(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    pending = _get_pending_audio_or_none(uid)
    state = wizard_state.get(uid)
    if state is None or not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    if not pending["audio"].thumbnail:
        await callback.answer(tr("MSG_WIZ_NO_IMAGE_TO_SKIP", uid), show_alert=True)
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

    await send_func(tr("MSG_WIZ_CHOOSE_SEGMENT", uid), reply_markup=build_wiz_segment_keyboard(total_duration, uid))


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
        await send_func(tr("MSG_WIZ_EXPIRED", uid))
        return

    job = dict(pending)
    job["uid"] = uid
    job["segment_start"] = segment_start

    starting_text = tr("MSG_WIZ_STARTING", uid)
    entities = build_premium_entities_from_text(starting_text)
    if entities:
        await send_func(starting_text, entities=entities)
    else:
        await send_func(starting_text)
    await _launch_job(bot, uid, job)


@router.callback_query(F.data == "cancel_queue")
async def on_cancel_queue(callback, bot: Bot):
    cancel_user_jobs(callback.from_user.id if callback.from_user else 0)
    uid_cq = callback.from_user.id if callback.from_user else 0
    await callback.message.edit_text(tr("MSG_QUEUE_CANCELED_EDIT", uid_cq))
    await callback.answer(tr("MSG_QUEUE_CANCELED_ANSWER", uid_cq))


@router.callback_query(F.data == "add_image")
async def on_add_image(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    await callback.message.reply(tr("MSG_SEND_IMAGE_NOW", uid))
    pending_images[callback.from_user.id] = {"waiting_for_image": True}
    await callback.answer()


@router.message(F.photo)
async def on_photo_for_audio(message: Message, bot: Bot):
    global developer_menu_image_file_id
    uid = message.from_user.id if message.from_user else 0
    if uid == config.DEVELOPER_ID and uid in awaiting_menu_image:
        awaiting_menu_image.discard(uid)
        developer_menu_image_file_id = message.photo[-1].file_id
        await message.reply(texts_module.MSG_DEV_MENU_IMAGE_SAVED)
        return

    # صورة أثناء معالج التخصيص (wizard): تُستخدم كصورة غلاف جديدة ثم ننتقل لخطوة تحديد الجزء
    if uid in wizard_state:
        pending_entry = _get_pending_audio_or_none(uid)
        if not pending_entry:
            await message.reply(tr("MSG_AUDIO_EXPIRED", uid))
            return
        photo = message.photo[-1]
        pending_entry["thumbnail_file_id"] = photo.file_id
        await reply_with_premium_emoji(message, tr("MSG_IMAGE_RECEIVED", uid))
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
            await message.reply(tr("MSG_AUDIO_EXPIRED", uid))
            return

        pending_audio.pop(uid, None)
        pending_images.pop(uid, None)

        job = dict(pending_entry)
        job["thumbnail_file_id"] = photo.file_id
        job["uid"] = uid
        job["segment_start"] = 0.0

        await reply_with_premium_emoji(message, tr("MSG_IMAGE_RECEIVED", uid))
        await _launch_job(bot, uid, job)
        return

    if pending.get("waiting_for_image"):
        photo = message.photo[-1]
        pending_entry = pending_audio.get(message.from_user.id)
        if not pending_entry:
            await message.reply(tr("MSG_NO_PENDING_AUDIO", uid))
            return

        if time.time() > pending_entry["expires_at"]:
            pending_audio.pop(message.from_user.id, None)
            pending_images.pop(message.from_user.id, None)
            await message.reply(tr("MSG_AUDIO_EXPIRED", uid))
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
        await reply_with_premium_emoji(message, tr("MSG_IMAGE_RECEIVED", uid))
        enqueue_job(job)
        return


@router.callback_query(F.data.startswith("vinyl:"))
async def on_vinyl_choice(callback, bot: Bot):
    choice = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    if choice in ("pink", "blue", "yellow", "red", "green","bloody"):
        developer_vinyl_choice[user_id] = choice
    else:
        developer_vinyl_choice.pop(user_id, None)
    await callback.message.edit_reply_markup(reply_markup=build_vinyl_color_keyboard(user_id))
    await callback.answer(tr("MSG_VINYL_CHOICE_SAVED_ANSWER", user_id))


@router.callback_query(F.data.startswith("speed:"))
async def on_speed_selected(callback, bot: Bot):
    data = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    if data == "full":
        user_rotation_seconds[user_id] = 0.0
    else:
        user_rotation_seconds[user_id] = 60 / float(data)
    await callback.message.edit_reply_markup(reply_markup=build_speed_keyboard(user_id))
    await callback.answer(tr("MSG_SPEED_SAVED_ANSWER", user_id))


@router.message(F.video | F.voice | F.document)
async def on_wrong_type(message: Message):
    uid = message.from_user.id if message.from_user else 0
    await message.reply(tr("MSG_WRONG_TYPE", uid))


@router.callback_query(F.data == "buy_stars")
async def on_buy_stars(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=texts_module.MSG_INVOICE_TITLE,
        description=texts_module.MSG_INVOICE_DESCRIPTION_FMT.format(limit=config.PREMIUM_DAILY_LIMIT),
        payload=f"{texts_module.MSG_INVOICE_PAYLOAD_PREFIX}_{uid}_{int(time.time())}",
        provider_token="",  # فارغ إجباريًا لمدفوعات نجوم تليكرام (XTR)
        currency="XTR",
        prices=[LabeledPrice(label=texts_module.MSG_INVOICE_LABEL, amount=config.STARS_SUBSCRIPTION_PRICE)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0
    limits.activate_subscription(uid, config.STARS_SUBSCRIPTION_DAYS)
    logger.info(texts_module.LOG_PAYMENT_RECORDED, uid)
    await reply_with_premium_emoji(message, tr("MSG_PAYMENT_SUCCESS_FMT", uid).format(limit=config.PREMIUM_DAILY_LIMIT))

    if config.DEVELOPER_ID:
        user = message.from_user
        try:
            await bot.send_message(
                config.DEVELOPER_ID,
                texts_module.MSG_NEW_SUBSCRIBER_ADMIN_FMT.format(
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
