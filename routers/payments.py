"""Telegram Stars subscription handlers."""

import logging
import time
from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

import config
import limits
import texts as texts_module
from services.localization import tr
from services.payments import build_subscription_payload, validate_subscription_payment

logger = logging.getLogger(__name__)

ReplyTextVariable = Callable[..., Awaitable[Message]]


def create_payment_router(reply_text_variable: ReplyTextVariable) -> Router:
    """Build the payment router while preserving rich custom-text delivery."""
    router = Router(name=__name__)

    @router.callback_query(F.data == "buy_stars")
    async def on_buy_stars(callback, bot: Bot):
        uid = callback.from_user.id if callback.from_user else 0
        await bot.send_invoice(
            chat_id=callback.message.chat.id,
            title=texts_module.MSG_INVOICE_TITLE,
            description=texts_module.MSG_INVOICE_DESCRIPTION_FMT.format(
                limit=config.PREMIUM_DAILY_LIMIT
            ),
            payload=build_subscription_payload(uid, int(time.time())),
            provider_token="",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label=texts_module.MSG_INVOICE_LABEL,
                    amount=config.STARS_SUBSCRIPTION_PRICE,
                )
            ],
        )
        await callback.answer()

    @router.pre_checkout_query()
    async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
        check = validate_subscription_payment(
            payload=pre_checkout_query.invoice_payload,
            currency=pre_checkout_query.currency,
            amount=pre_checkout_query.total_amount,
            user_id=pre_checkout_query.from_user.id,
            expected_amount=config.STARS_SUBSCRIPTION_PRICE,
        )
        if check.valid:
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
            return
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message=tr("MSG_PAYMENT_INVALID", pre_checkout_query.from_user.id),
        )

    @router.message(F.successful_payment, F.chat.type == "private")
    async def on_successful_payment(message: Message, bot: Bot):
        uid = message.from_user.id if message.from_user else 0
        payment = message.successful_payment
        check = validate_subscription_payment(
            payload=payment.invoice_payload,
            currency=payment.currency,
            amount=payment.total_amount,
            user_id=uid,
            expected_amount=config.STARS_SUBSCRIPTION_PRICE,
        )
        if not check.valid:
            logger.warning("رفض دفعة غير مطابقة للمستخدم %s: %s", uid, check.reason)
            await reply_text_variable(message, bot, "MSG_PAYMENT_INVALID", uid)
            return

        limits.activate_subscription(uid, config.STARS_SUBSCRIPTION_DAYS)
        logger.info(texts_module.LOG_PAYMENT_RECORDED, uid)
        await reply_text_variable(
            message,
            bot,
            "MSG_PAYMENT_SUCCESS_FMT",
            uid,
            limit=config.PREMIUM_DAILY_LIMIT,
        )

        if not config.DEVELOPER_ID:
            return
        user = message.from_user
        try:
            await bot.send_message(
                config.DEVELOPER_ID,
                texts_module.MSG_NEW_SUBSCRIBER_ADMIN_FMT.format(
                    full_name=user.full_name if user else "-",
                    username=f"@{user.username}" if user and user.username else "-",
                    user_id=uid,
                    amount=payment.total_amount,
                    days=config.STARS_SUBSCRIPTION_DAYS,
                    limit=config.PREMIUM_DAILY_LIMIT,
                ),
            )
        except Exception:
            logger.exception("فشل إرسال إشعار المشترك الجديد للمطور")

    return router
