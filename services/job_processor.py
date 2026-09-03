import asyncio
import logging
import os
import time
from collections.abc import Callable

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputRichMessage, Message

import config
import keyboard as keyboards
import limits
import texts as texts_module
from compose import build_disc
from processor import get_duration, render_vinyl
from rich_content import escape_rich_html
from services.contexts import is_channel_context, is_group_context, is_shared_context
from services.ephemeral import EphemeralMessenger, EphemeralStatusAnimator
from services.localization import tr
from services.messaging import reply_text_variable, reply_with_premium_emoji, send_rich_message
from services.vinyl_settings import VinylSettings

logger = logging.getLogger(__name__)
STATUS_UPDATE_INTERVAL_SECONDS = 2.2
JOB_TIMEOUT_SECONDS = 8 * 60
JOB_TIMEOUT_MAX_SECONDS = 30 * 60
JOB_TIMEOUT_SECONDS_PER_MB = 3.0
STATUS_EMOJI_ID = "5463010113440717314"
STATUS_EMOJI_CHAR = "👀"
HEADER_EMOJI_ID = "5431578344472746087"
HEADER_EMOJI_CHAR = "🤩"
RICH_STATUS_HEADER_TEXT = "جاري المعالجة"


def compute_job_timeout_seconds(audio_file_size_bytes: int | None) -> float:
    if not audio_file_size_bytes or audio_file_size_bytes <= 0:
        return JOB_TIMEOUT_SECONDS
    size_mb = audio_file_size_bytes / (1024 * 1024)
    dynamic = JOB_TIMEOUT_SECONDS + size_mb * JOB_TIMEOUT_SECONDS_PER_MB
    return min(max(dynamic, JOB_TIMEOUT_SECONDS), JOB_TIMEOUT_MAX_SECONDS)


def release_job_usage(job: dict) -> None:
    reserved_uid = job.pop("usage_reserved_for", None)
    if isinstance(reserved_uid, int):
        limits.release_reserved_usage(reserved_uid)


def _format_eta_seconds(seconds: float) -> str:
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
    header_emoji_html = (
        f'<tg-emoji emoji-id="{HEADER_EMOJI_ID}">{HEADER_EMOJI_CHAR}</tg-emoji>'
    )
    header = f"{header_emoji_html} {escape_rich_html(RICH_STATUS_HEADER_TEXT)}"
    stage_icons = stage_icons or [STATUS_EMOJI_CHAR]
    emoji_html = f'<tg-emoji emoji-id="{STATUS_EMOJI_ID}">{STATUS_EMOJI_CHAR}</tg-emoji>'
    percent = 0.0 if percent is None else max(0.0, min(100.0, percent))

    row_parts = [f"<mark>{emoji_html}</mark>" for _ in stage_icons[:-1]]
    row_parts.append(f"<mark>{emoji_html}</mark> {int(percent)}%")
    icons_row = " ".join(row_parts)

    eta_row = ""
    if eta_seconds is not None and 0 < percent < 100:
        eta_row = (
            '<tr><td align="left" valign="middle">⏳ '
            f"{escape_rich_html(_format_eta_seconds(eta_seconds))}</td></tr>"
        )

    return (
        f"<p>{escape_rich_html(intro_text)}</p>"
        f'<table bordered striped><tr><th align="center" valign="middle">{header}</th></tr>'
        f'<tr><td align="left" valign="middle">{icons_row}</td></tr>'
        f"{eta_row}</table>"
    )


class StatusAnimator:
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
        return render_rich_status_html(
            self.percent,
            tr("MSG_RICH_STATUS_INTRO", self.user_id),
            self.stage_icons,
            eta_seconds=self.eta_seconds,
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
                    "rich_message غير مدعوم بهالنسخة من aiogram، الرجوع لتحديث نصي عادي"
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


class JobProcessor:
    def __init__(
        self,
        *,
        ephemeral: EphemeralMessenger,
        vinyl_settings: VinylSettings,
        channel_reply_index: dict[tuple[int, int], str],
        temp_path: Callable[[str], str],
        cleanup: Callable[..., None],
        download_with_retries: Callable,
        notify_missing_channel_permission: Callable,
    ):
        self.ephemeral = ephemeral
        self.vinyl_settings = vinyl_settings
        self.channel_reply_index = channel_reply_index
        self.temp_path = temp_path
        self.cleanup = cleanup
        self.download_with_retries = download_with_retries
        self.notify_missing_channel_permission = notify_missing_channel_permission

    async def process(self, bot: Bot, job: dict) -> None:
        message = job["message"]
        audio = job["audio"]
        uid = job["uid"]
        context_key = job.get("context_key", uid)
        job_id = job["job_id"]

        audio_path = self.temp_path(
            f"{uid}_{job_id}_audio.{audio.file_name.split('.')[-1] if audio.file_name else 'mp3'}"
        )
        thumb_path = self.temp_path(f"{uid}_{job_id}_thumb.jpg")
        disc_path = self.temp_path(f"{uid}_{job_id}_disc.png")
        out_path = self.temp_path(f"{uid}_{job_id}_out.mp4")
        job["temp_paths"] = [audio_path, thumb_path, disc_path, out_path]

        if is_group_context(context_key):
            message_id = job.get("status_ephemeral_message_id")
            if message_id is None:
                status = await self.ephemeral.send_text(
                    bot,
                    message.chat.id,
                    uid,
                    tr("STAGE_PREPARING", uid),
                )
                message_id = status.ephemeral_message_id
                job["status_ephemeral_message_id"] = message_id
            animator = EphemeralStatusAnimator(bot, message.chat.id, uid, int(message_id))
        else:
            initial_html = render_rich_status_html(0.0, tr("MSG_RICH_STATUS_INTRO", uid))
            status = await send_rich_message(
                bot,
                message.chat.id,
                initial_html,
                reply_to_message_id=message.message_id,
            )
            animator = StatusAnimator(status, bot, uid)
        animator.start()

        duration_warning_msg: Message | None = None

        try:
            await bot.send_chat_action(message.chat.id, action=ChatAction.RECORD_VIDEO_NOTE)
            animator.set_stage(tr("STAGE_DOWNLOADING_AUDIO", uid))
            await self.download_with_retries(
                bot,
                audio.file_id,
                audio_path,
                timeout_seconds=300,
                retries=3,
            )

            thumbnail_file_id = job.get("thumbnail_file_id")
            if not thumbnail_file_id and getattr(audio, "thumbnail", None) is not None:
                thumbnail_file_id = audio.thumbnail.file_id
            if not thumbnail_file_id:
                raise ValueError(texts_module.ERR_NO_THUMBNAIL_AVAILABLE)

            animator.set_stage(tr("STAGE_DOWNLOADING_THUMBNAIL", uid))
            await self.download_with_retries(
                bot,
                thumbnail_file_id,
                thumb_path,
                timeout_seconds=60,
                retries=2,
            )

            duration = await get_duration(audio_path)
            if duration > config.MAX_DURATION_SECONDS and not job.get("segment_start"):
                if is_group_context(context_key):
                    animator.set_stage(
                        tr("MSG_DURATION_TOO_LONG_FMT", uid).format(duration=duration)
                    )
                else:
                    duration_warning_msg = await reply_with_premium_emoji(
                        message,
                        tr("MSG_DURATION_TOO_LONG_FMT", uid).format(duration=duration),
                    )

            await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
            animator.set_stage(tr("STAGE_BUILDING_DISC", uid))
            vinyl_choice = job.get("vinyl_choice")
            await asyncio.to_thread(
                build_disc,
                thumb_path,
                self.vinyl_settings.get_vinyl_path(uid, vinyl_choice),
                disc_path,
                self.vinyl_settings.get_hole_ratio(vinyl_choice),
                config.DISC_SIZE,
            )
            shadow_path = self.vinyl_settings.get_shadow_path(uid, vinyl_choice)

            animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=0)

            async def on_render_progress(percent: float) -> None:
                animator.set_stage(tr("STAGE_RENDERING_VIDEO", uid), percent=percent)

            await render_vinyl(
                disc_path,
                shadow_path,
                audio_path,
                out_path,
                rotation_seconds=job.get(
                    "rotation_seconds", self.vinyl_settings.get_rotation_seconds(uid)
                ),
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
            final_keyboard = (
                keyboards.build_channel_result_keyboard()
                if is_shared_context(context_key)
                else None
            )

            try:
                await message.reply_video_note(
                    FSInputFile(out_path),
                    length=config.DISC_SIZE,
                    reply_markup=final_keyboard,
                )
            except TelegramBadRequest as exc:
                if is_shared_context(context_key) and (
                    "rights" in str(exc).lower() or "administrator" in str(exc).lower()
                ):
                    place_label = "القناة" if is_channel_context(context_key) else "المجموعة"
                    await self.notify_missing_channel_permission(
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

            if is_shared_context(context_key):
                for msg_id in job.get("channel_msg_ids", []):
                    try:
                        await bot.delete_message(message.chat.id, msg_id)
                    except Exception:
                        pass
                for reply_key, mapped in list(self.channel_reply_index.items()):
                    if mapped == context_key:
                        self.channel_reply_index.pop(reply_key, None)
        except asyncio.CancelledError:
            logger.warning(texts_module.LOG_JOB_TIMEOUT)
            try:
                timeout_text = tr("MSG_PROCESSING_TIMEOUT_FMT", uid).format(
                    minutes=compute_job_timeout_seconds(getattr(audio, "file_size", None)) / 60
                )
                if is_group_context(context_key):
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
                if is_group_context(context_key):
                    animator.set_stage(
                        tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text=error_text)
                    )
                else:
                    await reply_text_variable(
                        message,
                        bot,
                        "MSG_PROCESSING_ERROR_FMT",
                        uid,
                        error_text=error_text,
                    )
            except Exception:
                logger.exception(texts_module.LOG_SEND_ERROR_FAILED)
        finally:
            release_job_usage(job)
            await animator.stop()
            self.cleanup(audio_path, thumb_path, disc_path, out_path)
            try:
                if is_group_context(context_key):
                    message_id = job.get("status_ephemeral_message_id")
                    if message_id is not None:
                        await self.ephemeral.delete_text(
                            bot,
                            message.chat.id,
                            uid,
                            int(message_id),
                        )
                else:
                    await status.delete()
            except Exception:
                pass
            if duration_warning_msg is not None:
                try:
                    await duration_warning_msg.delete()
                except Exception:
                    pass
