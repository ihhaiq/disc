# -*- coding: utf-8 -*-
"""
أمر /help كرسالة غنية (Rich Message) قابلة للتخصيص من لوحة المطور.

سير العمل:
1) المطور يرسل /help  → تظهر مسودة الرسالة الحالية (نص "النص" افتراضيًا)
   مع زر "🎛 تخصيص".
2) ضغط "تخصيص" → قائمة "اختر من ادناه" فيها 3 أزرار:
   • "📝 نص الرسالة (Rich Msg)"  → يطلب من المطور يرسل نص/رسالة غنية جديدة
     (يدعم استقبال رسالة أُنشئت من محرر تليكرام للرسائل الغنية مباشرة —
     Bot API 10.2، تحديث 14 يوليو 2026 — وإلا نص/HTML عادي كبديل).
   • "➕ اضف زر"  → يطلب "نص الزر | الرابط" ليضيف زر URL على الرسالة.
   • "👁 معاينة"  → يرسل نسخة تجريبية مطابقة تمامًا لما سيراه المستخدمون.
   وفيها كمان "💾 حفظ ونشر" و"🔙 رجوع".
3) عادي المستخدمين اللي يرسلون /help ياخذون آخر نسخة "منشورة" فقط،
   ولو ما فيه نسخة منشورة بعد يرجعون لنص المساعدة الافتراضي (MSG_START_HELP).

ملاحظة عن استقبال الرسائل الغنية من محرر تليكرام:
Bot API (تحديث 14 يوليو 2026) عرّف بنية InputRichMessage.blocks للإرسال، وأي
رسالة يبنيها المستخدم بمحرر تليكرام الغني وترسل للبوت تصل كرسالة فيها حقل
غني (rich content) بدل نص/HTML عادي. حتى نتعامل مع أي شكل توصل فيه aiogram
(rich_message ككائن، أو html جاهز، أو نص خام)، نحاول أكثر من مسار قراءة بالتتابع
وننزل لأبسط بديل متوفر بدل ما نطيح بخطأ.
"""
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


async def _extract_rich_html(message: Message) -> str | None:
    """
    يحاول يستخرج محتوى غني (HTML) من رسالة وصلت من المطور، بترتيب أولوية:
    1) message.rich_message.html — لو aiogram/Bot API عرضوا الرسالة كـ Rich
       Message جاهزة (هذا الشكل المتوقع لرسالة أُنشئت بمحرر تليكرام الغني).
    2) message.rich_message.blocks — نص تقريبي مبني من البلوكات لو ما فيه html
       جاهز (fallback بسيط: دمج نص كل بلوك).
    3) message.html_text (من aiogram) — تحويل تنسيقات تليكرام العادية (بولد/
       مائل/روابط...) إلى HTML.
    4) message.text/caption كنص خام.
    يرجّع None لو ما فيه أي محتوى نصي بالمرة.
    """
    rich = getattr(message, "rich_message", None)
    if rich is not None:
        html_val = getattr(rich, "html", None)
        if html_val:
            return html_val
        blocks = getattr(rich, "blocks", None)
        if blocks:
            parts = []
            for block in blocks:
                text_val = getattr(block, "text", None) or getattr(block, "html", None)
                if text_val:
                    parts.append(text_val)
            if parts:
                return "".join(parts)
            logger.warning("وصلت رسالة غنية (rich_message.blocks) بدون نص قابل للاستخراج تلقائيًا")

    html_text = getattr(message, "html_text", None)
    if html_text:
        return html_text

    if message.text:
        return escape_rich_html(message.text)
    if message.caption:
        return escape_rich_html(message.caption)

    return None


@router.message(Command("help"))
async def on_help(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0

    if not _is_dev(uid):
        published = help_storage.get_published()
        if published:
            await send_rich_message(
                bot, message.chat.id, published["html"],
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
        bot, message.chat.id, draft["html"],
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
        bot, callback.message.chat.id, draft["html"],
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
        bot, callback.message.chat.id, draft["html"],
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

    extracted = await _extract_rich_html(message)
    if not extracted:
        help_awaiting_text.add(uid)
        await message.reply(
            "❌ ما قدرت أستخرج أي نص من الرسالة اللي وصلتني. جرب ترسلها كنص "
            "عادي، أو أرسل /cancel_edit للإلغاء."
        )
        return

    draft = help_storage.get_draft(uid)
    draft["html"] = extracted
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
