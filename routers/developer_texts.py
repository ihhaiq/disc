"""Developer text search and rich-text editing."""

import html
import logging
import math
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import config
import custom_texts
import keyboard as keyboards
import texts as texts_module
from services.messaging import model_dump as _model_dump
from services.messaging import rich_text_fallback as _rich_text_fallback
from services.premium_emoji import extract_premium_emojis, validate_premium_emoji_syntax
from services.text_markup import process_text_markup

logger = logging.getLogger(__name__)
router = Router(name=__name__)
TEXTS_PER_PAGE = 5
dev_text_edit_page: dict[int, int] = {}
awaiting_text_value: dict[int, dict] = {}


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


def _text_list_keyboard(page: int, lang: str = "ar"):
    names = get_editable_text_names(lang)
    start = page * TEXTS_PER_PAGE
    page_names = names[start : start + TEXTS_PER_PAGE]
    return keyboards.build_dev_text_list_keyboard(
        page_names,
        page=page,
        lang=lang,
        has_previous=page > 0,
        has_next=start + TEXTS_PER_PAGE < len(names),
    )


def _text_list_header(page: int, lang: str = "ar") -> str:
    names = get_editable_text_names(lang)
    total = len(names)
    total_pages = max(1, math.ceil(total / TEXTS_PER_PAGE))
    lang_label = "English" if lang == "en" else "عربي"
    return f"✏️ تحرير النصوص ({lang_label}) — صفحة {page + 1}/{total_pages} ({total} متغيّر):"


def update_text_variable(
    var_name: str,
    new_value: str,
    editor_id: int = 0,
    editor_name: str = "",
    lang: str = "ar",
    rich_content: dict | None = None,
) -> None:
    processed_value = process_text_markup(new_value)

    if lang == "en":
        if var_name not in texts_module.TEXTS_EN:
            raise ValueError(f"المتغيّر {var_name} غير موجود بقاموس TEXTS_EN")
        custom_texts.set_custom(
            f"EN::{var_name}",
            processed_value,
            editor_id=editor_id,
            editor_name=editor_name,
            rich=rich_content,
        )
        texts_module.TEXTS_EN[var_name] = processed_value
        return

    if not hasattr(texts_module, var_name):
        raise ValueError(f"المتغيّر {var_name} غير موجود بملف texts.py")

    custom_texts.set_custom(
        var_name,
        processed_value,
        editor_id=editor_id,
        editor_name=editor_name,
        rich=rich_content,
    )
    setattr(texts_module, var_name, processed_value)


async def validate_html_text(bot: Bot, chat_id: int, text: str) -> str | None:
    try:
        test_msg = await bot.send_message(chat_id, text, disable_notification=True)
        await test_msg.delete()
        return None
    except TelegramBadRequest as exc:
        return str(exc)


@router.callback_query(F.data.startswith("dev_text:page:"))
async def on_dev_text_page(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
        return
    _, _, lang, page_str = callback.data.split(":", 3)
    page = int(page_str)
    dev_text_edit_page[callback.from_user.id] = page
    await callback.message.edit_text(
        _text_list_header(page, lang),
        reply_markup=_text_list_keyboard(page, lang),
    )
    await callback.answer()


async def send_text_edit_prompt(
    message: Message, uid: int, var_name: str, lang: str, current_value: str
) -> None:
    awaiting_text_value[uid] = {"var_name": var_name, "lang": lang}
    preview = current_value if len(current_value) <= 500 else current_value[:500] + "…"
    escaped_preview = html.escape(preview)
    lang_label = "English" if lang == "en" else "عربي"
    await message.reply(
        f"📝 القيمة الحالية لـ <code>{html.escape(var_name)}</code> ({lang_label}):\n\n"
        f"<code>{escaped_preview}</code>\n\n"
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
    await send_text_edit_prompt(
        callback.message, callback.from_user.id, var_name, lang, current_value
    )
    await callback.answer()


@router.message(Command("search"), F.chat.type == "private")
async def on_dev_search(message: Message, command: CommandObject):
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
    results: list[tuple[str, str, str]] = []
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

    max_results_shown = 15
    lines = [f"🔍 نتائج البحث عن <code>{html.escape(query)}</code> — {len(results)} نتيجة:\n"]
    for lang, name, value in results[:max_results_shown]:
        preview = value if len(value) <= 150 else value[:150] + "…"
        lang_label = "EN" if lang == "en" else "AR"
        lines.append(
            f"• <b>{html.escape(name)}</b> [{lang_label}]\n<code>{html.escape(preview)}</code>"
        )

    if len(results) > max_results_shown:
        lines.append(
            f"\n… و{len(results) - max_results_shown} نتيجة إضافية، دقق البحث أكثر."
        )
    lines.append(
        "\n✏️ للتعديل المباشر استخدم:\n"
        "<code>/edit VAR_NAME</code> (عربي افتراضيًا)\n"
        "<code>/edit VAR_NAME en</code> (إنكليزي)"
    )
    await message.reply("\n\n".join(lines))


@router.message(Command("edit"), F.chat.type == "private")
async def on_dev_edit_command(message: Message, command: CommandObject):
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
    await callback.message.edit_text(
        texts_module.MSG_DEV_CHOOSE_TEMPLATE,
        reply_markup=keyboards.build_dev_keyboard(),
    )
    await callback.answer()


@router.message(F.text == "/cancel_edit", F.chat.type == "private")
async def on_cancel_text_edit(message: Message):
    uid = message.from_user.id if message.from_user else 0
    if uid in awaiting_text_value:
        awaiting_text_value.pop(uid, None)
        await message.reply("❌ تم إلغاء التحرير.")


def normalize_dev_input(text: str) -> str:
    if not text:
        return text
    text = re.sub(
        r"!\[(.+?)\]\(tg://emoji\?id=(\d+)\)",
        r'<tg-emoji emoji-id="\2">\1</tg-emoji>',
        text,
    )
    text = re.sub(r"\\([\\_*\[\]()~`>#+\-=|{}.!])", r"\1", text)
    return re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)


async def _extract_dev_text_content(message: Message) -> tuple[str | None, dict | None]:
    rich = getattr(message, "rich_message", None)
    if rich is not None:
        rich_data = _model_dump(rich)
        if isinstance(rich_data, dict):
            blocks = rich_data.get("blocks")
            if blocks:
                fallback = _rich_text_fallback(blocks)
                return fallback, {
                    "blocks": blocks,
                    "is_rtl": rich_data.get("is_rtl"),
                }
            html_value = rich_data.get("html")
            if html_value:
                return html_value, {
                    "html": html_value,
                    "is_rtl": rich_data.get("is_rtl"),
                }

    html_text = getattr(message, "html_text", None)
    if html_text:
        return html_text, None
    text = message.text if message.text is not None else message.caption
    if text is not None:
        return text, None
    return None, None


@router.message(
    lambda m: (
        bool(m.from_user)
        and m.from_user.id == config.DEVELOPER_ID
        and m.from_user.id in awaiting_text_value
    ),
    F.chat.type == "private",
)
async def on_text_value_input(message: Message, bot: Bot):
    uid = message.from_user.id
    pending = awaiting_text_value.pop(uid)
    var_name = pending["var_name"]
    lang = pending["lang"]
    extracted_value, rich_content = await _extract_dev_text_content(message)

    if not extracted_value or not extracted_value.strip():
        awaiting_text_value[uid] = pending
        await message.reply(
            "❌ ما قدرت أستخرج محتوى صالح من الرسالة.\n\n"
            "أرسل نصًا عاديًا، أو أرسل رسالة من محرر Telegram الغني (Rich Message). "
            "وإذا كانت الرسالة الغنية تحتوي صورة أو وسائط، سأحفظها معها أيضًا.\n\n"
            "أو أرسل /cancel_edit للإلغاء."
        )
        return

    if rich_content:
        new_value = extracted_value
        emojis_found = {}
    else:
        new_value = normalize_dev_input(extracted_value)
        if not new_value.strip():
            awaiting_text_value[uid] = pending
            await message.reply(
                "❌ النص وصلني فاضي (أو صار فاضي بعد تنظيفه).\n\n"
                "أرسل نصًا عاديًا أو رسالة Rich من محرر Telegram."
            )
            return

        is_valid_emoji, emoji_error = validate_premium_emoji_syntax(new_value)
        if not is_valid_emoji:
            awaiting_text_value[uid] = pending
            await message.reply(
                "❌ خطأ في صيغة الإيموجي البريميوم:\n"
                f"<code>{html.escape(emoji_error)}</code>\n\n"
                "الصيغة الصحيحة:\n"
                "<code>&lt;tg-emoji emoji-id='123'&gt;🎶&lt;/tg-emoji&gt;</code>\n"
                "أو صيغة ماركداون تليكرام الرسمية:\n"
                "<code>![🎶](tg://emoji?id=123)</code>\n\n"
                "صحّح النص وأرسله مرة ثانية، أو أرسل /cancel_edit للإلغاء."
            )
            return

        html_error = await validate_html_text(bot, message.chat.id, new_value)
        if html_error:
            awaiting_text_value[uid] = pending
            await message.reply(
                "❌ النص فيه خطأ HTML ولن يُحفظ حتى يصير صحيحًا:\n"
                f"<code>{html.escape(html_error)}</code>\n\n"
                "صحّح النص وأرسله مرة ثانية، أو أرسل /cancel_edit للإلغاء."
            )
            return
        emojis_found = extract_premium_emojis(new_value)

    try:
        user = message.from_user
        editor_name = (user.first_name or user.username or f"User{uid}") if user else "Unknown"
        update_text_variable(
            var_name,
            new_value,
            editor_id=uid,
            editor_name=editor_name,
            lang=lang,
            rich_content=rich_content,
        )
    except Exception as exc:
        logger.exception("فشل حفظ النص المخصص")
        await message.reply(f"❌ فشل الحفظ:\n<code>{html.escape(str(exc))}</code>")
        return

    emoji_info = ""
    if emojis_found:
        emoji_list = "\n".join(
            f"  • {emoji} (ID: {emoji_id})" for emoji, emoji_id in emojis_found.items()
        )
        emoji_info = f"\n\n🎯 الإيموجي البريميوم المكتشفة تلقائياً:\n{emoji_list}"

    rich_info = ""
    if rich_content:
        blocks = rich_content.get("blocks") or []
        media_count = 0

        def count_media(obj):
            nonlocal media_count
            if isinstance(obj, dict):
                if obj.get("type") in {
                    "photo",
                    "video",
                    "animation",
                    "audio",
                    "voice_note",
                    "document",
                }:
                    media_count += 1
                for child in obj.values():
                    count_media(child)
            elif isinstance(obj, list):
                for child in obj:
                    count_media(child)

        count_media(blocks)
        rich_info = f"\n✨ النوع: <b>Rich Message</b>\n🧱 البلوكات: {len(blocks)}" + (
            f"\n🖼️ الوسائط داخلها: {media_count}" if media_count else ""
        )

    lang_label = "English" if lang == "en" else "عربي"
    success_msg = (
        f"✅ تم حفظ <code>{var_name}</code> ({lang_label}) بنجاح بشكل <b>دائم</b>! 🎉\n"
        "✨ التغيير مفعّل فوراً وسيبقى حتى بعد إعادة تشغيل البوت.\n"
        f"👤 محرّر: {html.escape(editor_name)} (ID: {uid})"
        f"{rich_info}"
        f"{emoji_info}"
    )
    await message.reply(success_msg, reply_markup=keyboards.build_dev_keyboard())
