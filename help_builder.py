import logging
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import help_storage
import texts as texts_module
from handlers import escape_rich_html, safe_reply, send_rich_message, tr

logger = logging.getLogger(__name__)
router = Router()

help_awaiting_text: set[int] = set()
help_awaiting_button: set[int] = set()


def _is_dev(uid: int) -> bool:
    return bool(uid) and uid == config.DEVELOPER_ID


async def _require_dev(callback: CallbackQuery) -> int | None:
    uid = callback.from_user.id if callback.from_user else 0
    if _is_dev(uid):
        return uid
    await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
    return None


def _buttons_keyboard(buttons: list[dict[str, str]]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text=b["text"], url=b["url"])] for b in buttons]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _builder_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 نص الرسالة (Rich Msg)",
                callback_data="help_builder:settext",
            )],
            [InlineKeyboardButton(text="➕ اضف زر", callback_data="help_builder:addbtn")],
            [InlineKeyboardButton(text="👁 معاينة", callback_data="help_builder:preview")],
            [
                InlineKeyboardButton(
                    text="💾 حفظ ونشر",
                    callback_data="help_builder:save",
                ),
                InlineKeyboardButton(text="🔙 رجوع", callback_data="help_builder:back"),
            ],
        ],
    )


def _root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎛 تخصيص", callback_data="help_builder:menu")],
        ]
    )


_MEDIA_BLOCK_TYPES = ("video", "photo", "animation", "audio", "document")


def _normalize_media_dict(media: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(media, dict):
        return media
    if "media" in media:
        return media
    file_id = media.get("file_id")
    return {"media": file_id} if file_id else media


def _normalize_blocks_for_input(value: Any) -> Any:
    if isinstance(value, dict):
        new_dict = {}
        for key, item in value.items():
            if key in _MEDIA_BLOCK_TYPES and isinstance(item, dict):
                new_dict[key] = _normalize_media_dict(item)
            else:
                new_dict[key] = _normalize_blocks_for_input(item)
        return new_dict
    if isinstance(value, list):
        return [_normalize_blocks_for_input(item) for item in value]
    return value


async def _extract_rich_content(message: Message) -> tuple[str | None, list | None]:
    """Extract rich blocks when available, otherwise return safe HTML."""
    rich = getattr(message, "rich_message", None)
    if rich is not None:
        html_val = getattr(rich, "html", None)
        if html_val:
            return html_val, None

        blocks = getattr(rich, "blocks", None)
        if blocks:
            try:
                raw_dump = [
                    (b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else b)
                    for b in blocks
                ]
            except Exception:
                logger.exception("فشل تفريغ rich_message.blocks")
                raw_dump = None

            if raw_dump:
                logger.debug("rich_message.blocks: %r", raw_dump)
                return None, _normalize_blocks_for_input(raw_dump)
            logger.warning(
                "وصلت رسالة غنية (rich_message.blocks) بدون بنية قابلة للاستخراج"
            )

    html_text = getattr(message, "html_text", None)
    if html_text:
        return html_text, None

    if message.text:
        return escape_rich_html(message.text), None
    if message.caption:
        return escape_rich_html(message.caption), None

    return None, None


@router.message(Command("help"))
@router.message(Command("start", magic=F.args == "help"))
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
async def on_help_menu(callback: CallbackQuery):
    if await _require_dev(callback) is None:
        return
    await callback.message.reply(
        "⚙️ اختر من ادناه:",
        reply_markup=_builder_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "help_builder:settext")
async def on_help_settext(callback: CallbackQuery):
    uid = await _require_dev(callback)
    if uid is None:
        return
    help_awaiting_text.add(uid)
    help_awaiting_button.discard(uid)
    await callback.message.reply(
        "📝 أرسل الآن نص رسالة /help الجديدة.\n\n"
        "يمكنك إرسال رسالة مُنشأة من محرر تليكرام للرسائل الغنية "
        "(Rich Text Editor) مباشرة، أو نص/HTML عادي كبديل.\n\n"
        "أو أرسل /cancel_edit للإلغاء."
    )
    await callback.answer()


@router.callback_query(F.data == "help_builder:addbtn")
async def on_help_addbtn(callback: CallbackQuery):
    uid = await _require_dev(callback)
    if uid is None:
        return
    help_awaiting_button.add(uid)
    help_awaiting_text.discard(uid)
    await callback.message.reply(
        "➕ أرسل الزر بهذه الصيغة:\n"
        "<code>نص الزر | https://example.com</code>\n\n"
        "أو أرسل /cancel_edit للإلغاء."
    )
    await callback.answer()


@router.callback_query(F.data == "help_builder:preview")
async def on_help_preview(callback: CallbackQuery, bot: Bot):
    uid = await _require_dev(callback)
    if uid is None:
        return
    draft = help_storage.get_draft(uid)
    await send_rich_message(
        bot, callback.message.chat.id,
        html_content=draft.get("html"),
        blocks=draft.get("blocks"),
        reply_markup=_buttons_keyboard(draft.get("buttons", [])),
    )
    await callback.answer(
        "👁 هذي المعاينة النهائية مثل ما راح يشوفها المستخدمين"
    )


@router.callback_query(F.data == "help_builder:save")
async def on_help_save(callback: CallbackQuery):
    uid = await _require_dev(callback)
    if uid is None:
        return
    draft = help_storage.get_draft(uid)
    user = callback.from_user
    editor_name = (user.first_name or user.username or f"User{uid}") if user else "Unknown"
    help_storage.publish(uid, draft, editor_name=editor_name)
    await callback.message.reply(
        "✅ تم حفظ ونشر رسالة /help الجديدة. "
        "كل المستخدمين راح يشوفوها من الآن."
    )
    await callback.answer("✅ تم النشر")


@router.callback_query(F.data == "help_builder:back")
async def on_help_back(callback: CallbackQuery, bot: Bot):
    uid = await _require_dev(callback)
    if uid is None:
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


@router.message(
    lambda m: m.text == "/cancel_edit"
    and bool(m.from_user)
    and (
        m.from_user.id in help_awaiting_text
        or m.from_user.id in help_awaiting_button
    )
)
async def on_help_cancel_edit(message: Message):
    uid = message.from_user.id
    help_awaiting_text.discard(uid)
    help_awaiting_button.discard(uid)
    await message.reply("❌ تم إلغاء التحرير.")


@router.message(lambda m: bool(m.from_user) and m.from_user.id in help_awaiting_text)
async def on_help_text_input(message: Message):
    uid = message.from_user.id
    help_awaiting_text.discard(uid)

    extracted_html, extracted_blocks = await _extract_rich_content(message)
    if not extracted_html and not extracted_blocks:
        help_awaiting_text.add(uid)
        await message.reply(
            "❌ ما قدرت أستخرج أي نص من الرسالة اللي وصلتني. "
            "جرب ترسلها كنص عادي، أو أرسل /cancel_edit للإلغاء."
        )
        return

    draft = help_storage.get_draft(uid)
    draft["html"] = extracted_html
    draft["blocks"] = extracted_blocks
    help_storage.save_draft(uid, draft)

    await message.reply(
        "✅ تم تحديث نص المسودة.",
        reply_markup=_builder_menu_keyboard(),
    )


@router.message(lambda m: bool(m.from_user) and m.from_user.id in help_awaiting_button)
async def on_help_button_input(message: Message):
    uid = message.from_user.id
    help_awaiting_button.discard(uid)

    raw = (message.text or "").strip()
    if "|" not in raw:
        help_awaiting_button.add(uid)
        await message.reply(
            "❌ الصيغة غلط. أرسل هكذا:\n"
            "<code>نص الزر | https://example.com</code>\n\n"
            "أو أرسل /cancel_edit للإلغاء."
        )
        return

    text_part, _, url_part = raw.partition("|")
    text_part = text_part.strip()
    url_part = url_part.strip()

    has_valid_url = url_part.startswith(("http://", "https://"))
    if not text_part or not has_valid_url:
        help_awaiting_button.add(uid)
        await message.reply(
            "❌ لازم نص الزر ما يكون فاضي، "
            "والرابط يبدأ بـ http:// أو https://.\n"
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
