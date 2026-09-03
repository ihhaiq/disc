"""Private-chat entry point and unsupported-input feedback."""

from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, Message

ReplyTextVariable = Callable[..., Awaitable[Message]]
StartKeyboardBuilder = Callable[[int, str], InlineKeyboardMarkup]


def create_start_router(
    reply_text_variable: ReplyTextVariable,
    build_start_keyboard: StartKeyboardBuilder,
) -> Router:
    router = Router(name=__name__)

    @router.message(Command("start"), F.chat.type == "private")
    async def on_start(message: Message, bot: Bot):
        uid = message.from_user.id if message.from_user else 0
        me = await bot.get_me()
        await reply_text_variable(
            message,
            bot,
            "MSG_START_HELP",
            uid,
            reply_markup=build_start_keyboard(uid, me.username),
        )

    @router.message((F.video | F.voice | F.document), F.chat.type == "private")
    async def on_wrong_type(message: Message, bot: Bot):
        uid = message.from_user.id if message.from_user else 0
        await reply_text_variable(message, bot, "MSG_WRONG_TYPE", uid)

    return router
