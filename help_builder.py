import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import config
import help_storage
import texts as texts_module
from handlers import send_rich_message, safe_reply, tr, escape_rich_html
logger = logging.getLogger(__name__)
router = Router()
# {developer_id}
help_awaiting_text: set[int] = set()
help_awaiting_button: set[int] = set()
def _is_dev(uid: int) -> bool:
    return bool(uid) and uid == config.DEVELOPER_ID
def _buttons_keyboard(buttons: list[dict]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text=b["text"], url=b["url"])] for b in buttons]
    return InlineKeyboardMarkup(inline_keyboard=rows)
def _builder_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 نص الرسالة (Rich Msg)", callback_data="help_builder:settext")],
        [InlineKeyboardButton(text="➕ اضف زر", callback_data="help_builder:addbtn")],
        [InlineKeyboardButton(text="👁 معاينة", callback_data="help_builder:preview")],
        [
            InlineKeyboardButton(text="💾 حفظ ونشر", callback_data="help_builder:save"),
            InlineKeyboardButton(text="🔙 رجوع", callback_data="help_builder:back"),
        ],
    ])
def _root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎛 تخصيص", callback_data="help_builder:menu")],
    ])
def _model_to_data(obj):
    """يحوّل كائنات pydantic (اللي aiogram يبنيها منها) إلى dict/list عادي."""
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(exclude_none=True)
        except Exception:
            pass
    return obj
# أنواع الوسائط اللي عند إعادة إرسالها كـ blocks تحتاج تحويل من صيغة الإخراج
# (Output: file_id/file_unique_id/width/height/...) إلى صيغة الإدخال
# (Input: حقل واحد اسمه "media" يحمل الـ file_id). لو ما حوّلناها، pydantic
# يرفض InputRichMessage بخطأ "media Field required".
_MEDIA_BLOCK_TYPES = ("video", "photo", "animation", "audio", "document")
def _normalize_media_dict(media: dict) -> dict:
    """
    يحوّل كائن وسائط بصيغة Output (فيه file_id + بيانات وصفية) إلى صيغة
    Input المطلوبة لإعادة الإرسال: {"media": file_id, ...باقي الحقول
    المسموحة زي has_spoiler لو موجودة}.
    """
    if not isinstance(media, dict):
        return media
    if "media" in media:
        # already input-shaped
        return media
    file_id = media.get("file_id")
    if not file_id:
        return media
    return {"media": file_id}


def _normalize_blocks_for_input(value):
    """
    يمشي بأي بنية (dict/list) ويطبّع كل بلوك وسائط (video/photo/animation/
    audio/document) من صيغة الإخراج (اللي وصلتنا من تليكرام) إلى صيغة
    الإدخال المطلوبة لإرسالها من جديد عبر InputRichMessage. باقي الحقول
    (النصوص، الجداول، details، custom_emoji...) تبقى كما هي بدون تغيير.
    """
    if isinstance(value, dict):
        new_dict = {}
        for k, v in value.items():
            if k in _MEDIA_BLOCK_TYPES and isinstance(v, dict):
                new_dict[k] = _normalize_media_dict(v)
            else:
                new_dict[k] = _normalize_blocks_for_input(v)
        return new_dict
    if isinstance(value, list):
        return [_normalize_blocks_for_input(item) for item in value]
    return value


async def _extract_rich_content(message: Message) -> tuple[str | None, list | None]:
    """
    يحاول يستخرج محتوى غني من رسالة وصلت من المطور، بترتيب أولوية:
    1) message.rich_message.html — لو aiogram/Bot API عرضوا الرسالة كـ Rich
       Message جاهزة بصيغة html مباشرة.
       يرجّع (html, None)
    2) message.rich_message.blocks — البنية الخام (Blocks) كما وصلتنا من
       تليكرام، بدون أي تفكيك أو تحويل لنص. نعيد إرسال نفس البنية لاحقًا
       عبر InputRichMessage(blocks=...) عشان نحافظ على الجدول/العناوين/
       الإيموجي البريميوم/الفيديوهات المضمّنة كما هي بالضبط.
       يرجّع (None, raw_blocks)
    3) message.html_text (من aiogram) — تحويل تنسيقات تليكرام العادية (بولد/
       مائل/روابط...) إلى HTML.
       يرجّع (html, None)
    4) message.text/caption كنص خام (يُهرَّب كـ HTML).
       يرجّع (html, None)
    يرجّع (None, None) لو ما فيه أي محتوى نصي بالمرة.
    """
    rich = getattr(message, "rich_message", None)
    if rich is not None:
        html_val = getattr(rich, "html", None)
        if html_val:
            return html_val, None

        blocks = getattr(rich, "blocks", None)
        if blocks:
            # 🔎 لوق دائم (INFO) للبنية الخام — انسخه وارسله لي لو النتيجة
            # النهائية ناقصة أي جزء، حتى أدقق الاستخراج على شكل بياناتك بالضبط.
            try:
                raw_dump = [
                    (b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else b)
                    for b in blocks
                ]
            except Exception:
                logger.exception("فشل تفريغ rich_message.blocks")
                raw_dump = None

            if raw_dump:
                logger.info("rich_message.blocks raw dump: %r", raw_dump)
                # ⚠️ لا نفكّك البنية إلى نص مسطّح ولا نحوّلها لـ HTML يدويًا —
                # هذا كان سبب كسر التنسيق. لكن نطبّع بلوكات الوسائط (فيديو/
                # صورة/...) من صيغة الإخراج إلى صيغة الإدخال (media بدل
                # file_id) حتى تقبلها InputRichMessage عند إعادة الإرسال.
                normalized = _normalize_blocks_for_input(raw_dump)
                return None, normalized
            logger.warning("وصلت رسالة غنية (rich_message.blocks) بدون بنية قابلة للاستخراج")

    html_text = getattr(message, "html_text", None)
    if html_text:
        return html_text, None

    if message.text:
        return escape_rich_html(message.text), None
    if message.caption:
        return escape_rich_html(message.caption), None

    return None, None


@router.message(Command("help"))
async def on_help(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0

    if not _is_dev(uid):
        published = help_storage.get_published()
        if published:
            await send_rich_message(
                bot, message.chat.id,
                html_content=published.get("html"),
                blocks=published.get("blocks"),
                reply_to_message_id=message.message_id,
                reply_markup=_buttons_keyboard(published.get("buttons", [])),
            )
        else:
            await safe_reply(message, tr("MSG_START_HELP", uid))
        return

    help_awaiting_text.discard(uid)
    help_awaiting_button.discard(uid)
    draft = help_storage.get_draft(uid)
    await send_rich_message(
        bot, message.chat.id,
        html_content=draft.get("html"),
        blocks=draft.get("blocks"),
        reply_to_message_id=message.message_id,
        reply_markup=_root_keyboard(),
    )


@router.callback_query(F.data == "help_builder:menu")
async def on_help_menu(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    if not _is_dev(uid):
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    await callback.message.reply("⚙️ اختر من ادناه:", reply_markup=_builder_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "help_builder:settext")
async def on_help_settext(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    if not _is_dev(uid):
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    help_awaiting_text.add(uid)
    help_awaiting_button.discard(uid)
    await callback.message.reply(
        "📝 أرسل الآن نص رسالة /help الجديدة.\n\n"
        "يمكنك إرسال رسالة مُنشأة من محرر تليكرام للرسائل الغنية (Rich Text "
        "Editor) مباشرة، أو نص/HTML عادي كبديل.\n\n"
        "أو أرسل /cancel_edit للإلغاء."
    )
    await callback.answer()


@router.callback_query(F.data == "help_builder:addbtn")
async def on_help_addbtn(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    if not _is_dev(uid):
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    help_awaiting_button.add(uid)
    help_awaiting_text.discard(uid)
    await callback.message.reply(
        "➕ أرسل الزر بهذه الصيغة:\n<code>نص الزر | https://example.com</code>\n\n"
        "أو أرسل /cancel_edit للإلغاء."
    )
    await callback.answer()


@router.callback_query(F.data == "help_builder:preview")
async def on_help_preview(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    if not _is_dev(uid):
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    draft = help_storage.get_draft(uid)
    await send_rich_message(
        bot, callback.message.chat.id,
        html_content=draft.get("html"),
        blocks=draft.get("blocks"),
        reply_markup=_buttons_keyboard(draft.get("buttons", [])),
    )
    await callback.answer("👁 هذي المعاينة النهائية مثل ما راح يشوفها المستخدمين")


@router.callback_query(F.data == "help_builder:save")
async def on_help_save(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    if not _is_dev(uid):
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    draft = help_storage.get_draft(uid)
    user = callback.from_user
    editor_name = (user.first_name or user.username or f"User{uid}") if user else "Unknown"
    help_storage.publish(uid, draft, editor_name=editor_name)
    await callback.message.reply("✅ تم حفظ ونشر رسالة /help الجديدة. كل المستخدمين راح يشوفوها من الآن.")
    await callback.answer("✅ تم النشر")


@router.callback_query(F.data == "help_builder:back")
async def on_help_back(callback, bot: Bot):
    uid = callback.from_user.id if callback.from_user else 0
    if not _is_dev(uid):
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    help_awaiting_text.discard(uid)
    help_awaiting_button.discard(uid)
    draft = help_storage.get_draft(uid)
    await send_rich_message(
        bot, callback.message.chat.id,
        html_content=draft.get("html"),
        blocks=draft.get("blocks"),
        reply_markup=_root_keyboard(),
    )
    await callback.answer()


@router.message(lambda m: m.text == "/cancel_edit" and bool(m.from_user)
                and (m.from_user.id in help_awaiting_text or m.from_user.id in help_awaiting_button))
async def on_help_cancel_edit(message: Message):
    # ⚠️ فلتر مقيّد بقصد: لازم يشتغل فقط إذا المطور بمنتصف تحرير خاص بـ /help،
    # حتى لا "يبلع" الحدث ويمنع /cancel_edit الأصلي بـ handlers.py (محرر
    # النصوص العام) من الاشتغال إذا كان هو المقصود.
    uid = message.from_user.id
    help_awaiting_text.discard(uid)
    help_awaiting_button.discard(uid)
    await message.reply("❌ تم إلغاء التحرير.")


@router.message(lambda m: bool(m.from_user) and m.from_user.id in help_awaiting_text)
async def on_help_text_input(message: Message, bot: Bot):
    uid = message.from_user.id
    help_awaiting_text.discard(uid)

    extracted_html, extracted_blocks = await _extract_rich_content(message)
    if not extracted_html and not extracted_blocks:
        help_awaiting_text.add(uid)
        await message.reply(
            "❌ ما قدرت أستخرج أي نص من الرسالة اللي وصلتني. جرب ترسلها كنص "
            "عادي، أو أرسل /cancel_edit للإلغاء."
        )
        return

    draft = help_storage.get_draft(uid)
    draft["html"] = extracted_html
    draft["blocks"] = extracted_blocks
    help_storage.save_draft(uid, draft)

    await message.reply("✅ تم تحديث نص المسودة.", reply_markup=_builder_menu_keyboard())


@router.message(lambda m: bool(m.from_user) and m.from_user.id in help_awaiting_button)
async def on_help_button_input(message: Message):
    uid = message.from_user.id
    help_awaiting_button.discard(uid)

    raw = (message.text or "").strip()
    if "|" not in raw:
        help_awaiting_button.add(uid)
        await message.reply(
            "❌ الصيغة غلط. أرسل هكذا:\n<code>نص الزر | https://example.com</code>\n\n"
            "أو أرسل /cancel_edit للإلغاء."
        )
        return

    text_part, _, url_part = raw.partition("|")
    text_part = text_part.strip()
    url_part = url_part.strip()

    if not text_part or not (url_part.startswith("http://") or url_part.startswith("https://")):
        help_awaiting_button.add(uid)
        await message.reply(
            "❌ لازم نص الزر ما يكون فاضي، والرابط يبدأ بـ http:// أو https://.\n"
            "جرب مرة ثانية، أو أرسل /cancel_edit للإلغاء."
        )
        return

    draft = help_storage.get_draft(uid)
    draft.setdefault("buttons", []).append({"text": text_part, "url": url_part})
    help_storage.save_draft(uid, draft)

    await message.reply(
        f"✅ تمت إضافة الزر: {text_part}",
        reply_markup=_builder_menu_keyboard(),
    )
