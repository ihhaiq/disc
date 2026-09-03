"""Developer controls for limits, whitelist, and editor entry points."""

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import limits
import texts as texts_module
from vinyl_catalog import VINYL_STYLES

router = Router(name=__name__)
awaiting_menu_image: set[int] = set()
awaiting_whitelist_add: set[int] = set()
VINYL_COLOR_CHOICES = [(style.key, style.text_key) for style in VINYL_STYLES]


def is_developer(user_id: int) -> bool:
    return bool(user_id) and user_id == config.DEVELOPER_ID


async def require_developer(callback) -> bool:
    if callback.from_user and is_developer(callback.from_user.id):
        return True
    await callback.answer(texts_module.MSG_DEV_ONLY_OPTION)
    return False


def build_dev_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts_module.BTN_VINYL_PINK, callback_data="vinyl:pink")],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_VINYL_DEFAULT, callback_data="vinyl:default"
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_VINYL_YELLOW, callback_data="vinyl:yellow"
                )
            ],
            [InlineKeyboardButton(text=texts_module.BTN_VINYL_BLUE, callback_data="vinyl:blue")],
            [InlineKeyboardButton(text=texts_module.BTN_VINYL_GREEN, callback_data="vinyl:green")],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_DEV_SET_MENU_IMAGE,
                    callback_data="vinyl_menu_image:set",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ تحرير النصوص (عربي)", callback_data="dev_text:page:ar:0"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Edit Texts (English)", callback_data="dev_text:page:en:0"
                )
            ],
            [InlineKeyboardButton(text="🛡️ القائمة البيضاء", callback_data="dev_whitelist:open")],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_DEV_LIMITS_MENU,
                    callback_data="dev_limits:open",
                )
            ],
        ]
    )


def build_whitelist_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"❌ إزالة {uid}", callback_data=f"dev_whitelist:remove:{uid}")]
        for uid in limits.list_whitelist()
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="➕ إضافة مستخدم", callback_data="dev_whitelist:add")],
            [InlineKeyboardButton(text=texts_module.BTN_BACK, callback_data="dev_whitelist:back")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def whitelist_text() -> str:
    ids = limits.list_whitelist()
    if not ids:
        return "🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\nلا يوجد أحد حاليًا."
    return "🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\n" + "\n".join(
        f"• {uid}" for uid in ids
    )


def build_dev_limits_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for value, text_var in VINYL_COLOR_CHOICES:
        color_label = getattr(texts_module, text_var, value)
        is_paid = limits.is_premium_color(value)
        suffix = (
            texts_module.BTN_DEV_LIMITS_PAID_SUFFIX
            if is_paid
            else texts_module.BTN_DEV_LIMITS_FREE_SUFFIX
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{color_label} — {suffix}",
                    callback_data=f"dev_limits:toggle:{value}",
                    style="danger" if is_paid else "primary",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=texts_module.BTN_BACK, callback_data="dev_limits:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "/dev", F.chat.type == "private")
async def on_dev(message: Message):
    if not message.from_user or not is_developer(message.from_user.id):
        return
    await message.reply(
        texts_module.MSG_DEV_CHOOSE_TEMPLATE
        + "\n\n🔍 <code>/search كلمة</code> — للبحث بأسماء المتغيرات ومحتواها\n"
        "✏️ <code>/edit VAR_NAME [ar|en]</code> — لتحرير متغيّر مباشرة بالاسم",
        reply_markup=build_dev_keyboard(),
    )


@router.callback_query(F.data == "dev_limits:open")
async def on_dev_limits_open(callback):
    if not await require_developer(callback):
        return
    await callback.message.edit_text(
        texts_module.MSG_DEV_LIMITS_HEADER,
        reply_markup=build_dev_limits_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dev_limits:toggle:"))
async def on_dev_limits_toggle(callback):
    if not await require_developer(callback):
        return
    value = callback.data.split(":", 2)[2]
    color_label = getattr(texts_module, dict(VINYL_COLOR_CHOICES).get(value, ""), value)
    now_paid = limits.toggle_premium_color(value)
    await callback.message.edit_text(
        texts_module.MSG_DEV_LIMITS_HEADER,
        reply_markup=build_dev_limits_keyboard(),
    )
    text_key = "MSG_DEV_LIMITS_TOGGLED_PAID_FMT" if now_paid else "MSG_DEV_LIMITS_TOGGLED_FREE_FMT"
    await callback.answer(getattr(texts_module, text_key).format(name=color_label))


@router.callback_query(F.data == "dev_limits:back")
@router.callback_query(F.data == "dev_whitelist:back")
async def on_dev_back(callback):
    if not await require_developer(callback):
        return
    await callback.message.edit_text(
        texts_module.MSG_DEV_CHOOSE_TEMPLATE,
        reply_markup=build_dev_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "dev_whitelist:open")
async def on_dev_whitelist_open(callback):
    if not await require_developer(callback):
        return
    await callback.message.edit_text(whitelist_text(), reply_markup=build_whitelist_keyboard())
    await callback.answer()


@router.callback_query(F.data == "dev_whitelist:add")
async def on_dev_whitelist_add(callback):
    if not await require_developer(callback):
        return
    awaiting_whitelist_add.add(callback.from_user.id)
    await callback.message.reply("أرسل آيدي المستخدم (رقم) أو حوّل لي أي رسالة منه مباشرة.")
    await callback.answer()


@router.callback_query(F.data.startswith("dev_whitelist:remove:"))
async def on_dev_whitelist_remove(callback):
    if not await require_developer(callback):
        return
    target_id = int(callback.data.split(":", 2)[2])
    limits.remove_whitelist(target_id)
    await callback.message.edit_text(whitelist_text(), reply_markup=build_whitelist_keyboard())
    await callback.answer("تمت الإزالة ✅")


@router.message(
    lambda message: bool(message.from_user) and message.from_user.id in awaiting_whitelist_add,
    F.chat.type == "private",
)
async def on_whitelist_target_input(message: Message):
    awaiting_whitelist_add.discard(message.from_user.id)
    target_id = None
    if message.forward_from:
        target_id = message.forward_from.id
    elif message.text and message.text.strip().lstrip("-").isdigit():
        target_id = int(message.text.strip())
    if target_id is None:
        await message.reply(
            "ما قدرت أفهم آيدي المستخدم. أرسل رقم آيدي صحيح، أو حوّل رسالة منه "
            "بشرط إعدادات الخصوصية تسمح بإظهار هويته."
        )
        return
    limits.add_whitelist(target_id)
    await message.reply(
        f"✅ تمت إضافة {target_id} للقائمة البيضاء.\n\n{whitelist_text()}",
        reply_markup=build_whitelist_keyboard(),
    )


@router.callback_query(F.data == "vinyl_menu_image:set")
async def on_dev_set_menu_image(callback):
    if not await require_developer(callback):
        return
    awaiting_menu_image.add(callback.from_user.id)
    await callback.message.reply(texts_module.MSG_DEV_SEND_MENU_IMAGE)
    await callback.answer()
