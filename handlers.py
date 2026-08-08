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
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, MessageEntity,
    InputRichMessage, ReplyParameters,
)

from compose import build_disc, build_disc_framed
from processor import get_duration, render_vinyl
import config
import limits
import texts as texts_module
from texts import clean_html, text_to_bold, text_to_italic, text_to_code, text_to_underline, text_to_strikethrough
import custom_texts
import math
from texts import BTN_VINYL_BLOODY , BTN_VINYL_ROSE , BTN_VINYL_EMERALD
logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# Ephemeral Messages — Bot API 9.6+
# ============================================================
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
# أقصى وقت مسموح لأي Job واحد (تنزيل + بناء + رندر + رفع). لو تجاوزه (مثلاً
# بسبب ملف صوتي تالف يعلّق ffmpeg/ffprobe للأبد)، نلغيه ونكمل للي بعده بدل
# ما يعلّق الـ worker بالكامل ويوقف كل الطابور من ورائه.
JOB_TIMEOUT_SECONDS = 8 * 60

# ============================================================
# دعم القنوات (Channels) — إنشاء القرص من منشور صوتي بقناة
# ============================================================
# كل الـ dictionaries أعلاه (pending_audio, wizard_state, developer_vinyl_choice,
# user_rotation_seconds, tracked_jobs, user_pending_jobs...) مفتاحها "uid" عادة
# int لمستخدم بالخاص. بسياق القناة نستخدم كمفتاح نص مركّب فريد بدل uid حقيقي
# (chat_id + message_id الملف الصوتي الأصلي)، فما فيه أي تصادم ممكن مع uid حقيقي
# int، وبنفس الوقت نعيد استخدام كل الدوال الموجودة (tr, build_wiz_*, get_developer_*)
# بدون أي تكرار كود — هذا هو سبب "التماسك" المطلوب.
CHANNEL_KEY_PREFIX = "c"

# نفس فكرة القنوات بالضبط، لكن للمجموعات/السوبرگروبات: مفتاح مركّب فريد
# (chat_id + message_id) بدل uid حقيقي، عشان ما يصير تصادم لو نفس الشخص
# عنده أكثر من طلب متزامن بمجموعات مختلفة أو بالخاص بنفس الوقت. الفرق
# الوحيد عن القنوات: بالمجموعة "صاحب الصوت الأصلي" يقدر يتحكم بالأزرار
# هو نفسه (مو بس الأدمن)، لأن بالمجموعة الشخص العادي هو اللي يرسل الصوت
# (بعكس القناة اللي المنشور فيها منسوب للقناة نفسها مو لعضو معيّن).
GROUP_KEY_PREFIX = "g"


def _channel_key(chat_id: int, message_id: int) -> str:
    return f"{CHANNEL_KEY_PREFIX}{chat_id}:{message_id}"


def _group_key(chat_id: int, message_id: int) -> str:
    return f"{GROUP_KEY_PREFIX}{chat_id}:{message_id}"


def _is_channel_context(uid) -> bool:
    return isinstance(uid, str) and uid.startswith(CHANNEL_KEY_PREFIX)


def _is_group_context(uid) -> bool:
    return isinstance(uid, str) and uid.startswith(GROUP_KEY_PREFIX)


def _is_shared_context(uid) -> bool:
    """سياق قناة أو مجموعة (بعكس محادثة خاصة عادية بمفتاح int)."""
    return _is_channel_context(uid) or _is_group_context(uid)


def _with_channel_suffix(callback_data: str, channel_chat_id: int | None, channel_message_id: int | None) -> str:
    """يضيف لاحقة chat_id:message_id لأي callback_data لو الكيبورد يُبنى لسياق قناة."""
    if channel_chat_id is None or channel_message_id is None:
        return callback_data
    return f"{callback_data}:{channel_chat_id}:{channel_message_id}"


def _split_channel_suffix(data: str) -> tuple[str, int | None, int | None]:
    """
    يفحص آخر جزئين من callback_data: لو كلاهما أرقام صحيحة (والأول ممكن يبدأ
    بإشارة سالبة، لأن آيدي القنوات بتليكرام سالب دايمًا)، يعتبرهم سياق قناة
    (chat_id, message_id) ويرجع باقي النص بدونهم. غير هذا يرجع النص الأصلي
    كامل بدون تغيير (سياق خاص عادي).
    """
    parts = data.split(":")
    if len(parts) >= 3:
        maybe_chat, maybe_msg = parts[-2], parts[-1]
        if maybe_chat.lstrip("-").isdigit() and maybe_msg.isdigit():
            base = ":".join(parts[:-2])
            return base, int(maybe_chat), int(maybe_msg)
    return data, None, None


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


async def notify_missing_channel_permission(bot: Bot, chat_id: int, chat_title: str, reason: str) -> None:
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


# فهرس يربط (chat_id, message_id لرسالة البوت اللي تطلب صورة) بمفتاح السياق
# المركّب، عشان لو الأدمن يرد على رسالة البوت هذي بصورة، نعرف لأي طلب تخص.
channel_reply_index: dict[tuple[int, int], str] = {}

CHANNEL_RESULT_URL = "http://t.me/discbybot?start=help"
CHANNEL_RESULT_EMOJI = "💌"


# ============================================================
# دعم إيموجي بريميوم (Telegram Premium Custom Emoji)
# ============================================================
PREMIUM_EMOJI_IDS = {
    "emerald": "5285265490350972397",
}
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


async def send_rich_message(bot: Bot, chat_id: int, html_content: str | None = None,
                             blocks: list | None = None,
                             reply_to_message_id: int | None = None,
                             reply_markup: InlineKeyboardMarkup | None = None) -> Message:
    """
    يرسل Rich Message. يدعم مصدرين للمحتوى:
    - blocks: البنية الخام كما وصلتنا من تليكرام (rich_message.blocks) — تُرسَل
      كما هي بدون أي تحويل، للحفاظ على الجدول/العناوين/الإيموجي البريميوم/
      الفيديوهات المضمّنة بالضبط كما أنشأها المطور بمحرر تليكرام.
    - html_content: نص HTML جاهز (يُستخدم فقط لو ما فيه blocks).
    """
    reply_params = ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
    try:
        if blocks:
            rich_message = InputRichMessage(blocks=blocks)
        else:
            rich_message = InputRichMessage(html=html_content or "")
        return await bot.send_rich_message(
            chat_id=chat_id,
            rich_message=rich_message,
            reply_parameters=reply_params,
            reply_markup=reply_markup,
        )
    except (AttributeError, TypeError):
        logger.warning("sendRichMessage غير مدعوم بهالنسخة من aiogram، الرجوع لرسالة عادية")
    except Exception:
        logger.exception("فشل إرسال Rich Message، الرجوع لرسالة عادية")

    # ⚠️ لا نملك تمثيل HTML موثوق لـ blocks، ولو عندنا html_content فهو مبني
    # بوسوم خاصة بـ Rich Message فقط (<p>, <table>, <mark> ...) وغير مدعومة
    # بـ sendMessage العادي (parse_mode=HTML يدعم فقط b/i/u/s/code/pre/a/tg-spoiler/tg-emoji)
    # فنحوّلها لنص خام مقروء بدل ما نرسلها كما هي ونطيح بخطأ can't parse entities
    if html_content:
        plain_fallback = re.sub(r"<[^>]+>", " ", html_content)
        plain_fallback = html.unescape(re.sub(r"\s+", " ", plain_fallback)).strip()
    else:
        plain_fallback = "⚠️ تعذّر عرض هذا المحتوى الغني بهالنسخة الحالية."
    return await bot.send_message(chat_id=chat_id, text=plain_fallback, reply_markup=reply_markup)


async def reply_rich(message: Message, bot: Bot, html_content: str | None = None,
                      blocks: list | None = None,
                      reply_markup: InlineKeyboardMarkup | None = None) -> Message:
    return await send_rich_message(
        bot, message.chat.id,
        html_content=html_content, blocks=blocks,
        reply_to_message_id=message.message_id,
        reply_markup=reply_markup,
    )


def render_progress_bar(percent: float, width: int = PROGRESS_BAR_WIDTH) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100))
    return "▓" * filled + "░" * (width - filled)


# ============================================================
# رسالة الحالة الغنية (Rich Message) — جدول + إيموجي بريميوم + شريط تظليل
# ============================================================
RICH_PROGRESS_BAR_WIDTH = 33
STATUS_EMOJI_ID = "5463010113440717314"
STATUS_EMOJI_CHAR = "👀"

# الحقل الأول: نص ثابت لا يتغيّر مع المراحل + إيموجي بريميوم ثابت
HEADER_EMOJI_ID = "5431578344472746087"
HEADER_EMOJI_CHAR = "🤩"
RICH_STATUS_HEADER_TEXT = "جاري المعالجة"  # نص ثابت — عدّله حسب رغبتك


def render_rich_status_html(
    percent: float | None,
    intro_text: str,
    stage_icons: list[str] | None = None,
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
    """
    header_emoji_html = f'<tg-emoji emoji-id="{HEADER_EMOJI_ID}">{HEADER_EMOJI_CHAR}</tg-emoji>'
    header = f'{header_emoji_html} {escape_rich_html(RICH_STATUS_HEADER_TEXT)}'

    stage_icons = stage_icons or [STATUS_EMOJI_CHAR]
    emoji_html = f'<tg-emoji emoji-id="{STATUS_EMOJI_ID}">{STATUS_EMOJI_CHAR}</tg-emoji>'

    percent = 0.0 if percent is None else max(0.0, min(100.0, percent))

    row_parts = []
    # الإيموجيات السابقة خلصت مراحلها ← تضل مظللة دايمًا
    for _ in stage_icons[:-1]:
        row_parts.append(f'<mark>{emoji_html}</mark>')

    # الإيموجي الأخير (المضاف حديثًا): يتظلل باستمرار، والنسبة جنبه تبدأ من 0% وترتفع
    row_parts.append(f'<mark>{emoji_html}</mark> {int(percent)}%')

    icons_row = " ".join(row_parts)

    return (
        f"<p>{escape_rich_html(intro_text)}</p>"
        f'<table bordered striped><tr><th align="center" valign="middle">{header}</th></tr>'
        f'<tr><td align="left" valign="middle">{icons_row}</td></tr></table>'
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

    def set_stage(self, stage_text: str, percent: float | None = None) -> None:
        if stage_text != self._last_stage_text:
            # مرحلة جديدة ← نسخة جديدة من نفس الإيموجي البريميوم تنضاف، والرقم يروح جنبها
            self.stage_icons.append(STATUS_EMOJI_CHAR)
            self._last_stage_text = stage_text
        self.stage_text = stage_text
        # ما نصفّر النسبة بين المراحل اللي ما تمرر نسبة صريحة — تضل محتفظة بآخر قيمة
        # وتستمر بالارتفاع بدل ما تختفي/ترجع None
        if percent is not None:
            self.percent = percent

    def _render_html(self) -> str:
        intro = tr("MSG_RICH_STATUS_INTRO", self.user_id)
        return render_rich_status_html(self.percent, intro, self.stage_icons)

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
                logger.warning("rich_message غير مدعوم بهالنسخة من aiogram (edit_message_text)، الرجوع لتحديث نصي عادي")
                self._rich_supported = False
            except TelegramBadRequest:
                return
            except Exception:
                logger.exception("فشل تحديث رسالة الحالة الغنية")
                return

        # fallback: تحديث نصي عادي بدون جدول/تظليل (لو النسخة ما تدعم تعديل الريتش ميسج)
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
                try:
                    await asyncio.wait_for(process_job(bot, job), timeout=JOB_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    # process_job نفسها تكون قد أرسلت رسالة توضيحية للمستخدم
                    # ونظّفت ملفاتها المؤقتة (عبر معالجة CancelledError بداخلها
                    # + finally). هنا بس نكمل للطلب التالي بدل ما نوقف الطابور.
                    logger.warning(texts_module.LOG_JOB_TIMEOUT)
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


def get_developer_vinyl_path(user_id: int, choice_override: str | None = None) -> str:
    choice = choice_override if choice_override is not None else developer_vinyl_choice.get(user_id)
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
    if choice == "rose" :
        return config.VINYL_ROSE_PATH
    if choice == "emerald" :
        return config.VINYL_EMERALD_PATH
    return config.VINYL_PATH


def get_developer_shadow_path(user_id: int, choice_override: str | None = None) -> str:
    choice = choice_override if choice_override is not None else developer_vinyl_choice.get(user_id)
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
    if choice == "rose" :
        return config.SHADOW_ROSE_PATH
    if choice == "emerald" :
        return config.SHADOW_ROSE_PATH
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
    context_key = job.get("context_key", uid)
    job_id = job["job_id"]

    audio_path = tmp(f"{uid}_{job_id}_audio.{audio.file_name.split('.')[-1] if audio.file_name else 'mp3'}")
    thumb_path = tmp(f"{uid}_{job_id}_thumb.jpg")
    disc_path = tmp(f"{uid}_{job_id}_disc.png")
    out_path = tmp(f"{uid}_{job_id}_out.mp4")
    job["temp_paths"] = [audio_path, thumb_path, disc_path, out_path]

    if _is_group_context(context_key):
        ephemeral_id = job.get("status_ephemeral_message_id")
        if ephemeral_id is None:
            # مسار احتياطي فقط إذا لم تكن هناك رسالة Wizard Ephemeral محفوظة.
            status = await send_ephemeral_text(
                bot, message.chat.id, uid,
                tr("STAGE_PREPARING", uid),
            )
            ephemeral_id = status.ephemeral_message_id
            job["status_ephemeral_message_id"] = ephemeral_id
        animator = EphemeralStatusAnimator(bot, message.chat.id, uid, int(ephemeral_id))
    else:
        initial_html = render_rich_status_html(
            0.0, tr("MSG_RICH_STATUS_INTRO", uid)
        )
        status = await send_rich_message(bot, message.chat.id, initial_html, reply_to_message_id=message.message_id)
        animator = StatusAnimator(status, bot, uid)
    animator.start()

    duration_warning_msg: Message | None = None

    try:
        await bot.send_chat_action(message.chat.id, action=ChatAction.RECORD_VIDEO_NOTE)
        animator.set_stage(tr("STAGE_DOWNLOADING_AUDIO", uid))
        await download_with_retries(bot, audio.file_id, audio_path, timeout_seconds=300, retries=3)

        thumbnail_file_id = None
        if job.get("thumbnail_file_id"):
            # المستخدم رفع صورة يدويًا (بمعالج التخصيص أو الإنشاء السريع) — لها الأولوية دائمًا
            thumbnail_file_id = job["thumbnail_file_id"]
        elif getattr(audio, "thumbnail", None) is not None:
            thumbnail_file_id = audio.thumbnail.file_id

        if thumbnail_file_id:
            animator.set_stage(tr("STAGE_DOWNLOADING_THUMBNAIL", uid))
            await download_with_retries(bot, thumbnail_file_id, thumb_path, timeout_seconds=60, retries=2)
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
        # ⛔️ حُذفت خطوة "الإطار الإضافية" (frame) هنا. build_disc بملف compose.py
        # يقبل فقط (thumb_path, vinyl_path, out_path, hole_ratio, size)، وكانت
        # هذه الدالة تُستدعى بمعامل سادس إضافي (get_developer_frame_path) غير
        # موجود بتوقيع build_disc إطلاقًا، فكان هذا يفشّل كل عملية بناء قرص
        # بخطأ TypeError. الآن الاستدعاء مطابق تمامًا لتوقيع compose.build_disc.
        #
        # 🆕 "الإطار الكلاسيكي" (frame_classic) قالب مختلف عن باقي الألوان: ما
        # عنده ملف vinyl_*.png (حلقة/ذراع فقط بدون أخاديد قرص)، فنبني القرص عبر
        # build_disc_framed (خلفية غامقة + صورة الغلاف تغطي كامل فتحة الإطار)
        # ثم نستخدم frame_classic.png نفسه كطبقة ثابتة (نفس دور shadow.png
        # العادي) بدل get_developer_shadow_path — القرص يدور تحته والإطار يبقى
        # ثابت فوقه، تمامًا مثل أي shadow آخر بـ processor.py.
        vinyl_choice = job.get("vinyl_choice")
        if vinyl_choice == "frame_classic":
            await asyncio.to_thread(
                build_disc_framed, thumb_path, disc_path,
                config.DISC_SIZE, config.FRAME_CLASSIC_LABEL_RATIO, config.FRAME_CLASSIC_DISC_RATIO,
            )
            render_shadow_path = config.FRAME_CLASSIC_PATH
        else:
            await asyncio.to_thread(
                build_disc, thumb_path, get_developer_vinyl_path(uid, vinyl_choice), disc_path,
                config.HOLE_RATIO, config.DISC_SIZE,
            )
            render_shadow_path = get_developer_shadow_path(uid, vinyl_choice)

        animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=0)

        async def on_render_progress(percent: float) -> None:
            animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=percent)

        await render_vinyl(
            disc_path, render_shadow_path, audio_path, out_path,
            rotation_seconds=job.get("rotation_seconds", get_user_rotation_seconds(uid)),
            size=config.DISC_SIZE, fps=config.OUTPUT_FPS,
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
            final_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=f"{CHANNEL_RESULT_EMOJI} كيف اسوي وحدة مثل هذي؟",
                    url=CHANNEL_RESULT_URL,
                    style="danger",
                )
            ]])

        try:
            await message.reply_video_note(FSInputFile(out_path), length=config.DISC_SIZE, reply_markup=final_keyboard)
        except TelegramBadRequest as e:
            if _is_shared_context(context_key) and ("rights" in str(e).lower() or "administrator" in str(e).lower()):
                place_label = "القناة" if _is_channel_context(context_key) else "المجموعة"
                await notify_missing_channel_permission(
                    bot, message.chat.id, message.chat.title or place_label,
                    f"نشر فيديو/رسائل بـ{place_label} (صلاحية Post Messages).",
                )
                return
            raise

        # تنظيف رسائل البوت الوسيطة (اختيار الوضع + خطوات الـ Wizard) بسياق
        # القناة/المجموعة فقط — ما نلمس منشور/رسالة الصوت الأصلية للمستخدم إطلاقًا.
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
        # يصير هذا تحديدًا لو process_job أُلغيت من الخارج بسبب تجاوز
        # JOB_TIMEOUT_SECONDS (انظر _worker أدناه). لازم نمسكها بشكل صريح
        # لأن CancelledError لا يرثها Exception بايثون 3.8+، ولو تركناها
        # تنتشر بدون التقاطها هنا فالتنظيف بالأسفل (finally) يصير طبيعي،
        # لكن نبي كمان نبلّغ المستخدم برسالة واضحة بدل ما تختفي المهمة بصمت.
        logger.warning(texts_module.LOG_JOB_TIMEOUT)
        try:
            if _is_group_context(context_key):
                animator.set_stage(texts_module.MSG_PROCESSING_TIMEOUT_FMT.format(minutes=JOB_TIMEOUT_SECONDS / 60))
            else:
                await reply_with_premium_emoji(
                    message,
                    texts_module.MSG_PROCESSING_TIMEOUT_FMT.format(minutes=JOB_TIMEOUT_SECONDS / 60),
                )
        except Exception:
            logger.exception(texts_module.LOG_SEND_ERROR_FAILED)
        raise
    except Exception as e:
        logger.exception(texts_module.LOG_PROCESS_JOB_FAILED)
        error_text = str(e) or repr(e) or e.__class__.__name__
        try:
            if _is_group_context(context_key):
                animator.set_stage(tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text=error_text))
            else:
                await reply_with_premium_emoji(message, tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text=error_text))
        except Exception:
            logger.exception(texts_module.LOG_SEND_ERROR_FAILED)
    finally:
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
        # رسالة "الملف أطول من المسموح" (وفيها إشارة لتغيير اللغة للإنكليزية
        # عبر زر 🌐) ما نحتاجها بعد انتهاء المهمة — نحذفها تلقائيًا حتى لا
        # تضل عالقة بالمحادثة.
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
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = []
    for label, value in labels:
        selected = current in (None, 0) if value == "full" else current == (60 / float(value))
        mark = " ✅" if selected else ""
        buttons.append(InlineKeyboardButton(
            text=f"{label}{mark}",
            callback_data=f"speed:{value}",
            style="primary",
        ))

    return InlineKeyboardMarkup(inline_keyboard=[
        buttons[:2],
        buttons[2:4],
        [InlineKeyboardButton(
            text=tr("BTN_VINYL_COLOR_MENU", user_id),
            callback_data="vinyl_menu:open",
            style="danger",
        )],
        [InlineKeyboardButton(
            text=tr("BTN_BACK", user_id),
            callback_data="customize:back",
            style="primary",
        )],
    ])


def build_start_keyboard(user_id: int, bot_username: str) -> InlineKeyboardMarkup:
    """لوحة الترحيب: إضافة البوت، اللغة، والتخصيص."""
    add_url = f"https://t.me/{bot_username}?startgroup=start"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ أضفني للمجموعة",
            url=add_url,
            style="primary",
        )],
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
    ])


def build_vinyl_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    current = developer_vinyl_choice.get(user_id)

    def label(var_name: str, value: str) -> str:
        text = tr(var_name, user_id)
        is_selected = current == value or (current is None and value == "default")
        return f"{text} ✅" if is_selected else text

    def btn_style(value: str) -> str:
        is_selected = current == value or (current is None and value == "default")
        return "success" if is_selected else "primary"

    return InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text=label("BTN_VINYL_BLACK", "default"),
            callback_data="vinyl:default",
            style=btn_style("default")
        )
    ],
    [
        InlineKeyboardButton(
            text=label("BTN_VINYL_PINK", "pink"),
            callback_data="vinyl:pink",
            style=btn_style("pink")
        ),
        InlineKeyboardButton(
            text=label("BTN_VINYL_BLUE", "blue"),
            callback_data="vinyl:blue",
            style=btn_style("blue")
        ),
    ],
    [
        InlineKeyboardButton(
            text=label("BTN_VINYL_YELLOW", "yellow"),
            callback_data="vinyl:yellow",
            style=btn_style("yellow")
        ),
        InlineKeyboardButton(
            text=label("BTN_VINYL_RED", "red"),
            callback_data="vinyl:red",
            style=btn_style("red")
        ),
    ],
    [
        InlineKeyboardButton(
            text=label("BTN_VINYL_GREEN", "green"),
            callback_data="vinyl:green",
            style=btn_style("green")
        ),
        InlineKeyboardButton(
            text=label("BTN_VINYL_BLOODY", "bloody"),
            callback_data="vinyl:bloody",
            style=btn_style("bloody")
        ),
    ],
    [
        InlineKeyboardButton(
            text=label("BTN_VINYL_ROSE", "rose"),
            callback_data="vinyl:rose",
            style=btn_style("rose")
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
            text=tr("BTN_BACK", user_id),
            callback_data="vinyl_menu:back"
        )
    ],
])


@router.message(F.text == "/dev", F.chat.type == "private")
async def on_dev(message: Message):
    if not message.from_user or message.from_user.id != config.DEVELOPER_ID:
        return
    await message.reply(
        texts_module.MSG_DEV_CHOOSE_TEMPLATE
        + "\n\n🔍 <code>/search كلمة</code> — للبحث بأسماء المتغيرات ومحتواها\n"
        "✏️ <code>/edit VAR_NAME [ar|en]</code> — لتحرير متغيّر مباشرة بالاسم",
        reply_markup=build_dev_keyboard(),
    )


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


@router.message(lambda m: bool(m.from_user) and m.from_user.id in awaiting_whitelist_add, F.chat.type == "private")
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


async def send_text_edit_prompt(message: Message, uid: int, var_name: str, lang: str, current_value: str) -> None:
    """يجهّز جلسة تحرير نص (يخزّن الحالة بـ awaiting_text_value) ويرسل رسالة الطلب."""
    awaiting_text_value[uid] = {"var_name": var_name, "lang": lang}
    preview = current_value if len(current_value) <= 500 else current_value[:500] + "…"
    escaped_preview = html.escape(preview)
    lang_label = "English" if lang == "en" else "عربي"
    await message.reply(
        f"📝 القيمة الحالية لـ <code>{html.escape(var_name)}</code> ({lang_label}):\n\n<code>{escaped_preview}</code>\n\n"
        "أرسل النص الجديد الآن ليحل محلها. لإيموجي بريميوم استخدم صيغة:\n"
        "<code>&lt;tg-emoji emoji-id='123'&gt;😀&lt;/tg-emoji&gt;</code>\n"
        "(بايدي رقمي صحيح ومحتوى fallback بالداخل) وسأتحقق منه قبل الحفظ.\n"
        "التنسيقات مدعومة أيضًا: **عريض**، *مائل*، `كود`، ~~مشطوب~~، &lt;&lt;مسطر&gt;&gt;.\n"
        "أو أرسل /cancel_edit للإلغاء."
    )


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

    await send_text_edit_prompt(callback.message, callback.from_user.id, var_name, lang, current_value)
    await callback.answer()


@router.message(Command("search"), F.chat.type == "private")
async def on_dev_search(message: Message, command: CommandObject):
    """
    🔍 /search <كلمة البحث>
    يبحث بأسماء المتغيرات ومحتواها (عربي + إنكليزي) ويرجّع النتائج مع معاينة النص.
    """
    if not message.from_user or message.from_user.id != config.DEVELOPER_ID:
        return

    query = (command.args or "").strip()
    if not query:
        await message.reply(
            "استخدم الأمر هكذا:\n<code>/search كلمة البحث</code>\n\n"
            "يبحث بأسماء المتغيرات والنصوص العربية والإنكليزية معًا."
        )
        return

    query_lower = query.lower()
    results: list[tuple[str, str, str]] = []  # (lang, var_name, value)

    for name in get_editable_text_names("ar"):
        value = getattr(texts_module, name, "") or ""
        if query_lower in value.lower() or query_lower in name.lower():
            results.append(("ar", name, value))

    for name in get_editable_text_names("en"):
        value = texts_module.TEXTS_EN.get(name, "") or ""
        if query_lower in value.lower() or query_lower in name.lower():
            results.append(("en", name, value))

    if not results:
        await message.reply(f"🔍 لا توجد نتائج لـ: <code>{html.escape(query)}</code>")
        return

    MAX_RESULTS_SHOWN = 15
    lines = [f"🔍 نتائج البحث عن <code>{html.escape(query)}</code> — {len(results)} نتيجة:\n"]
    for lang, name, value in results[:MAX_RESULTS_SHOWN]:
        preview = value if len(value) <= 150 else value[:150] + "…"
        preview_escaped = html.escape(preview)
        lang_label = "EN" if lang == "en" else "AR"
        lines.append(f"• <b>{html.escape(name)}</b> [{lang_label}]\n<code>{preview_escaped}</code>")

    if len(results) > MAX_RESULTS_SHOWN:
        lines.append(f"\n… و{len(results) - MAX_RESULTS_SHOWN} نتيجة إضافية، دقق البحث أكثر.")

    lines.append(
        "\n✏️ للتعديل المباشر استخدم:\n"
        "<code>/edit VAR_NAME</code> (عربي افتراضيًا)\n"
        "<code>/edit VAR_NAME en</code> (إنكليزي)"
    )

    await message.reply("\n\n".join(lines))


@router.message(Command("edit"), F.chat.type == "private")
async def on_dev_edit_command(message: Message, command: CommandObject):
    """
    ✏️ /edit VAR_NAME [ar|en]
    يبدأ تحرير مباشر لمتغيّر معيّن بالاسم، بدون الحاجة يتصفح لوحة الأزرار.
    """
    if not message.from_user or message.from_user.id != config.DEVELOPER_ID:
        return

    args = (command.args or "").strip().split()
    if not args:
        await message.reply(
            "استخدم الأمر هكذا:\n"
            "<code>/edit VAR_NAME</code> (يحرر النسخة العربية افتراضيًا)\n"
            "<code>/edit VAR_NAME en</code> (يحرر النسخة الإنكليزية)\n\n"
            "استخدم /search للبحث عن اسم المتغيّر المناسب."
        )
        return

    var_name = args[0]
    lang = args[1].lower() if len(args) > 1 else None
    uid = message.from_user.id

    if lang not in (None, "ar", "en"):
        await message.reply("⚠️ اللغة لازم تكون <code>ar</code> أو <code>en</code> فقط.")
        return

    if lang is None:
        if hasattr(texts_module, var_name) and isinstance(getattr(texts_module, var_name), str):
            lang = "ar"
        elif var_name in texts_module.TEXTS_EN:
            lang = "en"
        else:
            await message.reply(
                f"⚠️ المتغيّر <code>{html.escape(var_name)}</code> غير موجود.\n"
                "استخدم /search للبحث عن الاسم الصحيح."
            )
            return

    current_value = get_editable_text_value(var_name, lang)
    if current_value is None:
        await message.reply(
            f"⚠️ المتغيّر <code>{html.escape(var_name)}</code> غير موجود بلغة "
            f"{'الإنكليزية' if lang == 'en' else 'العربية'}."
        )
        return

    await send_text_edit_prompt(message, uid, var_name, lang, current_value)


@router.callback_query(F.data == "dev_text:back")
async def on_dev_text_back(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    awaiting_text_value.pop(callback.from_user.id, None)
    await callback.message.edit_text(texts_module.MSG_DEV_CHOOSE_TEMPLATE, reply_markup=build_dev_keyboard())
    await callback.answer()


@router.message(F.text == "/cancel_edit", F.chat.type == "private")
async def on_cancel_text_edit(message: Message):
    uid = message.from_user.id if message.from_user else 0
    if uid in awaiting_text_value:
        awaiting_text_value.pop(uid, None)
        await message.reply("❌ تم إلغاء التحرير.")


def normalize_dev_input(text: str) -> str:
    """
    يطبّع صيغ شائعة قد يلصقها المطور (مثل ماركداون تليكرام الرسمي لصيغة V2)
    إلى صيغة HTML المدعومة عندنا، عشان ما ترفضها تليكرام أو تطلع فاضية بالغلط:

    - ![إيموجي](tg://emoji?id=123) → <tg-emoji emoji-id="123">إيموجي</tg-emoji>
      (هذي هي صيغة تليكرام الرسمية للإيموجي المميز بماركداون V2)
    - \\( \\) \\. \\! إلخ (هروب MarkdownV2) → تُزال لأنها غير مطلوبة بوضع HTML
    - عناوين ماركداون بأول السطر (# ## ### ...) → تتحول لعريض <b>...</b>
    """
    if not text:
        return text

    # 1) صيغة الإيموجي الرسمية بماركداون V2: ![emoji](tg://emoji?id=ID)
    text = re.sub(
        r'!\[(.+?)\]\(tg://emoji\?id=(\d+)\)',
        r'<tg-emoji emoji-id="\2">\1</tg-emoji>',
        text,
    )

    # 2) إزالة هروب MarkdownV2 غير المطلوب بوضع HTML (مثل \( \) \. \! \-)
    text = re.sub(r'\\([\\_*\[\]()~`>#+\-=|{}.!])', r'\1', text)

    # 3) عناوين ماركداون بأول السطر (# .. ######) → عريض
    text = re.sub(r'^#{1,6}\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    return text


@router.message(
    lambda m: bool(m.from_user)
    and m.from_user.id == config.DEVELOPER_ID
    and m.from_user.id in awaiting_text_value,
    F.chat.type == "private",
)
async def on_text_value_input(message: Message, bot: Bot):
    uid = message.from_user.id
    pending = awaiting_text_value.pop(uid)
    var_name = pending["var_name"]
    lang = pending["lang"]
    new_value = normalize_dev_input(message.text or "")

    if not new_value.strip():
        awaiting_text_value[uid] = pending
        await message.reply(
            "❌ النص وصلني فاضي (أو صار فاضي بعد تنظيفه). تليكرام يرفض حفظ رسالة فاضية.\n\n"
            "لو أرسلت رسالة \"غنية\" (Rich Message) بتنسيق خاص، هذا المحرر يدعم HTML بس + "
            "صيغة ماركداون الإيموجي الرسمية <code>![إيموجي](tg://emoji?id=ID)</code>، "
            "ولا يدعم عناصر زي <code>&lt;footer&gt;</code> أو أي وسم HTML غير مدعوم بتليكرام.\n\n"
            "صحّح النص وأرسله مرة ثانية، أو أرسل /cancel_edit للإلغاء."
        )
        return

    # 1️⃣ تحقق من صيغة الإيموجي البريميوم
    is_valid_emoji, emoji_error = validate_premium_emoji_syntax(new_value)
    if not is_valid_emoji:
        awaiting_text_value[uid] = pending
        await message.reply(
            f"❌ خطأ في صيغة الإيموجي البريميوم:\n"
            f"<code>{html.escape(emoji_error)}</code>\n\n"
            "الصيغة الصحيحة:\n"
            "<code>&lt;tg-emoji emoji-id='123'&gt;🎶&lt;/tg-emoji&gt;</code>\n"
            "أو صيغة ماركداون تليكرام الرسمية:\n"
            "<code>![🎶](tg://emoji?id=123)</code>\n\n"
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


@router.message(Command("start"), F.chat.type == "private")
async def on_start(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0
    me = await bot.get_me()
    await safe_reply(
        message,
        tr("MSG_START_HELP", uid),
        reply_markup=build_start_keyboard(uid, me.username),
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
    await callback.message.edit_text(
        tr("MSG_START_HELP", user_id),
        reply_markup=build_start_keyboard(user_id, me.username),
    )
    await callback.answer()


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
        await callback.message.answer(tr("MSG_START_HELP", user_id), reply_markup=build_customize_keyboard(user_id))
    else:
        await callback.message.edit_text("⚙️ تخصيص إعدادات القرص:", reply_markup=build_customize_keyboard(user_id))
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
    is_customize_menu = bool(current_markup and any(
        btn.callback_data and (btn.callback_data.startswith("speed:") or btn.callback_data == "vinyl_menu:open")
        for row in current_markup.inline_keyboard for btn in row
    ))
    try:
        if is_color_menu:
            await callback.message.edit_text(
                tr("MSG_VINYL_COLOR_INFO", user_id),
                reply_markup=build_vinyl_color_keyboard(user_id),
            )
        elif is_customize_menu:
            await callback.message.edit_text(
                "⚙️ تخصيص إعدادات القرص:" if get_user_lang(user_id) == "ar" else "⚙️ Customize your disc settings:",
                reply_markup=build_customize_keyboard(user_id),
            )
        else:
            me = await bot.get_me()
            await callback.message.edit_text(
                tr("MSG_START_HELP", user_id),
                reply_markup=build_start_keyboard(user_id, me.username),
            )
    except TelegramBadRequest:
        pass
    await callback.answer("✅ EN" if new_lang == "en" else "✅ AR")

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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=tr("BTN_QUICK_CREATE", key),
            callback_data=_with_channel_suffix("mode:quick", chat_id, message.message_id),
        )],
        [InlineKeyboardButton(
            text=tr("BTN_CUSTOMIZE", key),
            callback_data=_with_channel_suffix("mode:custom", chat_id, message.message_id),
        )],
        [InlineKeyboardButton(
            text=tr("BTN_CANCEL", key),
            callback_data=_with_channel_suffix("cancel_queue", chat_id, message.message_id),
        )],
    ])

    try:
        prompt = await message.reply(tr("MSG_CHOOSE_MODE", key), reply_markup=keyboard)
    except TelegramBadRequest as e:
        pending_audio.pop(key, None)
        if "rights" in str(e).lower() or "administrator" in str(e).lower():
            await notify_missing_channel_permission(
                bot, chat_id, message.chat.title or "القناة",
                "إرسال الرسائل وأزرار Inline بالقناة (صلاحية Post Messages).",
            )
        else:
            logger.exception("فشل إرسال رسالة اختيار الوضع بالقناة")
        return

    # نسجّل رسالة "اختيار الوضع" بفهرس الردود لأنها هي نفسها اللي ستُستخدم/تُعدَّل
    # طول مسار الـ Wizard (لون → سرعة → صورة → مقطع)، فتسجيلها مرة وحدة يكفي
    # حتى لو انتقلنا لخطوة تطلب صورة لاحقًا (رد على نفس الرسالة).
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
        hours = max(1, math.ceil(limits.get_reset_seconds(owner_id) / 3600))
        limit_text = tr("MSG_LIMIT_REACHED_FMT", owner_id).format(
            limit=limits.get_daily_limit(owner_id),
            hours=hours,
            premium_limit=config.PREMIUM_DAILY_LIMIT,
            price=config.STARS_SUBSCRIPTION_PRICE,
        )
        if is_group:
            await send_ephemeral_text(
                bot, message.chat.id, owner_id,
                limit_text,
                reply_markup=build_buy_stars_keyboard(owner_id),
            )
        else:
            await message.reply(limit_text, reply_markup=build_buy_stars_keyboard(owner_id))
        return

    if audio.file_size and audio.file_size > config.MAX_TELEGRAM_AUDIO_SIZE_BYTES:
        logger.info(texts_module.LOG_FILE_TOO_LARGE)

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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr("BTN_QUICK_CREATE", owner_id), callback_data="mode:quick")],
        [InlineKeyboardButton(text=tr("BTN_CUSTOMIZE", owner_id), callback_data="mode:custom")],
        [InlineKeyboardButton(text=tr("BTN_CANCEL", owner_id), callback_data="cancel_queue")],
    ])
    if is_group:
        group_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=tr("BTN_QUICK_CREATE", owner_id), callback_data=_with_channel_suffix("mode:quick", message.chat.id, message.message_id))],
            [InlineKeyboardButton(text=tr("BTN_CUSTOMIZE", owner_id), callback_data=_with_channel_suffix("mode:custom", message.chat.id, message.message_id))],
            [InlineKeyboardButton(text=tr("BTN_CANCEL", owner_id), callback_data=_with_channel_suffix("cancel_queue", message.chat.id, message.message_id))],
        ])
        sent = await send_ephemeral_text(
            bot, message.chat.id, owner_id,
            tr("MSG_CHOOSE_MODE", owner_id),
            reply_markup=group_keyboard,
        )
        pending_audio[uid]["ephemeral_message_id"] = sent.ephemeral_message_id
    else:
        await message.reply(tr("MSG_CHOOSE_MODE", owner_id), reply_markup=keyboard)


def _get_pending_audio_or_none(uid: int) -> dict | None:
    pending = pending_audio.get(uid)
    if not pending or time.time() > pending["expires_at"]:
        pending_audio.pop(uid, None)
        wizard_state.pop(uid, None)
        return None
    return pending


async def _launch_job(bot: Bot, uid: int, job: dict) -> None:
    await start_job_worker(bot)
    owner_id = job.get("owner_user_id", job.get("uid", uid))
    if _is_group_context(job.get("context_key", uid)):
        job["uid"] = owner_id
    tracked_jobs[job["job_id"]] = job
    user_pending_jobs.setdefault(owner_id, set()).add(job["job_id"])
    enqueue_job(job)


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
            await edit_text_with_premium_emoji(callback.message, tr("MSG_JOB_QUEUED", uid))
        pending_audio.pop(uid, None)
        job["segment_start"] = 0.0
        await _launch_job(bot, job["uid"], job)
    elif channel_chat_id is not None:
        # بالقناة ما نقدر نطلب "أرسل صورة" برسالة عادية (لأنها راح تصير منشور
        # علني)؛ بدل هذا نطلب من الأدمن يرد على رسالة البوت نفسها بالصورة.
        pending["awaiting_reply_image"] = True
        await _edit_wizard_text(bot, uid, callback.message, texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY)
    else:
        pending_images[uid] = {"quick_mode": True, "audio_message_id": pending["message"].message_id}
        await _edit_wizard_text(bot, uid, callback.message, tr("MSG_QUICK_NEED_IMAGE", uid))
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
        bot, uid, callback.message,
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
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None
) -> InlineKeyboardMarkup:

    def cb(data: str) -> str:
        return _with_channel_suffix(
            data,
            channel_chat_id,
            channel_message_id
        )

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_BLACK", user_id),
                callback_data=cb("wiz_color:default"),
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_PINK", user_id),
                callback_data=cb("wiz_color:pink"),
                style="primary"
            ),
            InlineKeyboardButton(
                text=tr("BTN_VINYL_BLUE", user_id),
                callback_data=cb("wiz_color:blue"),
                style="primary"
            ),
        ],
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_YELLOW", user_id),
                callback_data=cb("wiz_color:yellow"),
                style="primary"
            ),
            InlineKeyboardButton(
                text=tr("BTN_VINYL_RED", user_id),
                callback_data=cb("wiz_color:red"),
                style="primary"
            ),
        ],
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_GREEN", user_id),
                callback_data=cb("wiz_color:green"),
                style="primary"
            ),
            InlineKeyboardButton(
                text=tr("BTN_VINYL_BLOODY", user_id),
                callback_data=cb("wiz_color:bloody"),
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_EMERALD", user_id),
                callback_data=cb("wiz_color:emerald"),
                style="primary",
                icon_custom_emoji_id=PREMIUM_EMOJI_IDS["emerald"],
            )
        ],
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_ROSE", user_id),
                callback_data=cb("wiz_color:rose"),
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_FRAME_CLASSIC", user_id),
                callback_data=cb("wiz_color:frame_classic"),
                style="primary"
            )
        ],
    ])


def build_wiz_speed_keyboard(user_id: int = 0, channel_chat_id: int | None = None,
                              channel_message_id: int | None = None) -> InlineKeyboardMarkup:
    labels = [
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=_with_channel_suffix(f"wiz_speed:{value}", channel_chat_id, channel_message_id),
        )
        for label, value in labels
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:]])


def build_wiz_image_keyboard(has_thumbnail: bool, user_id: int = 0, channel_chat_id: int | None = None,
                              channel_message_id: int | None = None) -> InlineKeyboardMarkup:
    rows = []
    if has_thumbnail:
        rows.append([InlineKeyboardButton(
            text=tr("BTN_WIZ_SKIP_IMAGE", user_id),
            callback_data=_with_channel_suffix("wiz_image:skip", channel_chat_id, channel_message_id),
        )])
    rows.append([InlineKeyboardButton(
        text=tr("BTN_CANCEL", user_id),
        callback_data=_with_channel_suffix("cancel_queue", channel_chat_id, channel_message_id),
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wiz_segment_keyboard(total_duration: float, user_id: int = 0, channel_chat_id: int | None = None,
                                channel_message_id: int | None = None) -> InlineKeyboardMarkup:
    minutes_count = max(1, math.ceil(total_duration / 60))
    buttons = []
    for i in range(minutes_count):
        start = i * 60
        if start >= total_duration:
            break
        buttons.append(InlineKeyboardButton(
            text=tr("BTN_WIZ_SEGMENT_FMT", user_id).format(n=i + 1),
            callback_data=_with_channel_suffix(f"wiz_segment:{start}", channel_chat_id, channel_message_id),
            style="success",
        ))
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
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
    if choice in ("black", "green", "pink", "blue", "yellow", "red", "bloody", "rose", "emerald", "frame_classic"):
        developer_vinyl_choice[uid] = choice
    else:
        developer_vinyl_choice.pop(uid, None)
    ch_chat, ch_msg = _channel_ctx(uid)
    await _edit_wizard_text(
        bot, uid, callback.message,
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
        texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY_WITH_SKIP if ch_chat is not None and has_thumb
        else texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY if ch_chat is not None
        else tr("MSG_WIZ_CHOOSE_IMAGE", uid)
    )
    await _edit_wizard_text(
        bot, uid, callback.message,
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
    await _wiz_advance_to_segment_or_finish(bot, uid, callback.message, lambda text, **kwargs: _edit_wizard_text(bot, uid, callback.message, text, **kwargs))
    await callback.answer()


async def _wiz_advance_to_segment_or_finish(bot: Bot, uid, target_message: Message, send_func) -> None:
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
    if _is_shared_context(uid) and sent is not None and sent.message_id not in pending.get("channel_msg_ids", []):
        pending.setdefault("channel_msg_ids", []).append(sent.message_id)


@router.callback_query(F.data.startswith("wiz_segment:"))
async def on_wiz_segment(callback, bot: Bot):
    resolved = await resolve_callback_uid(callback, bot)
    if resolved is None:
        return
    base, uid, _channel_chat_id = resolved
    start_seconds = float(base.split(":", 1)[1])
    await _finish_wizard(bot, uid, lambda text, **kwargs: _edit_wizard_text(bot, uid, callback.message, text, **kwargs), segment_start=start_seconds)
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

    starting_text = tr("MSG_WIZ_STARTING", owner_id)
    entities = build_premium_entities_from_text(starting_text)

    if _is_group_context(uid):
        # نفس رسالة الـEphemeral تستمر من الـWizard إلى مراحل المعالجة.
        # لا ننشئ رسالة ثانية؛ process_job سيحدّث هذه الرسالة نفسها.
        job["status_ephemeral_message_id"] = _ephemeral_id(pending)
    else:
        if entities:
            sent = await send_func(starting_text, entities=entities)
        else:
            sent = await send_func(starting_text)

        if _is_shared_context(uid) and sent is not None:
            job.setdefault("channel_msg_ids", [])
            if sent.message_id not in job["channel_msg_ids"]:
                job["channel_msg_ids"].append(sent.message_id)

    await _launch_job(bot, owner_id, job)


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
        await callback.message.edit_text(tr("MSG_QUEUE_CANCELED_EDIT", uid))
    pending_audio.pop(uid, None)
    wizard_state.pop(uid, None)
    await callback.answer(tr("MSG_QUEUE_CANCELED_ANSWER", uid))


@router.callback_query(F.data == "add_image")
async def on_add_image(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    await callback.message.reply(tr("MSG_SEND_IMAGE_NOW", uid))
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
        # سيناريو "إنشاء سريع" لملف بدون صورة مصغّرة أصلاً
        pending_audio.pop(key, None)
        job = dict(pending)
        job["context_key"] = key
        job["segment_start"] = 0.0
        await _launch_job(bot, key, job)
        return

    # غير هذا نكون بمنتصف معالج التخصيص (wizard) بخطوة اختيار/استبدال الصورة
    await _wiz_advance_to_segment_or_finish(bot, key, message, message.reply)


@router.message(F.photo)
async def on_photo_for_audio(message: Message, bot: Bot):
    global developer_menu_image_file_id
    owner_id = message.from_user.id if message.from_user else 0
    group_uid = _group_pending_key_for_user(message.chat.id, owner_id) if message.chat.type in ("group", "supergroup") else None
    uid = group_uid or owner_id
    if owner_id == config.DEVELOPER_ID and owner_id in awaiting_menu_image:
        awaiting_menu_image.discard(owner_id)
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
        if _is_group_context(uid):
            original = pending_entry.get("message")
            await _edit_wizard_text(bot, uid, original, tr("MSG_IMAGE_RECEIVED", owner_id))
            await _wiz_advance_to_segment_or_finish(
                bot, uid, original,
                lambda text, **kwargs: _edit_wizard_text(bot, uid, original, text, **kwargs),
            )
        else:
            await reply_with_premium_emoji(message, tr("MSG_IMAGE_RECEIVED", uid))
            await _wiz_advance_to_segment_or_finish(bot, uid, message, message.reply)
        return

    pending = pending_images.get(uid)
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

        job = dict(pending_entry)
        job["thumbnail_file_id"] = photo.file_id
        job["uid"] = pending_entry.get("owner_user_id", uid)
        job["context_key"] = uid
        job["segment_start"] = 0.0

        if not _is_group_context(uid):
            await reply_with_premium_emoji(message, tr("MSG_IMAGE_RECEIVED", uid))
        else:
            original = job.get("message")
            if original is not None:
                await _edit_wizard_text(bot, uid, original, tr("MSG_IMAGE_RECEIVED", owner_id))
        pending_audio.pop(uid, None)
        pending_images.pop(uid, None)
        await _launch_job(bot, job["uid"], job)
        return

    if pending.get("waiting_for_image"):
        photo = message.photo[-1]
        pending_entry = pending_audio.get(uid)
        if not pending_entry:
            await message.reply(tr("MSG_NO_PENDING_AUDIO", uid))
            return

        if time.time() > pending_entry["expires_at"]:
            pending_audio.pop(uid, None)
            pending_images.pop(uid, None)
            await message.reply(tr("MSG_AUDIO_EXPIRED", uid))
            return

        pending_images[uid] = {"photo_file_id": photo.file_id, "audio_message_id": pending.get("audio_message_id")}

        audio = pending_entry["audio"]
        job = dict(pending_entry)
        job["thumbnail_file_id"] = photo.file_id
        job["message"] = pending_entry["message"]
        job["uid"] = pending_entry.get("owner_user_id", owner_id)
        job["context_key"] = uid
        job["job_id"] = pending_entry["job_id"]
        job["segment_start"] = 0.0

        if not _is_group_context(uid):
            await reply_with_premium_emoji(message, tr("MSG_IMAGE_RECEIVED", uid))
        else:
            original = job.get("message")
            if original is not None:
                await _edit_wizard_text(bot, uid, original, tr("MSG_IMAGE_RECEIVED", owner_id))
        pending_audio.pop(uid, None)
        pending_images.pop(uid, None)

        await start_job_worker(bot)
        enqueue_job(job)
        return


@router.callback_query(F.data.startswith("vinyl:"))
async def on_vinyl_choice(callback, bot: Bot):
    choice = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    if choice in ("pink", "blue", "yellow", "red", "green","bloody", "rose", "emerald"):
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


@router.message((F.video | F.voice | F.document), F.chat.type == "private")
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


@router.message(F.successful_payment, F.chat.type == "private")
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
