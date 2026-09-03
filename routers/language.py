"""User-language callback handlers."""

from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from services.localization import get_user_lang, user_language

EditTextVariable = Callable[..., Awaitable[Message]]
KeyboardBuilder = Callable[[int], InlineKeyboardMarkup]
StartKeyboardBuilder = Callable[[int, str], InlineKeyboardMarkup]


def create_language_router(
    edit_text_variable: EditTextVariable,
    build_vinyl_color_keyboard: KeyboardBuilder,
    build_customize_keyboard: KeyboardBuilder,
    build_start_keyboard: StartKeyboardBuilder,
) -> Router:
    router = Router(name=__name__)

    @router.callback_query(F.data == "lang:toggle")
    async def on_lang_toggle(callback: CallbackQuery, bot: Bot):
        user_id = callback.from_user.id if callback.from_user else 0
        new_lang = "en" if get_user_lang(user_id) == "ar" else "ar"
        user_language[user_id] = new_lang

        current_markup = callback.message.reply_markup
        is_color_menu = bool(
            current_markup
            and any(
                button.callback_data and button.callback_data.startswith("vinyl:")
                for row in current_markup.inline_keyboard
                for button in row
            )
        )
        is_customize_menu = bool(
            current_markup
            and any(
                button.callback_data
                and (
                    button.callback_data.startswith("speed:")
                    or button.callback_data == "vinyl_menu:open"
                )
                for row in current_markup.inline_keyboard
                for button in row
            )
        )
        try:
            if is_color_menu:
                await edit_text_variable(
                    callback.message,
                    bot,
                    "MSG_VINYL_COLOR_INFO",
                    user_id,
                    reply_markup=build_vinyl_color_keyboard(user_id),
                )
            elif is_customize_menu:
                text = (
                    "⚙️ تخصيص إعدادات القرص:"
                    if new_lang == "ar"
                    else "⚙️ Customize your disc settings:"
                )
                await callback.message.edit_text(
                    text,
                    reply_markup=build_customize_keyboard(user_id),
                )
            else:
                me = await bot.get_me()
                await edit_text_variable(
                    callback.message,
                    bot,
                    "MSG_START_HELP",
                    user_id,
                    reply_markup=build_start_keyboard(user_id, me.username),
                )
        except TelegramBadRequest:
            pass
        await callback.answer("✅ EN" if new_lang == "en" else "✅ AR")

    return router
