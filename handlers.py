import asyncio
import html
import logging
import os
import time
import uuid
from aiogram import Router, F, Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MessageEntity,
    InputRichMessage,
)

from compose import build_disc
from processor import get_duration, render_vinyl, render_preview
import config
import limits
import texts as texts_module
import math
from services.contexts import channel_key as _channel_key
from services.contexts import group_key as _group_key
from services.contexts import is_channel_context as _is_channel_context
from services.contexts import is_group_context as _is_group_context
from services.contexts import is_shared_context as _is_shared_context
from services.contexts import split_context_suffix as _split_channel_suffix
from services.contexts import with_context_suffix as _with_channel_suffix
from services.localization import get_user_lang, tr
from services.messaging import (
    edit_text_variable,
    format_rich_value as _format_rich_value,
    get_text_rich_content,
    get_text_value,
    normalize_rich_blocks_for_input as _normalize_rich_blocks_for_input,
    reply_text_variable,
    sanitize_text as sanitize_and_convert_text,
    send_rich_message,
    send_text_variable,
)
from services.premium_emoji import (
    build_premium_entities_from_text,
    clean_premium_emoji_tags,
    extract_premium_emojis,
)
from rich_content import escape_rich_html
from routers.language import create_language_router
from routers.payments import create_payment_router
from routers.start import create_start_router
from routers.developer import awaiting_menu_image
from routers.developer import router as developer_router
from routers.developer_texts import router as developer_text_router
from vinyl_catalog import VINYL_STYLES, get_vinyl_style

logger = logging.getLogger(__name__)
router = Router()


async def send_ephemeral_text(
    bot: Bot,
    chat_id: int,
    user_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    entities: list[MessageEntity] | None = None,
    callback_query_id: str | None = None,
) -> Message:
    """إرسال رسالة مؤقتة للمستخدم داخل مجموعة/سوبرغروب."""
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        receiver_user_id=user_id,
        callback_query_id=callback_query_id,
        reply_markup=reply_markup,
        entities=entities,
    )


async def edit_ephemeral_text(
    bot: Bot,
    chat_id: int,
    user_id: int,
    ephemeral_message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    entities: list[MessageEntity] | None = None,
) -> bool:
    """تعديل نفس الرسالة المؤقتة بدل إرسال رسالة جديدة."""
    return await bot.edit_ephemeral_message_text(
        chat_id=chat_id,
        receiver_user_id=user_id,
        ephemeral_message_id=ephemeral_message_id,
        text=text,
        reply_markup=reply_markup,
        entities=entities,
    )


async def delete_ephemeral_text(
    bot: Bot, chat_id: int, user_id: int, ephemeral_message_id: int
) -> bool:
    return await bot.delete_ephemeral_message(
        chat_id=chat_id,
        receiver_user_id=user_id,
        ephemeral_message_id=ephemeral_message_id,
    )


def _ephemeral_id(pending: dict | None) -> int | None:
    if not pending:
        return None
    value = pending.get("ephemeral_message_id")
    return int(value) if value is not None else None


def _group_pending_key_for_user(chat_id: int, user_id: int) -> str | None:
    """أحدث طلب صوت نشط لهذا المستخدم داخل المجموعة."""
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


async def _edit_wizard_text(
    bot: Bot,
    uid,
    target_message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    entities: list[MessageEntity] | None = None,
) -> Message | None:
    """يعدّل نفس رسالة الـWizard؛ بالمجموعة تكون Ephemeral."""
    if _is_group_context(uid):
        pending = pending_audio.get(uid)
        eid = _ephemeral_id(pending)
        if eid is None:
            return None
        original = pending.get("message")
        owner_id = pending.get("owner_user_id") or (
            original.from_user.id if original and original.from_user else 0
        )
        await edit_ephemeral_text(
            bot,
            target_message.chat.id,
            owner_id,
            eid,
            text,
            reply_markup=reply_markup,
            entities=entities,
        )
        return target_message

    return await target_message.edit_text(
        text,
        reply_markup=reply_markup,
        entities=entities,
    )


async def edit_wizard_text_variable(
    bot: Bot,
    uid,
    target_message: Message,
    var_name: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    **format_kwargs,
):
    rich = get_text_rich_content(var_name, uid)
    if rich and not _is_group_context(uid):
        blocks = _format_rich_value(rich.get("blocks"), **format_kwargs)
        html_content = _format_rich_value(rich.get("html"), **format_kwargs)
        if blocks or html_content:
            return await target_message.edit_text(
                rich_message=InputRichMessage(
                    blocks=_normalize_rich_blocks_for_input(blocks),
                    html=html_content,
                    is_rtl=rich.get("is_rtl"),
                ),
                reply_markup=reply_markup,
            )

    text = get_text_value(var_name, uid)
    if format_kwargs:
        text = text.format(**format_kwargs)
    return await _edit_wizard_text(
        bot,
        uid,
        target_message,
        text,
        reply_markup=reply_markup,
    )


job_queue: asyncio.Queue[dict] = asyncio.Queue()
developer_job_queue: asyncio.Queue[dict] = asyncio.Queue()
worker_tasks: list[asyncio.Task] = []
queue_order: list[str] = []
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
STATUS_UPDATE_INTERVAL_SECONDS = 2.2
JOB_TIMEOUT_SECONDS = 8 * 60
JOB_TIMEOUT_MAX_SECONDS = 30 * 60
JOB_TIMEOUT_SECONDS_PER_MB = 3.0


def compute_job_timeout_seconds(audio_file_size_bytes: int | None) -> float:
    """يحسب مهلة زمنية معقولة لمعالجة Job واحد بناءً على حجم الملف الصوتي."""
    if not audio_file_size_bytes or audio_file_size_bytes <= 0:
        return JOB_TIMEOUT_SECONDS
    size_mb = audio_file_size_bytes / (1024 * 1024)
    dynamic = JOB_TIMEOUT_SECONDS + size_mb * JOB_TIMEOUT_SECONDS_PER_MB
    return min(max(dynamic, JOB_TIMEOUT_SECONDS), JOB_TIMEOUT_MAX_SECONDS)


async def _is_channel_controller(bot: Bot, chat_id: int, user_id: int) -> bool:
    """يتحقق إن المستخدم أدمن أو مالك بالقناة (chat_id)."""
    if not user_id:
        return False
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def resolve_callback_uid(callback, bot: Bot) -> tuple[str, int | None, int | None] | None:
    """
    يحلل callback.data ويرجع (base_data, uid, channel_chat_id) حيث uid ممكن يكون
    int (زر بالخاص) أو str مركّب (زر بسياق قناة/مجموعة). يرجع None ويرد على
    callback برسالة رفض تلقائيًا لو الضاغط ما يملك صلاحية التحكم.

    - قناة: أدمن/مالك القناة فقط.
    - مجموعة: صاحب الصوت الأصلي (اللي أرسله) أو أي أدمن بالمجموعة.
    """
    base, ch_chat, ch_msg = _split_channel_suffix(callback.data)
    if ch_chat is not None:
        presser_id = callback.from_user.id if callback.from_user else 0
        chat_type = callback.message.chat.type if callback.message else None

        if chat_type in ("group", "supergroup"):
            key = _group_key(ch_chat, ch_msg)
            pending = pending_audio.get(key)
            original_sender_id = None
            if pending:
                original_message = pending.get("message")
                if original_message is not None and original_message.from_user:
                    original_sender_id = original_message.from_user.id
            is_owner = original_sender_id is not None and presser_id == original_sender_id
            if not is_owner and not await _is_channel_controller(bot, ch_chat, presser_id):
                await callback.answer(texts_module.MSG_CHANNEL_ADMIN_ONLY, show_alert=True)
                return None
            return base, key, ch_chat

        if not await _is_channel_controller(bot, ch_chat, presser_id):
            await callback.answer(texts_module.MSG_CHANNEL_ADMIN_ONLY, show_alert=True)
            return None
        return base, _channel_key(ch_chat, ch_msg), ch_chat
    return base, (callback.from_user.id if callback.from_user else 0), None


async def notify_missing_channel_permission(
    bot: Bot, chat_id: int, chat_title: str, reason: str
) -> None:
    """
    لو البوت ينقصه صلاحية بالقناة (نشر/حذف رسائل)، نحاول نبلّغ مالك القناة أو
    أي أدمن (بالخاص) بالترتيب: المالك أولاً، وإلا أول أدمن نقدر نوصله. لو فشلت
    كل المحاولات (مثلاً محد منهم بدأ محادثة خاصة مع البوت من قبل، وتليكرام
    يمنع البوت من ابتداء محادثة)، نحاول كحل أخير نطبع تحذير داخل القناة نفسها.
    """
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

    admins_sorted = sorted(admins, key=lambda m: 0 if m.status == "creator" else 1)
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


channel_reply_index: dict[tuple[int, int], str] = {}

CHANNEL_RESULT_URL = "http://t.me/discbybot?start=help"
CHANNEL_RESULT_EMOJI = "💌"

VINYL_TEMPLATE_PREVIEW_URL = "https://t.me/VinylTemplate"
PREVIEW_EMOJI_ID = "5904219717073114606"


PREMIUM_EMOJI_IDS = {
    "emerald": "5285265490350972397",
    "koi": "5339487433828353468",
    "kiss": "5474525960143385880",
    "ali": "5460737770798489825",
    "black": "5399878127163811970",
}


async def reply_with_premium_emoji(message: Message, text: str, **kwargs) -> Message:
    """
    أرسل رسالة مع دعم كامل للإيموجي البريميوم والـ HTML.

    يتولى تلقائياً:
    - استخراج أكواد الإيموجي البريميوم
    - تحويل HTML غير المدعوم
    - بناء entities صحيحة
    """
    text = sanitize_and_convert_text(text)

    emojis_dict = extract_premium_emojis(text)

    if emojis_dict:
        clean_text = clean_premium_emoji_tags(text)

        entities = build_premium_entities_from_text(text)

        try:
            if entities:
                return await message.reply(clean_text, entities=entities, **kwargs)
            return await message.reply(clean_text, **kwargs)
        except TelegramBadRequest as e:
            logger.warning(f"فشل إرسال رسالة مع إيموجي بريميوم: {e}, سيتم الإرسال بدونها")
            return await message.reply(clean_text, **kwargs)

    try:
        return await message.reply(text, **kwargs)
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            logger.warning("فشل تفسير HTML، سيُرسل كنص خام: %s", e)
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "entities"}
            return await message.reply(html.escape(text), **clean_kwargs)
        raise


STATUS_EMOJI_ID = "5463010113440717314"
STATUS_EMOJI_CHAR = "👀"

HEADER_EMOJI_ID = "5431578344472746087"
HEADER_EMOJI_CHAR = "🤩"
RICH_STATUS_HEADER_TEXT = "جاري المعالجة"


def _format_eta_seconds(seconds: float) -> str:
    """يحوّل عدد الثواني لنص عربي مختصر ومقروء (مثلاً: '١ دقيقة و١٠ث' → نكتبها إنجليزي أرقام لسهولة)."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}ث"
    minutes, secs = divmod(seconds, 60)
    if secs == 0:
        return f"{minutes}د"
    return f"{minutes}د {secs}ث"


def render_rich_status_html(
    percent: float | None,
    intro_text: str,
    stage_icons: list[str] | None = None,
    eta_seconds: float | None = None,
) -> str:
    """
    يبني HTML الرسالة الغنية لعرض حالة المعالجة:
    - سطر مقدّمة
    - جدول فيه صف عنوان: نص ثابت (RICH_STATUS_HEADER_TEXT) + إيموجي بريميوم ثابت،
      لا يتغيّر مهما تغيّرت المرحلة
    - صف فيه سلسلة من نفس الإيموجي البريميوم: إيموجي جديد ينضاف لكل مرحلة،
      وكل الإيموجيات (شاملة الحالي) تظهر مظلَّلة باستمرار، والنسبة المئوية تبدأ
      من 0% عند ظهور أول إيموجي مضلل وتستمر بالارتفاع تزامنًا مع تقدّم العملية
      وإضافة كل إيموجي جديد، لحين الاكتمال
    - سطر أخير اختياري يعرض تقدير الوقت المتبقي (يُحسب خارجيًا بناءً على معدّل
      التقدّم الفعلي، ويظهر فقط لو عندنا نسبة مئوية أكبر من 0% وأقل من 100%)
    """
    header_emoji_html = f'<tg-emoji emoji-id="{HEADER_EMOJI_ID}">{HEADER_EMOJI_CHAR}</tg-emoji>'
    header = f"{header_emoji_html} {escape_rich_html(RICH_STATUS_HEADER_TEXT)}"

    stage_icons = stage_icons or [STATUS_EMOJI_CHAR]
    emoji_html = f'<tg-emoji emoji-id="{STATUS_EMOJI_ID}">{STATUS_EMOJI_CHAR}</tg-emoji>'

    percent = 0.0 if percent is None else max(0.0, min(100.0, percent))

    row_parts = []
    for _ in stage_icons[:-1]:
        row_parts.append(f"<mark>{emoji_html}</mark>")

    row_parts.append(f"<mark>{emoji_html}</mark> {int(percent)}%")

    icons_row = " ".join(row_parts)

    eta_row = ""
    if eta_seconds is not None and 0 < percent < 100:
        eta_row = f'<tr><td align="left" valign="middle">⏳ {escape_rich_html(_format_eta_seconds(eta_seconds))}</td></tr>'

    return (
        f"<p>{escape_rich_html(intro_text)}</p>"
        f'<table bordered striped><tr><th align="center" valign="middle">{header}</th></tr>'
        f'<tr><td align="left" valign="middle">{icons_row}</td></tr>'
        f"{eta_row}</table>"
    )


class EphemeralStatusAnimator:
    """يحدّث نفس رسالة الـEphemeral التي بدأ بها الـWizard."""

    def __init__(self, bot: Bot, chat_id: int, user_id: int, ephemeral_message_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
        self.ephemeral_message_id = ephemeral_message_id
        self.stage_text = texts_module.STAGE_PREPARING
        self.percent: float = 0.0
        self._last_rendered: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def set_stage(self, stage_text: str, percent: float | None = None) -> None:
        self.stage_text = stage_text
        if percent is not None:
            self.percent = percent

    async def _push_update(self) -> None:
        text = self.stage_text + (f" {int(self.percent)}%" if self.percent is not None else "…")
        if text == self._last_rendered:
            return
        try:
            await edit_ephemeral_text(
                self.bot,
                self.chat_id,
                self.user_id,
                int(self.ephemeral_message_id),
                text,
            )
            self._last_rendered = text
        except TelegramBadRequest:
            pass
        except Exception:
            logger.exception(texts_module.LOG_PROGRESS_UPDATE_FAILED)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._push_update()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=STATUS_UPDATE_INTERVAL_SECONDS
                )
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


class StatusAnimator:
    """يحدّث رسالة الحالة الغنية (Rich Message) بشكل دوري: إيموجي متسلسل لكل مرحلة + شريط تظليل."""

    def __init__(self, message: Message, bot: Bot, user_id: int = 0):
        self.message = message
        self.bot = bot
        self.user_id = user_id
        self.stage_text = texts_module.STAGE_PREPARING
        self.percent: float = 0.0
        self.stage_icons: list[str] = [STATUS_EMOJI_CHAR]
        self._last_stage_text: str | None = texts_module.STAGE_PREPARING
        self._last_rendered: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._rich_supported = True
        self._progress_start_time: float | None = None
        self.eta_seconds: float | None = None

    def set_stage(self, stage_text: str, percent: float | None = None) -> None:
        if stage_text != self._last_stage_text:
            self.stage_icons.append(STATUS_EMOJI_CHAR)
            self._last_stage_text = stage_text
        self.stage_text = stage_text
        if percent is not None:
            if percent > 0 and self._progress_start_time is None:
                self._progress_start_time = time.time()
            self.percent = percent
            if self._progress_start_time is not None and 0 < percent < 100:
                elapsed = time.time() - self._progress_start_time
                estimated_total = elapsed / (percent / 100)
                self.eta_seconds = max(0.0, estimated_total - elapsed)
            elif percent >= 100:
                self.eta_seconds = 0.0

    def _render_html(self) -> str:
        intro = tr("MSG_RICH_STATUS_INTRO", self.user_id)
        return render_rich_status_html(
            self.percent, intro, self.stage_icons, eta_seconds=self.eta_seconds
        )

    async def _push_update(self) -> None:
        html_content = self._render_html()
        if html_content == self._last_rendered:
            return

        if self._rich_supported:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.message.chat.id,
                    message_id=self.message.message_id,
                    rich_message=InputRichMessage(html=html_content),
                )
                self._last_rendered = html_content
                return
            except (AttributeError, TypeError):
                logger.warning(
                    "rich_message غير مدعوم بهالنسخة من aiogram (edit_message_text)، الرجوع لتحديث نصي عادي"
                )
                self._rich_supported = False
            except TelegramBadRequest:
                return
            except Exception:
                logger.exception("فشل تحديث رسالة الحالة الغنية")
                return

        plain = self.stage_text + (f" {int(self.percent)}%" if self.percent is not None else "…")
        try:
            await self.message.edit_text(plain)
            self._last_rendered = html_content
        except TelegramBadRequest:
            pass
        except Exception:
            logger.exception(texts_module.LOG_PROGRESS_UPDATE_FAILED)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._push_update()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=STATUS_UPDATE_INTERVAL_SECONDS
                )
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


DOWNLOAD_BACKOFF_BASE_SECONDS = 1.5
DOWNLOAD_BACKOFF_MAX_SECONDS = 20.0


async def download_with_retries(
    bot: Bot, file_id: str, destination: str, timeout_seconds: int, retries: int = 3
) -> None:
    """
    ينزّل ملف من تليكرام مع إعادة محاولة بـ exponential backoff (بدل انتظار
    ثابت 2 ثانية) عشان ما نضغط أكثر على شبكة/سيرفر أصلًا متعثّر مؤقتًا، وحتى
    نمنح فرصة أكبر للتعافي بمشاكل الشبكة المتقطعة قبل فشل الطلب بالكامل.
    """
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
    """
    يرجّع "دور" الطلب بالطابور المرئي:
    - 0  → الطلب مو بالطابور (يعالَج الآن فعليًا، أو خلص، أو غير موجود أصلاً)
    - 1  → التالي مباشرة (يبدأ فور ما يفرغ أي worker)
    - N  → فيه N-1 طلب قبله
    """
    try:
        return queue_order.index(job_id) + 1
    except ValueError:
        return 0


def _queue_position_text(uid, job_id: str) -> str | None:
    """نص جاهز للعرض يوضّح دور المستخدم بالطابور، أو None لو صار دوره فورًا."""
    display_uid = uid if isinstance(uid, int) else 0
    pos = get_queue_position(job_id)
    if pos <= 0:
        return None
    if pos == 1:
        return tr("MSG_QUEUE_POSITION_NEXT", display_uid)
    return tr("MSG_QUEUE_POSITION_FMT", display_uid).format(position=pos)


async def notify_queue_position(bot: Bot, chat_id: int, uid, job_id: str) -> None:
    """
    يرسل رسالة قصيرة توضح ترتيب الطلب بالطابور. مقتصر على المحادثات الخاصة
    فقط (بدون قنوات/مجموعات) تفاديًا لتعقيد الرسائل المؤقتة (Ephemeral) هناك.
    """
    if _is_shared_context(uid):
        return
    text = _queue_position_text(uid, job_id)
    if text is None:
        return
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("فشل إرسال رسالة موقع الطابور")


CLEANUP_INTERVAL_SECONDS = 10 * 60
cleanup_task: asyncio.Task | None = None


def _cleanup_expired_pending_audio() -> int:
    now = time.time()
    removed = 0
    for key in list(pending_audio.keys()):
        entry = pending_audio.get(key)
        if entry is None or now > entry.get("expires_at", 0):
            pending_audio.pop(key, None)
            wizard_state.pop(key, None)
            if isinstance(key, int):
                pending_images.pop(key, None)
            removed += 1
    return removed


def _cleanup_orphaned_wizard_state() -> int:
    """أي wizard_state ما له entry مقابل بـ pending_audio يُعتبر يتيمًا (orphan)."""
    removed = 0
    for key in list(wizard_state.keys()):
        if key not in pending_audio:
            wizard_state.pop(key, None)
            removed += 1
    return removed


def _cleanup_expired_pending_confirm() -> int:
    now = time.time()
    removed = 0
    for uid, job in list(pending_confirm.items()):
        if now > job.get("confirm_expires_at", 0):
            pending_confirm.pop(uid, None)
            removed += 1
    return removed


def _cleanup_orphaned_channel_reply_index() -> int:
    """أي مفتاح بـ channel_reply_index يشاور على سياق قناة/مجموعة ما موجود
    فعليًا بـ pending_audio (يعني خلص أو انتهت صلاحيته) يصير غير مفيد."""
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
            n1 = _cleanup_expired_pending_audio()
            n2 = _cleanup_orphaned_wizard_state()
            n3 = _cleanup_expired_pending_confirm()
            n4 = _cleanup_orphaned_channel_reply_index()
            total = n1 + n2 + n3 + n4
            if total:
                logger.info(
                    "🧹 تنظيف دوري للحالة المؤقتة: pending_audio=%s wizard_state=%s "
                    "pending_confirm=%s channel_reply_index=%s (مجموع=%s)",
                    n1,
                    n2,
                    n3,
                    n4,
                    total,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("فشل التنظيف الدوري للحالة المؤقتة")


def start_cleanup_task() -> None:
    """يشغّل مهمة التنظيف الدوري مرة واحدة فقط (idempotent)."""
    global cleanup_task
    if cleanup_task is None or cleanup_task.done():
        cleanup_task = asyncio.create_task(_periodic_cleanup_loop())


async def start_job_worker(bot: Bot) -> None:
    """
    يشغّل عدة workers بالتوازي (بعدد config.MAX_CONCURRENT_JOBS) بدل واحد
    فقط، عشان نستفيد فعليًا من هذا المتغيّر بدل ما يبقى معرّف بدون استخدام.
    """
    global worker_tasks
    worker_tasks = [t for t in worker_tasks if not t.done()]
    needed = max(1, config.MAX_CONCURRENT_JOBS) - len(worker_tasks)
    for _ in range(needed):
        worker_tasks.append(asyncio.create_task(_job_worker_loop(bot)))


async def _get_next_job() -> tuple[dict, asyncio.Queue]:
    """
    يرجّع أول Job جاهز مع الطابور اللي جاء منه (بأولوية دائمة لطابور المطور).
    ينتظر بشكل حدثي (event-driven عبر asyncio.wait) بدل الـ polling المتكرر
    (busy-wait بـ asyncio.sleep(0.1)) لما تكون كل الطوابير فاضية — هذا يلغي
    استهلاك دورة CPU كل 100ms طوال فترات الخمول الطويلة بين الطلبات.
    """
    while True:
        if not developer_job_queue.empty():
            return developer_job_queue.get_nowait(), developer_job_queue
        if not job_queue.empty():
            return job_queue.get_nowait(), job_queue

        dev_task = asyncio.create_task(developer_job_queue.get())
        normal_task = asyncio.create_task(job_queue.get())
        try:
            done, pending = await asyncio.wait(
                {dev_task, normal_task}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for t in pending:
                t.cancel()
            for t in pending:
                try:
                    await t
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
            job_timeout = compute_job_timeout_seconds(getattr(job.get("audio"), "file_size", None))
            try:
                await asyncio.wait_for(process_job(bot, job), timeout=job_timeout)
            except asyncio.TimeoutError:
                logger.warning(texts_module.LOG_JOB_TIMEOUT)
        except Exception:
            logger.exception(texts_module.LOG_QUEUE_PROCESS_FAILED)
        finally:
            _release_job_usage(job)
            tracked_jobs.pop(job_id, None)
            user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
            if queue is not None:
                queue.task_done()


def get_user_rotation_seconds(user_id: int) -> float | None:
    return user_rotation_seconds.get(user_id, config.ROTATION_SECONDS)


def get_developer_vinyl_path(user_id: int, choice_override: str | None = None) -> str:
    choice = choice_override if choice_override is not None else developer_vinyl_choice.get(user_id)
    return get_vinyl_style(choice).vinyl_path


def get_developer_shadow_path(user_id: int, choice_override: str | None = None) -> str:
    choice = choice_override if choice_override is not None else developer_vinyl_choice.get(user_id)
    return get_vinyl_style(choice).shadow_path


def get_developer_hole_ratio(vinyl_choice: str | None) -> float:
    return get_vinyl_style(vinyl_choice).hole_ratio_override or config.HOLE_RATIO


VINYL_COLOR_CHOICES: list[tuple[str, str]] = [(style.key, style.text_key) for style in VINYL_STYLES]

VALID_VINYL_COLOR_VALUES: frozenset[str] = frozenset(value for value, _ in VINYL_COLOR_CHOICES)


def user_has_premium_access(user_id: int) -> bool:
    """
    يرجّع True لو المستخدم يقدر يستخدم الألوان المدفوعة: مشترك فعليًا
    (limits.is_premium)، أو بالقائمة البيضاء، أو هو المطور نفسه.
    """
    if user_id and user_id == config.DEVELOPER_ID:
        return True
    if limits.is_whitelisted(user_id):
        return True
    return limits.is_premium(user_id)


def get_job_priority(user_id: int) -> int:
    return 0 if user_id and user_id == config.DEVELOPER_ID else 1


def build_buy_stars_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_BUY_STARS", user_id).format(price=config.STARS_SUBSCRIPTION_PRICE),
                    callback_data="buy_stars",
                )
            ],
        ]
    )


def enqueue_job(job: dict) -> None:
    uid = job.get("uid", 0)
    queue_order.append(job["job_id"])
    if get_job_priority(uid) == 0:
        developer_job_queue.put_nowait(job)
    else:
        job_queue.put_nowait(job)


def _release_job_usage(job: dict) -> None:
    reserved_uid = job.pop("usage_reserved_for", None)
    if isinstance(reserved_uid, int):
        limits.release_reserved_usage(reserved_uid)


def cancel_user_jobs(user_id: int) -> None:
    pending_ids = user_pending_jobs.pop(user_id, set())
    for job_id in list(pending_ids):
        canceled_job_ids.add(job_id)
        job = tracked_jobs.pop(job_id, None)
        if job:
            _release_job_usage(job)
            cleanup(*job.get("temp_paths", []))
        if job_id in queue_order:
            queue_order.remove(job_id)


async def process_job(bot: Bot, job: dict) -> None:
    message = job["message"]
    audio = job["audio"]
    uid = job["uid"]
    context_key = job.get("context_key", uid)
    job_id = job["job_id"]

    audio_path = tmp(
        f"{uid}_{job_id}_audio.{audio.file_name.split('.')[-1] if audio.file_name else 'mp3'}"
    )
    thumb_path = tmp(f"{uid}_{job_id}_thumb.jpg")
    disc_path = tmp(f"{uid}_{job_id}_disc.png")
    out_path = tmp(f"{uid}_{job_id}_out.mp4")
    job["temp_paths"] = [audio_path, thumb_path, disc_path, out_path]

    if _is_group_context(context_key):
        ephemeral_id = job.get("status_ephemeral_message_id")
        if ephemeral_id is None:
            status = await send_ephemeral_text(
                bot,
                message.chat.id,
                uid,
                tr("STAGE_PREPARING", uid),
            )
            ephemeral_id = status.ephemeral_message_id
            job["status_ephemeral_message_id"] = ephemeral_id
        animator = EphemeralStatusAnimator(bot, message.chat.id, uid, int(ephemeral_id))
    else:
        initial_html = render_rich_status_html(0.0, tr("MSG_RICH_STATUS_INTRO", uid))
        status = await send_rich_message(
            bot, message.chat.id, initial_html, reply_to_message_id=message.message_id
        )
        animator = StatusAnimator(status, bot, uid)
    animator.start()

    duration_warning_msg: Message | None = None

    try:
        await bot.send_chat_action(message.chat.id, action=ChatAction.RECORD_VIDEO_NOTE)
        animator.set_stage(tr("STAGE_DOWNLOADING_AUDIO", uid))
        await download_with_retries(bot, audio.file_id, audio_path, timeout_seconds=300, retries=3)

        thumbnail_file_id = None
        if job.get("thumbnail_file_id"):
            thumbnail_file_id = job["thumbnail_file_id"]
        elif getattr(audio, "thumbnail", None) is not None:
            thumbnail_file_id = audio.thumbnail.file_id

        if thumbnail_file_id:
            animator.set_stage(tr("STAGE_DOWNLOADING_THUMBNAIL", uid))
            await download_with_retries(
                bot, thumbnail_file_id, thumb_path, timeout_seconds=60, retries=2
            )
        else:
            raise ValueError(texts_module.ERR_NO_THUMBNAIL_AVAILABLE)

        duration = await get_duration(audio_path)
        if duration > config.MAX_DURATION_SECONDS and not job.get("segment_start"):
            if _is_group_context(context_key):
                animator.set_stage(tr("MSG_DURATION_TOO_LONG_FMT", uid).format(duration=duration))
            else:
                duration_warning_msg = await reply_with_premium_emoji(
                    message, tr("MSG_DURATION_TOO_LONG_FMT", uid).format(duration=duration)
                )

        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        animator.set_stage(tr("STAGE_BUILDING_DISC", uid))
        vinyl_choice = job.get("vinyl_choice")

        await asyncio.to_thread(
            build_disc,
            thumb_path,
            get_developer_vinyl_path(uid, vinyl_choice),
            disc_path,
            get_developer_hole_ratio(vinyl_choice),
            config.DISC_SIZE,
        )
        render_shadow_path = get_developer_shadow_path(uid, vinyl_choice)

        animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=0)

        async def on_render_progress(percent: float) -> None:
            animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=percent)

        await render_vinyl(
            disc_path,
            render_shadow_path,
            audio_path,
            out_path,
            rotation_seconds=job.get("rotation_seconds", get_user_rotation_seconds(uid)),
            size=config.DISC_SIZE,
            fps=config.OUTPUT_FPS,
            max_duration=config.MAX_DURATION_SECONDS,
            start_offset=job.get("segment_start", 0.0),
            on_progress=on_render_progress,
        )
        if not os.path.exists(out_path):
            raise FileNotFoundError(texts_module.ERR_OUTPUT_NOT_CREATED)

        animator.set_stage(tr("STAGE_UPLOADING_VIDEO", uid), percent=100)
        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)

        final_keyboard = None
        if _is_shared_context(context_key):
            final_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{CHANNEL_RESULT_EMOJI} كيف اسوي وحدة مثل هذي؟",
                            url=CHANNEL_RESULT_URL,
                            style="danger",
                        )
                    ]
                ]
            )

        try:
            await message.reply_video_note(
                FSInputFile(out_path), length=config.DISC_SIZE, reply_markup=final_keyboard
            )
        except TelegramBadRequest as e:
            if _is_shared_context(context_key) and (
                "rights" in str(e).lower() or "administrator" in str(e).lower()
            ):
                place_label = "القناة" if _is_channel_context(context_key) else "المجموعة"
                await notify_missing_channel_permission(
                    bot,
                    message.chat.id,
                    message.chat.title or place_label,
                    f"نشر فيديو/رسائل بـ{place_label} (صلاحية Post Messages).",
                )
                return
            raise

        reserved_uid = job.pop("usage_reserved_for", None)
        if isinstance(reserved_uid, int):
            limits.commit_reserved_usage(reserved_uid)

        if _is_shared_context(context_key):
            for msg_id in job.get("channel_msg_ids", []):
                try:
                    await bot.delete_message(message.chat.id, msg_id)
                except Exception:
                    pass
            ch_chat, _ch_msg = _channel_ctx(context_key)
            if ch_chat is not None:
                for reply_key, mapped in list(channel_reply_index.items()):
                    if mapped == uid:
                        channel_reply_index.pop(reply_key, None)
    except asyncio.CancelledError:
        logger.warning(texts_module.LOG_JOB_TIMEOUT)
        try:
            actual_timeout_minutes = (
                compute_job_timeout_seconds(getattr(audio, "file_size", None)) / 60
            )
            timeout_text = tr("MSG_PROCESSING_TIMEOUT_FMT", uid).format(
                minutes=actual_timeout_minutes
            )
            if _is_group_context(context_key):
                animator.set_stage(timeout_text)
            else:
                await reply_with_premium_emoji(message, timeout_text)
        except Exception:
            logger.exception(texts_module.LOG_SEND_ERROR_FAILED)
        raise
    except Exception:
        logger.exception(texts_module.LOG_PROCESS_JOB_FAILED)
        error_text = tr("MSG_PROCESSING_FAILED_SAFE", uid)
        try:
            if _is_group_context(context_key):
                animator.set_stage(
                    tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text=error_text)
                )
            else:
                await reply_text_variable(
                    message, bot, "MSG_PROCESSING_ERROR_FMT", uid, error_text=error_text
                )
        except Exception:
            logger.exception(texts_module.LOG_SEND_ERROR_FAILED)
    finally:
        _release_job_usage(job)
        await animator.stop()
        cleanup(audio_path, thumb_path, disc_path, out_path)
        try:
            if _is_group_context(context_key):
                eid = job.get("status_ephemeral_message_id")
                if eid is not None:
                    await delete_ephemeral_text(bot, message.chat.id, uid, int(eid))
            else:
                await status.delete()
        except Exception:
            pass
        if duration_warning_msg is not None:
            try:
                await duration_warning_msg.delete()
            except Exception:
                pass


def build_customize_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """قائمة التخصيص التي تُفتح من زر (تخصيص) في رسالة الترحيب."""
    current = get_user_rotation_seconds(user_id)
    labels = [
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_19RPM", user_id), "19"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = []
    for label, value in labels:
        selected = current in (None, 0) if value == "full" else current == (60 / float(value))
        mark = " ✅" if selected else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{label}{mark}",
                callback_data=f"speed:{value}",
                style="primary",
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:2],
            buttons[2:4],
            buttons[4:6],
            [
                InlineKeyboardButton(
                    text=tr("BTN_VINYL_COLOR_MENU", user_id),
                    callback_data="vinyl_menu:open",
                    style="danger",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_BACK", user_id),
                    callback_data="customize:back",
                    style="primary",
                )
            ],
        ]
    )


def build_start_keyboard(user_id: int, bot_username: str) -> InlineKeyboardMarkup:
    """لوحة الترحيب: إضافة البوت، اللغة، والتخصيص."""
    add_url = f"https://t.me/{bot_username}?startgroup=start"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ أضفني للمجموعة",
                    url=add_url,
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_LANG,
                    callback_data="lang:toggle",
                    style="success",
                ),
                InlineKeyboardButton(
                    text=tr("BTN_CUSTOMIZE", user_id),
                    callback_data="customize:open",
                    style="danger",
                ),
            ],
        ]
    )


def build_vinyl_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    current = developer_vinyl_choice.get(user_id)
    has_premium = user_has_premium_access(user_id)

    def label(var_name: str, value: str) -> str:
        text = tr(var_name, user_id)
        is_selected = current == value or (current is None and value == "default")
        if limits.is_premium_color(value) and not has_premium:
            text = f"🔒 {text}"
        return f"{text} ✅" if is_selected else text

    def btn_style(value: str) -> str:
        is_selected = current == value or (current is None and value == "default")
        return "success" if is_selected else "default"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLACK", "default"),
                    callback_data="vinyl:default",
                    style=btn_style("default"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["black"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_PINK", "pink"),
                    callback_data="vinyl:pink",
                    style=btn_style("pink"),
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLUE", "blue"),
                    callback_data="vinyl:blue",
                    style=btn_style("blue"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_YELLOW", "yellow"),
                    callback_data="vinyl:yellow",
                    style=btn_style("yellow"),
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_RED", "red"),
                    callback_data="vinyl:red",
                    style=btn_style("red"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_GREEN", "green"),
                    callback_data="vinyl:green",
                    style=btn_style("green"),
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLOODY", "bloody"),
                    callback_data="vinyl:bloody",
                    style=btn_style("bloody"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_ROSE", "rose"),
                    callback_data="vinyl:rose",
                    style=btn_style("rose"),
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_EMERALD", "Emerald"),
                    callback_data="vinyl:emerald",
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["emerald"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_KOI", "koi"),
                    callback_data="vinyl:koi",
                    style=btn_style("koi"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["koi"],
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_KISS", "kiss"),
                    callback_data="vinyl:kiss",
                    style=btn_style("kiss"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["kiss"],
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_ALI", "ali"),
                    callback_data="vinyl:ali",
                    style=btn_style("ali"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["ali"],
                ),
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_VINYL_COLOR_PREVIEW", user_id),
                    url=VINYL_TEMPLATE_PREVIEW_URL,
                    icon_custom_emoji_id=PREVIEW_EMOJI_ID,
                )
            ],
            [InlineKeyboardButton(text=tr("BTN_BACK", user_id), callback_data="vinyl_menu:back")],
        ]
    )


@router.callback_query(F.data == "customize:open")
async def on_customize_open(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    text = (
        "⚙️ Customize your disc settings:"
        if get_user_lang(user_id) == "en"
        else "⚙️ تخصيص إعدادات القرص:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=build_customize_keyboard(user_id),
    )
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
        reply_markup=build_start_keyboard(user_id, me.username),
    )
    await callback.answer()


@router.callback_query(F.data == "vinyl_menu:open")
async def on_vinyl_menu_open(callback, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else 0
    if developer_menu_image_file_id and not get_text_rich_content("MSG_VINYL_COLOR_INFO", user_id):
        await callback.message.delete()
        await callback.message.answer_photo(
            developer_menu_image_file_id,
            caption=tr("MSG_VINYL_COLOR_INFO", user_id),
            reply_markup=build_vinyl_color_keyboard(user_id),
        )
    elif developer_menu_image_file_id:
        await callback.message.delete()
        await send_text_variable(
            bot,
            callback.message.chat.id,
            "MSG_VINYL_COLOR_INFO",
            user_id,
            reply_markup=build_vinyl_color_keyboard(user_id),
        )
    else:
        await edit_text_variable(
            callback.message,
            bot,
            "MSG_VINYL_COLOR_INFO",
            user_id,
            reply_markup=build_vinyl_color_keyboard(user_id),
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
            reply_markup=build_customize_keyboard(user_id),
        )
    else:
        await callback.message.edit_text(
            "⚙️ تخصيص إعدادات القرص:", reply_markup=build_customize_keyboard(user_id)
        )
    await callback.answer()


@router.channel_post(F.audio)
async def on_channel_audio(message: Message, bot: Bot):
    """
    نفس فكرة on_audio بالضبط، لكن للمنشورات الصوتية داخل القنوات. ما فيه أي
    فحص limits/whitelist هنا (تلك الحدود خاصة بالاستخدام الشخصي بالخاص)،
    لأن التحكم بالخطوات محصور أصلاً على أدمن القناة عبر resolve_callback_uid.
    """
    chat_id = message.chat.id
    key = _channel_key(chat_id, message.message_id)
    audio = message.audio

    pending_audio[key] = {
        "audio": audio,
        "message": message,
        "expires_at": time.time() + WIZARD_TTL_SECONDS,
        "job_id": uuid.uuid4().hex,
        "uid": key,
        "channel_msg_ids": [],
    }
    wizard_state.pop(key, None)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_QUICK_CREATE", key),
                    callback_data=_with_channel_suffix("mode:quick", chat_id, message.message_id),
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_CUSTOMIZE", key),
                    callback_data=_with_channel_suffix("mode:custom", chat_id, message.message_id),
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_CANCEL", key),
                    callback_data=_with_channel_suffix("cancel_queue", chat_id, message.message_id),
                )
            ],
        ]
    )

    try:
        prompt = await reply_text_variable(
            message, bot, "MSG_CHOOSE_MODE", key, reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        pending_audio.pop(key, None)
        if "rights" in str(e).lower() or "administrator" in str(e).lower():
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
    uid = _group_key(message.chat.id, message.message_id) if is_group else owner_id
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
            await send_ephemeral_text(bot, message.chat.id, owner_id, too_large_text)
        else:
            await reply_with_premium_emoji(message, too_large_text)
        return

    pending_audio[uid] = {
        "audio": audio,
        "message": message,
        "expires_at": time.time() + WIZARD_TTL_SECONDS,
        "job_id": uuid.uuid4().hex,
        "uid": owner_id,
        "owner_user_id": owner_id,
    }
    wizard_state.pop(uid, None)
    pending_images.pop(uid, None)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_QUICK_CREATE", owner_id), callback_data="mode:quick"
                )
            ],
            [InlineKeyboardButton(text=tr("BTN_CUSTOMIZE", owner_id), callback_data="mode:custom")],
            [InlineKeyboardButton(text=tr("BTN_CANCEL", owner_id), callback_data="cancel_queue")],
        ]
    )
    if is_group:
        group_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=tr("BTN_QUICK_CREATE", owner_id),
                        callback_data=_with_channel_suffix(
                            "mode:quick", message.chat.id, message.message_id
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=tr("BTN_CUSTOMIZE", owner_id),
                        callback_data=_with_channel_suffix(
                            "mode:custom", message.chat.id, message.message_id
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=tr("BTN_CANCEL", owner_id),
                        callback_data=_with_channel_suffix(
                            "cancel_queue", message.chat.id, message.message_id
                        ),
                    )
                ],
            ]
        )
        sent = await send_ephemeral_text(
            bot,
            message.chat.id,
            owner_id,
            tr("MSG_CHOOSE_MODE", owner_id),
            reply_markup=group_keyboard,
        )
        pending_audio[uid]["ephemeral_message_id"] = sent.ephemeral_message_id
    else:
        await reply_text_variable(message, bot, "MSG_CHOOSE_MODE", owner_id, reply_markup=keyboard)


def _get_pending_audio_or_none(uid: int) -> dict | None:
    pending = pending_audio.get(uid)
    if not pending or time.time() > pending["expires_at"]:
        pending_audio.pop(uid, None)
        wizard_state.pop(uid, None)
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
        limit_text = tr("MSG_LIMIT_REACHED_FMT", owner_id).format(**format_kwargs)
        await send_ephemeral_text(
            bot,
            message.chat.id,
            owner_id,
            limit_text,
            reply_markup=build_buy_stars_keyboard(owner_id),
        )
        return
    await reply_text_variable(
        message,
        bot,
        "MSG_LIMIT_REACHED_FMT",
        owner_id,
        reply_markup=build_buy_stars_keyboard(owner_id),
        **format_kwargs,
    )


async def _launch_job(bot: Bot, uid: int, job: dict) -> bool:
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
        await notify_queue_position(bot, message.chat.id, context_key, job["job_id"])
    return True


@router.callback_query(F.data.startswith("mode:quick"))
async def on_mode_quick(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    _, uid, channel_chat_id = resolved
    pending = _get_pending_audio_or_none(uid)
    if not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return

    audio = pending["audio"]
    if audio.thumbnail:
        job = dict(pending)
        job["context_key"] = uid
        if _is_group_context(uid):
            job["uid"] = pending.get("owner_user_id", uid)
            job["status_ephemeral_message_id"] = _ephemeral_id(pending)
        else:
            await edit_wizard_text_variable(bot, uid, callback.message, "MSG_JOB_QUEUED")
        pending_audio.pop(uid, None)
        job["segment_start"] = 0.0
        await _launch_job(bot, job["uid"], job)
    elif channel_chat_id is not None:
        pending["awaiting_reply_image"] = True
        await _edit_wizard_text(
            bot, uid, callback.message, texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY
        )
    else:
        pending_images[uid] = {
            "quick_mode": True,
            "audio_message_id": pending["message"].message_id,
        }
        await edit_wizard_text_variable(bot, uid, callback.message, "MSG_QUICK_NEED_IMAGE")
    await callback.answer()


@router.callback_query(F.data.startswith("mode:custom"))
async def on_mode_custom(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    _, uid, _channel_chat_id = resolved
    pending = _get_pending_audio_or_none(uid)
    if not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    wizard_state[uid] = {}
    ch_chat, ch_msg = _channel_ctx(uid)
    await _edit_wizard_text(
        bot,
        uid,
        callback.message,
        tr("MSG_WIZ_CHOOSE_COLOR", uid),
        reply_markup=build_wiz_color_keyboard(uid, ch_chat, ch_msg),
    )
    await callback.answer()


def _channel_ctx(uid) -> tuple[int | None, int | None]:
    """
    يستخرج (chat_id, message_id) من مفتاح سياق القناة أو المجموعة، أو
    (None, None) لو مو سياق مشترك (يعني محادثة خاصة بمفتاح uid عادي).
    البادئتان (CHANNEL_KEY_PREFIX و GROUP_KEY_PREFIX) بحرف واحد بالضبط،
    فنفس منطق القص (uid[1:]) يشتغل لكلتيهما.
    """
    if not _is_shared_context(uid):
        return None, None
    rest = uid[1:]
    chat_str, _, msg_str = rest.partition(":")
    try:
        return int(chat_str), int(msg_str)
    except ValueError:
        return None, None


def build_wiz_color_keyboard(
    user_id: int = 0, channel_chat_id: int | None = None, channel_message_id: int | None = None
) -> InlineKeyboardMarkup:

    def cb(data: str) -> str:
        return _with_channel_suffix(data, channel_chat_id, channel_message_id)

    has_premium = user_has_premium_access(user_id)

    def wiz_label(var_name: str, value: str) -> str:
        text = tr(var_name, user_id)
        if limits.is_premium_color(value) and not has_premium:
            return f"🔒 {text}"
        return text

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_BLACK", "default"),
                    callback_data=cb("wiz_color:default"),
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_PINK", "pink"),
                    callback_data=cb("wiz_color:pink"),
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_BLUE", "blue"),
                    callback_data=cb("wiz_color:blue"),
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_YELLOW", "yellow"),
                    callback_data=cb("wiz_color:yellow"),
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_RED", "red"),
                    callback_data=cb("wiz_color:red"),
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_GREEN", "green"),
                    callback_data=cb("wiz_color:green"),
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_BLOODY", "bloody"),
                    callback_data=cb("wiz_color:bloody"),
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_EMERALD", "emerald"),
                    callback_data=cb("wiz_color:emerald"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["emerald"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_ROSE", "rose"),
                    callback_data=cb("wiz_color:rose"),
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_KOI", "koi"),
                    callback_data=cb("wiz_color:koi"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["koi"],
                ),
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_KISS", "kiss"),
                    callback_data=cb("wiz_color:kiss"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["kiss"],
                ),
            ],
            [
                InlineKeyboardButton(
                    text=wiz_label("BTN_VINYL_ALI", "ali"),
                    callback_data=cb("wiz_color:ali"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["ali"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_VINYL_COLOR_PREVIEW", user_id),
                    url=VINYL_TEMPLATE_PREVIEW_URL,
                    icon_custom_emoji_id=PREVIEW_EMOJI_ID,
                )
            ],
        ]
    )


def build_wiz_speed_keyboard(
    user_id: int = 0, channel_chat_id: int | None = None, channel_message_id: int | None = None
) -> InlineKeyboardMarkup:
    labels = [
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_19RPM", user_id), "19"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=_with_channel_suffix(
                f"wiz_speed:{value}", channel_chat_id, channel_message_id
            ),
        )
        for label, value in labels
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:2],
            buttons[2:4],
            buttons[4:6],
        ]
    )


def build_wiz_image_keyboard(
    has_thumbnail: bool,
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    if has_thumbnail:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("BTN_WIZ_SKIP_IMAGE", user_id),
                    callback_data=_with_channel_suffix(
                        "wiz_image:skip", channel_chat_id, channel_message_id
                    ),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("BTN_CANCEL", user_id),
                callback_data=_with_channel_suffix(
                    "cancel_queue", channel_chat_id, channel_message_id
                ),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wiz_segment_keyboard(
    total_duration: float,
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None,
) -> InlineKeyboardMarkup:
    minutes_count = max(1, math.ceil(total_duration / 60))
    buttons = []
    for i in range(minutes_count):
        start = i * 60
        if start >= total_duration:
            break
        buttons.append(
            InlineKeyboardButton(
                text=tr("BTN_WIZ_SEGMENT_FMT", user_id).format(n=i + 1),
                callback_data=_with_channel_suffix(
                    f"wiz_segment:{start}", channel_chat_id, channel_message_id
                ),
                style="success",
            )
        )
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("wiz_color:"))
async def on_wiz_color(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    base, uid, _channel_chat_id = resolved
    state = wizard_state.get(uid)
    if state is None or not _get_pending_audio_or_none(uid):
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    choice = base.split(":", 1)[1]
    presser_id = callback.from_user.id if callback.from_user else 0
    if choice in VALID_VINYL_COLOR_VALUES:
        if limits.is_premium_color(choice) and not user_has_premium_access(presser_id):
            await callback.answer(tr("MSG_COLOR_PREMIUM_ONLY", presser_id), show_alert=True)
            await callback.message.reply(
                tr("MSG_COLOR_PREMIUM_ONLY", presser_id),
                reply_markup=build_buy_stars_keyboard(presser_id),
            )
            return
        if choice == "default":
            developer_vinyl_choice.pop(uid, None)
        else:
            developer_vinyl_choice[uid] = choice
    else:
        developer_vinyl_choice.pop(uid, None)

    ch_chat, ch_msg = _channel_ctx(uid)
    await _edit_wizard_text(
        bot,
        uid,
        callback.message,
        tr("MSG_WIZ_CHOOSE_SPEED", uid),
        reply_markup=build_wiz_speed_keyboard(uid, ch_chat, ch_msg),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz_speed:"))
async def on_wiz_speed(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    base, uid, _channel_chat_id = resolved
    state = wizard_state.get(uid)
    pending = _get_pending_audio_or_none(uid)
    if state is None or not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    value = base.split(":", 1)[1]
    user_rotation_seconds[uid] = 0.0 if value == "full" else 60 / float(value)

    has_thumb = bool(pending["audio"].thumbnail)
    ch_chat, ch_msg = _channel_ctx(uid)
    image_text = (
        texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY_WITH_SKIP
        if ch_chat is not None and has_thumb
        else texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY
        if ch_chat is not None
        else tr("MSG_WIZ_CHOOSE_IMAGE", uid)
    )
    await _edit_wizard_text(
        bot,
        uid,
        callback.message,
        image_text,
        reply_markup=build_wiz_image_keyboard(has_thumb, uid, ch_chat, ch_msg),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz_image:skip"))
async def on_wiz_image_skip(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    _, uid, _channel_chat_id = resolved
    pending = _get_pending_audio_or_none(uid)
    state = wizard_state.get(uid)
    if state is None or not pending:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    if not pending["audio"].thumbnail:
        await callback.answer(tr("MSG_WIZ_NO_IMAGE_TO_SKIP", uid), show_alert=True)
        return
    await _wiz_advance_to_segment_or_finish(
        bot,
        uid,
        callback.message,
        lambda text, **kwargs: _edit_wizard_text(bot, uid, callback.message, text, **kwargs),
    )
    await callback.answer()


async def _wiz_advance_to_segment_or_finish(
    bot: Bot, uid, target_message: Message, send_func
) -> None:
    pending = pending_audio.get(uid)
    if not pending:
        return
    audio = pending["audio"]
    total_duration = audio.duration or 0

    if total_duration <= config.MAX_DURATION_SECONDS:
        await _finish_wizard(bot, uid, send_func, segment_start=0.0)
        return

    ch_chat, ch_msg = _channel_ctx(uid)
    sent = await send_func(
        tr("MSG_WIZ_CHOOSE_SEGMENT", uid),
        reply_markup=build_wiz_segment_keyboard(total_duration, uid, ch_chat, ch_msg),
    )
    if (
        _is_shared_context(uid)
        and sent is not None
        and sent.message_id not in pending.get("channel_msg_ids", [])
    ):
        pending.setdefault("channel_msg_ids", []).append(sent.message_id)


@router.callback_query(F.data.startswith("wiz_segment:"))
async def on_wiz_segment(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    base, uid, _channel_chat_id = resolved
    start_seconds = float(base.split(":", 1)[1])
    await _finish_wizard(
        bot,
        uid,
        lambda text, **kwargs: _edit_wizard_text(bot, uid, callback.message, text, **kwargs),
        segment_start=start_seconds,
    )
    await callback.answer()


async def _finish_wizard(bot: Bot, uid, send_func, segment_start: float) -> None:
    pending = pending_audio.pop(uid, None)
    wizard_state.pop(uid, None)
    if not pending:
        await send_func(tr("MSG_WIZ_EXPIRED", uid))
        return

    job = dict(pending)
    owner_id = pending.get("owner_user_id", uid)
    job["uid"] = owner_id
    job["context_key"] = uid
    job["segment_start"] = segment_start
    job["vinyl_choice"] = developer_vinyl_choice.get(uid)
    job["rotation_seconds"] = user_rotation_seconds.get(uid, config.ROTATION_SECONDS)

    if _is_group_context(uid):
        job["status_ephemeral_message_id"] = _ephemeral_id(pending)
        await _launch_job(bot, owner_id, job)
        return

    if _is_channel_context(uid):
        starting_text = tr("MSG_WIZ_STARTING", owner_id)
        entities = build_premium_entities_from_text(starting_text)
        sent = (
            await send_func(starting_text, entities=entities)
            if entities
            else await send_func(starting_text)
        )
        if sent is not None:
            job.setdefault("channel_msg_ids", [])
            if sent.message_id not in job["channel_msg_ids"]:
                job["channel_msg_ids"].append(sent.message_id)
        await _launch_job(bot, owner_id, job)
        return

    job["confirm_expires_at"] = time.time() + WIZARD_TTL_SECONDS
    pending_confirm[owner_id] = job
    await send_func(
        tr("MSG_WIZ_REVIEW", owner_id),
        reply_markup=build_wiz_confirm_keyboard(owner_id),
    )


pending_confirm: dict[int, dict] = {}


def build_wiz_confirm_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_WIZ_PREVIEW", user_id), callback_data="wiz_preview_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_WIZ_CONFIRM_FULL", user_id),
                    callback_data="wiz_full_confirm",
                    style="success",
                )
            ],
            [InlineKeyboardButton(text=tr("BTN_CANCEL", user_id), callback_data="cancel_queue")],
        ]
    )


async def _run_quick_preview(bot: Bot, target_message: Message, uid: int, job: dict) -> None:
    """
    يولّد معاينة سريعة (٣ ثواني، دقة منخفضة) بنفس إعدادات المستخدم المختارة
    (اللون/السرعة/الصورة/المقطع) ويرسلها كفيديو عادي — مو Video Note — عشان
    يتأكد المستخدم من الشكل قبل ما ينتظر الإنتاج الكامل.
    """
    audio = job["audio"]
    job_id = job["job_id"]
    ext = audio.file_name.split(".")[-1] if audio.file_name else "mp3"
    preview_audio_path = tmp(f"preview_{uid}_{job_id}_audio.{ext}")
    preview_thumb_path = tmp(f"preview_{uid}_{job_id}_thumb.jpg")
    preview_disc_path = tmp(f"preview_{uid}_{job_id}_disc.png")
    preview_out_path = tmp(f"preview_{uid}_{job_id}_out.mp4")

    try:
        await bot.send_chat_action(target_message.chat.id, action=ChatAction.UPLOAD_VIDEO)
        await download_with_retries(
            bot, audio.file_id, preview_audio_path, timeout_seconds=180, retries=2
        )

        thumbnail_file_id = job.get("thumbnail_file_id")
        if not thumbnail_file_id and getattr(audio, "thumbnail", None) is not None:
            thumbnail_file_id = audio.thumbnail.file_id
        if not thumbnail_file_id:
            await target_message.reply(texts_module.ERR_NO_THUMBNAIL_AVAILABLE)
            return
        await download_with_retries(
            bot, thumbnail_file_id, preview_thumb_path, timeout_seconds=60, retries=2
        )

        vinyl_choice = job.get("vinyl_choice")
        await asyncio.to_thread(
            build_disc,
            preview_thumb_path,
            get_developer_vinyl_path(uid, vinyl_choice),
            preview_disc_path,
            get_developer_hole_ratio(vinyl_choice),
            config.DISC_SIZE,
        )
        shadow_path = get_developer_shadow_path(uid, vinyl_choice)

        await render_preview(
            preview_disc_path,
            shadow_path,
            preview_audio_path,
            preview_out_path,
            rotation_seconds=job.get("rotation_seconds", get_user_rotation_seconds(uid)),
            native_size=config.DISC_SIZE,
            start_offset=job.get("segment_start", 0.0),
        )

        await target_message.reply_video(
            FSInputFile(preview_out_path),
            caption=tr("MSG_PREVIEW_READY_CAPTION", uid),
            reply_markup=build_wiz_confirm_keyboard(uid),
        )
    except Exception:
        logger.exception("فشل توليد المعاينة السريعة")
        try:
            await target_message.reply(
                tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text="preview failed")
            )
        except Exception:
            pass
    finally:
        cleanup(preview_audio_path, preview_thumb_path, preview_disc_path, preview_out_path)


@router.callback_query(F.data == "wiz_preview_confirm")
async def on_wiz_preview_confirm(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    job = pending_confirm.get(uid)
    if not job:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    await callback.answer(tr("MSG_PREVIEW_STARTING", uid))
    await _run_quick_preview(bot, callback.message, uid, job)


@router.callback_query(F.data == "wiz_full_confirm")
async def on_wiz_full_confirm(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    job = pending_confirm.pop(uid, None)
    if not job:
        await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
        return
    await callback.answer()
    starting_text = tr("MSG_WIZ_STARTING", uid)
    entities = build_premium_entities_from_text(starting_text)
    if entities:
        await callback.message.reply(starting_text, entities=entities)
    else:
        await callback.message.reply(starting_text)
    await _launch_job(bot, uid, job)


@router.callback_query(F.data.startswith("cancel_queue"))
async def on_cancel_queue(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    _, uid, _channel_chat_id = resolved
    pending = pending_audio.get(uid)
    owner_id = pending.get("owner_user_id", uid) if pending else uid
    cancel_user_jobs(owner_id)
    if _is_group_context(uid):
        eid = _ephemeral_id(pending)
        if eid is not None:
            try:
                await delete_ephemeral_text(bot, callback.message.chat.id, owner_id, eid)
            except Exception:
                pass
    else:
        await edit_text_variable(callback.message, bot, "MSG_QUEUE_CANCELED_EDIT", uid)
    pending_audio.pop(uid, None)
    wizard_state.pop(uid, None)
    if isinstance(uid, int):
        pending_confirm.pop(uid, None)
    await callback.answer(tr("MSG_QUEUE_CANCELED_ANSWER", uid))


@router.callback_query(F.data == "add_image")
async def on_add_image(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    await reply_text_variable(callback.message, bot, "MSG_SEND_IMAGE_NOW", uid)
    pending_images[callback.from_user.id] = {"waiting_for_image": True}
    await callback.answer()


@router.channel_post(F.photo)
async def on_channel_photo_reply(message: Message, bot: Bot):
    """
    يقابل on_photo_for_audio لكن بسياق القناة: بدل انتظار أي صورة توصل بالخاص،
    ننتظر تحديدًا صورة تُرسل كـ "رد" على رسالة البوت (اختيار الوضع/خطوات
    الـ Wizard)، ونربطها بالطلب الصحيح عبر channel_reply_index. أي صورة
    بالقناة بدون رد على رسالة البوت تُتجاهل بالكامل (ما هي جزء من أي تدفق).
    """
    if not message.reply_to_message:
        return
    chat_id = message.chat.id
    key = channel_reply_index.get((chat_id, message.reply_to_message.message_id))
    if key is None:
        return

    pending = _get_pending_audio_or_none(key)
    if not pending:
        return

    photo = message.photo[-1]
    pending["thumbnail_file_id"] = photo.file_id
    pending.setdefault("channel_msg_ids", []).append(message.message_id)

    if pending.pop("awaiting_reply_image", False) and key not in wizard_state:
        pending_audio.pop(key, None)
        job = dict(pending)
        job["context_key"] = key
        job["segment_start"] = 0.0
        await _launch_job(bot, key, job)
        return

    await _wiz_advance_to_segment_or_finish(bot, key, message, message.reply)


@router.message(F.photo)
async def on_photo_for_audio(message: Message, bot: Bot):
    global developer_menu_image_file_id
    owner_id = message.from_user.id if message.from_user else 0
    group_uid = (
        _group_pending_key_for_user(message.chat.id, owner_id)
        if message.chat.type in ("group", "supergroup")
        else None
    )
    uid = group_uid or owner_id
    if owner_id == config.DEVELOPER_ID and owner_id in awaiting_menu_image:
        awaiting_menu_image.discard(owner_id)
        developer_menu_image_file_id = message.photo[-1].file_id
        await message.reply(texts_module.MSG_DEV_MENU_IMAGE_SAVED)
        return

    if uid in wizard_state:
        pending_entry = _get_pending_audio_or_none(uid)
        if not pending_entry:
            await reply_text_variable(message, bot, "MSG_AUDIO_EXPIRED", uid)
            return
        photo = message.photo[-1]
        pending_entry["thumbnail_file_id"] = photo.file_id
        if _is_group_context(uid):
            original = pending_entry.get("message")
            await edit_wizard_text_variable(bot, uid, original, "MSG_IMAGE_RECEIVED")
            await _wiz_advance_to_segment_or_finish(
                bot,
                uid,
                original,
                lambda text, **kwargs: _edit_wizard_text(bot, uid, original, text, **kwargs),
            )
        else:
            await reply_text_variable(message, bot, "MSG_IMAGE_RECEIVED", uid)
            await _wiz_advance_to_segment_or_finish(bot, uid, message, message.reply)
        return

    pending = pending_images.get(uid)
    if not pending:
        return

    if pending.get("quick_mode"):
        photo = message.photo[-1]
        pending_entry = _get_pending_audio_or_none(uid)
        if not pending_entry:
            pending_images.pop(uid, None)
            await reply_text_variable(message, bot, "MSG_AUDIO_EXPIRED", uid)
            return

        job = dict(pending_entry)
        job["thumbnail_file_id"] = photo.file_id
        job["uid"] = pending_entry.get("owner_user_id", uid)
        job["context_key"] = uid
        job["segment_start"] = 0.0

        if not _is_group_context(uid):
            await reply_text_variable(message, bot, "MSG_IMAGE_RECEIVED", uid)
        else:
            original = job.get("message")
            if original is not None:
                await edit_wizard_text_variable(bot, uid, original, "MSG_IMAGE_RECEIVED")
        pending_audio.pop(uid, None)
        pending_images.pop(uid, None)
        await _launch_job(bot, job["uid"], job)
        return

    if pending.get("waiting_for_image"):
        photo = message.photo[-1]
        pending_entry = pending_audio.get(uid)
        if not pending_entry:
            await reply_text_variable(message, bot, "MSG_NO_PENDING_AUDIO", uid)
            return

        if time.time() > pending_entry["expires_at"]:
            pending_audio.pop(uid, None)
            pending_images.pop(uid, None)
            await reply_text_variable(message, bot, "MSG_AUDIO_EXPIRED", uid)
            return

        pending_images[uid] = {
            "photo_file_id": photo.file_id,
            "audio_message_id": pending.get("audio_message_id"),
        }

        job = dict(pending_entry)
        job["thumbnail_file_id"] = photo.file_id
        job["message"] = pending_entry["message"]
        job["uid"] = pending_entry.get("owner_user_id", owner_id)
        job["context_key"] = uid
        job["job_id"] = pending_entry["job_id"]
        job["segment_start"] = 0.0

        if not _is_group_context(uid):
            await reply_text_variable(message, bot, "MSG_IMAGE_RECEIVED", uid)
        else:
            original = job.get("message")
            if original is not None:
                await edit_wizard_text_variable(bot, uid, original, "MSG_IMAGE_RECEIVED")
        pending_audio.pop(uid, None)
        pending_images.pop(uid, None)

        await _launch_job(bot, job["uid"], job)
        return


@router.callback_query(F.data.startswith("vinyl:"))
async def on_vinyl_choice(callback, bot: Bot):
    choice = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    if choice in VALID_VINYL_COLOR_VALUES:
        if limits.is_premium_color(choice) and not user_has_premium_access(user_id):
            await callback.answer(tr("MSG_COLOR_PREMIUM_ONLY", user_id), show_alert=True)
            await callback.message.reply(
                tr("MSG_COLOR_PREMIUM_ONLY", user_id),
                reply_markup=build_buy_stars_keyboard(user_id),
            )
            return
        if choice == "default":
            developer_vinyl_choice.pop(user_id, None)
        else:
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
    await callback.message.edit_reply_markup(reply_markup=build_customize_keyboard(user_id))
    await callback.answer(tr("MSG_SPEED_SAVED_ANSWER", user_id))


router.include_router(developer_router)
router.include_router(developer_text_router)
router.include_router(
    create_language_router(
        edit_text_variable,
        build_vinyl_color_keyboard,
        build_customize_keyboard,
        build_start_keyboard,
    )
)
router.include_router(create_start_router(reply_text_variable, build_start_keyboard))
router.include_router(create_payment_router(reply_text_variable))
