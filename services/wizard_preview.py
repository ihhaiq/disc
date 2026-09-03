import asyncio
import logging
from collections.abc import Callable

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.types import FSInputFile, Message

import config
import keyboard as keyboards
import texts as texts_module
from compose import build_disc
from processor import render_preview
from services.localization import tr
from services.vinyl_settings import VinylSettings

logger = logging.getLogger(__name__)


class WizardPreviewService:
    def __init__(
        self,
        *,
        vinyl_settings: VinylSettings,
        download_with_retries: Callable,
        temp_path: Callable[[str], str],
        cleanup: Callable[..., None],
    ):
        self.vinyl_settings = vinyl_settings
        self.download_with_retries = download_with_retries
        self.temp_path = temp_path
        self.cleanup = cleanup

    async def run(self, bot: Bot, target_message: Message, uid: int, job: dict) -> None:
        audio = job["audio"]
        job_id = job["job_id"]
        ext = audio.file_name.split(".")[-1] if audio.file_name else "mp3"
        audio_path = self.temp_path(f"preview_{uid}_{job_id}_audio.{ext}")
        thumb_path = self.temp_path(f"preview_{uid}_{job_id}_thumb.jpg")
        disc_path = self.temp_path(f"preview_{uid}_{job_id}_disc.png")
        out_path = self.temp_path(f"preview_{uid}_{job_id}_out.mp4")

        try:
            await bot.send_chat_action(target_message.chat.id, action=ChatAction.UPLOAD_VIDEO)
            await self.download_with_retries(
                bot, audio.file_id, audio_path, timeout_seconds=180, retries=2
            )

            thumbnail_file_id = job.get("thumbnail_file_id")
            if not thumbnail_file_id and getattr(audio, "thumbnail", None) is not None:
                thumbnail_file_id = audio.thumbnail.file_id
            if not thumbnail_file_id:
                await target_message.reply(texts_module.ERR_NO_THUMBNAIL_AVAILABLE)
                return
            await self.download_with_retries(
                bot, thumbnail_file_id, thumb_path, timeout_seconds=60, retries=2
            )

            vinyl_choice = job.get("vinyl_choice")
            await asyncio.to_thread(
                build_disc,
                thumb_path,
                self.vinyl_settings.get_vinyl_path(uid, vinyl_choice),
                disc_path,
                self.vinyl_settings.get_hole_ratio(vinyl_choice),
                config.DISC_SIZE,
            )
            await render_preview(
                disc_path,
                self.vinyl_settings.get_shadow_path(uid, vinyl_choice),
                audio_path,
                out_path,
                rotation_seconds=job.get(
                    "rotation_seconds", self.vinyl_settings.get_rotation_seconds(uid)
                ),
                native_size=config.DISC_SIZE,
                start_offset=job.get("segment_start", 0.0),
            )

            await target_message.reply_video(
                FSInputFile(out_path),
                caption=tr("MSG_PREVIEW_READY_CAPTION", uid),
                reply_markup=keyboards.build_wiz_confirm_keyboard(uid),
            )
        except Exception:
            logger.exception("فشل توليد المعاينة السريعة")
            try:
                await target_message.reply(
                    tr("MSG_PROCESSING_ERROR_FMT", uid).format(error_text="preview failed")
                )
            except Exception:
                pass
        finally:
            self.cleanup(audio_path, thumb_path, disc_path, out_path)
