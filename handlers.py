import asyncio
import logging
import os
import time
import uuid

from aiogram import Router, F, Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from compose import build_disc, build_album_cover
from processor import get_duration, render_vinyl, render_album
import config
from texts import (
    STAGE_PREPARING,
    STAGE_DOWNLOADING_AUDIO,
    STAGE_DOWNLOADING_THUMBNAIL,
    STAGE_BUILDING_DISC,
    STAGE_BUILDING_ALBUM,
    STAGE_RENDERING_VIDEO,
    STAGE_UPLOADING_VIDEO,
    LOG_PROGRESS_UPDATE_FAILED,
    LOG_DELETE_FAILED_FMT,
    LOG_DOWNLOAD_RETRY_FAILED_FMT,
    LOG_NO_DETAIL_MESSAGE,
    LOG_QUEUE_PROCESS_FAILED,
    LOG_PROCESS_JOB_FAILED,
    LOG_SEND_ERROR_FAILED,
    LOG_FILE_TOO_LARGE,
    ERR_NO_THUMBNAIL_AVAILABLE,
    ERR_OUTPUT_NOT_CREATED,
    MSG_AUDIO_RECEIVED,
    MSG_DURATION_TOO_LONG_FMT,
    MSG_PROCESSING_ERROR_FMT,
    MSG_DEV_CHOOSE_TEMPLATE,
    MSG_START_HELP,
    MSG_TEMPLATE_FILES_MISSING,
    MSG_NO_THUMBNAIL_PROMPT,
    MSG_JOB_QUEUED,
    MSG_QUEUE_CANCELED_EDIT,
    MSG_QUEUE_CANCELED_ANSWER,
    MSG_SEND_IMAGE_NOW,
    MSG_NO_PENDING_AUDIO,
    MSG_AUDIO_EXPIRED,
    MSG_IMAGE_RECEIVED,
    MSG_DEV_ONLY_OPTION,
    MSG_VINYL_CHOICE_SAVED_EDIT,
    MSG_VINYL_CHOICE_SAVED_ANSWER,
    MSG_SPEED_SAVED_ANSWER,
    MSG_WRONG_TYPE,
    MSG_STYLE_INTRO,
    MSG_STYLE_INTRO_NO_IMAGE_NOTE,
    MSG_STYLE_ALBUM_SAVED_EDIT,
    MSG_STYLE_ALBUM_SAVED_ANSWER,
    MSG_STYLE_CLASSIC_SAVED_EDIT,
    MSG_STYLE_CLASSIC_SAVED_ANSWER,
    MSG_DEV_SET_STYLE_IMAGE_PROMPT,
    MSG_STYLE_IMAGE_SAVED,
    BTN_ADD_IMAGE,
    BTN_CANCEL,
    BTN_VINYL_PINK,
    BTN_VINYL_DEFAULT,
    BTN_VINYL_YELLOW,
    BTN_VINYL_BLUE,
    BTN_STYLE_OTHER,
    BTN_STYLE_ALBUM,
    BTN_STYLE_CLASSIC,
    BTN_DEV_SET_STYLE_IMAGE,
    SPEED_LABEL_FULL,
    SPEED_LABEL_8RPM,
    SPEED_LABEL_33RPM,
    SPEED_LABEL_45RPM,
)

logger = logging.getLogger(__name__)
router = Router()

job_queue: asyncio.Queue[dict] = asyncio.Queue()
developer_job_queue: asyncio.Queue[dict] = asyncio.Queue()
worker_task: asyncio.Task | None = None
pending_images: dict[int, dict] = {}
pending_audio: dict[int, dict] = {}
user_rotation_seconds: dict[int, float | None] = {}
user_pending_jobs: dict[int, set[str]] = {}
tracked_jobs: dict[str, dict] = {}
canceled_job_ids: set[str] = set()
developer_vinyl_choice: dict[int, str] = {}
user_style_choice: dict[int, str] = {}  # "album" أو غير موجود = كلاسيكي
pending_dev_style_photo: set[int] = set()


HOURGLASS_FRAMES = ["⏳", "⌛"]
PROGRESS_BAR_WIDTH = 12
STATUS_UPDATE_INTERVAL_SECONDS = 2.2


def render_progress_bar(percent: float, width: int = PROGRESS_BAR_WIDTH) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100))
    return "▓" * filled + "░" * (width - filled)


class StatusAnimator:
    """يحدّث رسالة الحالة بالتليكرام بشكل دوري: ساعة رملية متحركة + نص/شريط تقدّم."""

    def __init__(self, message: Message):
        self.message = message
        self.stage_text = STAGE_PREPARING
        self.percent: float | None = None
        self._frame = 0
        self._last_rendered: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def set_stage(self, stage_text: str, percent: float | None = None) -> None:
        self.stage_text = stage_text
        self.percent = percent

    def _render(self) -> str:
        hourglass = HOURGLASS_FRAMES[self._frame % len(HOURGLASS_FRAMES)]
        if self.percent is not None:
            bar = render_progress_bar(self.percent)
            return f"{hourglass} {self.stage_text}\n{bar}  {int(self.percent)}%"
        dots = "." * ((self._frame % 3) + 1)
        return f"{hourglass} {self.stage_text}{dots}"

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            self._frame += 1
            text = self._render()
            if text != self._last_rendered:
                try:
                    await self.message.edit_text(text)
                    self._last_rendered = text
                except TelegramBadRequest:
                    pass
                except Exception:
                    logger.exception(LOG_PROGRESS_UPDATE_FAILED)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=STATUS_UPDATE_INTERVAL_SECONDS)
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


def tmp(name: str) -> str:
    path = os.path.join(config.TEMP_DIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def cleanup(*paths: str) -> None:
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError as e:
            logger.warning(LOG_DELETE_FAILED_FMT.format(p=p, e=e))


async def download_with_retries(bot: Bot, file_id: str, destination: str,
                                timeout_seconds: int, retries: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        if os.path.exists(destination):
            os.remove(destination)
        try:
            await bot.download(
                file_id,
                destination=destination,
                timeout=timeout_seconds,
                chunk_size=64 * 1024,
            )
            return
        except Exception as exc:
            last_error = exc
            logger.warning(
                LOG_DOWNLOAD_RETRY_FAILED_FMT,
                attempt, retries, type(exc).__name__, exc or LOG_NO_DETAIL_MESSAGE,
            )
            if attempt < retries:
                await asyncio.sleep(2)
            else:
                raise
    if last_error is not None:
        raise last_error


async def start_job_worker(bot: Bot) -> None:
    global worker_task
    if worker_task is not None and not worker_task.done():
        return

    async def _worker() -> None:
        while True:
            queue = None
            try:
                job = developer_job_queue.get_nowait()
                queue = developer_job_queue
            except asyncio.QueueEmpty:
                try:
                    job = job_queue.get_nowait()
                    queue = job_queue
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)
                    continue

            try:
                job_id = job.get("job_id")
                if job_id in canceled_job_ids:
                    canceled_job_ids.discard(job_id)
                    tracked_jobs.pop(job_id, None)
                    user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
                    continue

                tracked_jobs[job_id] = job
                await process_job(bot, job)
            except Exception:
                logger.exception(LOG_QUEUE_PROCESS_FAILED)
            finally:
                tracked_jobs.pop(job_id, None)
                user_pending_jobs.get(job.get("uid", 0), set()).discard(job_id)
                if queue is not None:
                    queue.task_done()

    worker_task = asyncio.create_task(_worker())


def get_user_rotation_seconds(user_id: int) -> float | None:
    return user_rotation_seconds.get(user_id, config.ROTATION_SECONDS)


def get_user_style(user_id: int) -> str:
    return user_style_choice.get(user_id, "classic")


def compute_album_layout(size: int) -> dict:
    cover_size = max(1, int(size * config.ALBUM_COVER_RATIO))
    cover_x = int(size * config.ALBUM_COVER_OFFSET_X_RATIO)
    cover_y = int(size * config.ALBUM_COVER_OFFSET_Y_RATIO)

    disc_size = max(1, int(size * config.ALBUM_DISC_RATIO))
    visible = disc_size * config.ALBUM_DISC_VISIBLE_RATIO
    disc_x = int(cover_x + cover_size - (disc_size - visible))
    disc_y = int(size * config.ALBUM_DISC_OFFSET_Y_RATIO)

    return {
        "cover_size": cover_size,
        "cover_x": cover_x,
        "cover_y": cover_y,
        "disc_size": disc_size,
        "disc_x": disc_x,
        "disc_y": disc_y,
    }


def get_developer_vinyl_path(user_id: int) -> str:
    if user_id == config.DEVELOPER_ID:
        choice = developer_vinyl_choice.get(user_id)
        if choice == "pink":
            return config.VINYL_PINK_PATH
        if choice == "yellow":
            return config.VINYL_YELLOW_PATH
        if choice == "blue":
            return config.VINYL_BLUE_PATH
    return config.VINYL_PATH
        


def get_developer_shadow_path(user_id: int) -> str:
    if user_id == config.DEVELOPER_ID:
        choice = developer_vinyl_choice.get(user_id)
        if choice == "pink":
            return config.SHADOW_PINK_PATH
        if choice == "yellow":
            return config.SHADOW_YELLOW_PATH
        if choice == "blue":
            return config.SHADOW_BLUE_PATH
    return config.SHADOW_PATH


def get_job_priority(user_id: int) -> int:
    return 0 if user_id and user_id == config.DEVELOPER_ID else 1


def enqueue_job(job: dict) -> None:
    if get_job_priority(job.get("uid", 0)) == 0:
        developer_job_queue.put_nowait(job)
    else:
        job_queue.put_nowait(job)


def cancel_user_jobs(user_id: int) -> None:
    pending_ids = user_pending_jobs.pop(user_id, set())
    for job_id in list(pending_ids):
        canceled_job_ids.add(job_id)
        job = tracked_jobs.pop(job_id, None)
        if job:
            cleanup(*job.get("temp_paths", []))


async def process_job(bot: Bot, job: dict) -> None:
    message = job["message"]
    audio = job["audio"]
    uid = job["uid"]
    job_id = job["job_id"]

    style = get_user_style(uid)

    audio_path = tmp(f"{uid}_{job_id}_audio.{audio.file_name.split('.')[-1] if audio.file_name else 'mp3'}")
    thumb_path = tmp(f"{uid}_{job_id}_thumb.jpg")
    disc_path = tmp(f"{uid}_{job_id}_disc.png")
    out_path = tmp(f"{uid}_{job_id}_out.mp4")
    job["temp_paths"] = [audio_path, thumb_path, disc_path, out_path]

    status = await message.reply(MSG_AUDIO_RECEIVED)
    animator = StatusAnimator(status)
    animator.start()

    try:
        await bot.send_chat_action(message.chat.id, action=ChatAction.RECORD_VIDEO_NOTE)
        animator.set_stage(STAGE_DOWNLOADING_AUDIO)
        await download_with_retries(bot, audio.file_id, audio_path, timeout_seconds=300, retries=3)

        thumbnail_file_id = None
        if getattr(audio, "thumbnail", None) is not None:
            thumbnail_file_id = audio.thumbnail.file_id
        elif job.get("thumbnail_file_id"):
            thumbnail_file_id = job["thumbnail_file_id"]

        if thumbnail_file_id:
            animator.set_stage(STAGE_DOWNLOADING_THUMBNAIL)
            await download_with_retries(bot, thumbnail_file_id, thumb_path, timeout_seconds=60, retries=2)
        else:
            raise ValueError(ERR_NO_THUMBNAIL_AVAILABLE)

        duration = await get_duration(audio_path)
        if duration > config.MAX_DURATION_SECONDS:
            await message.reply(MSG_DURATION_TOO_LONG_FMT.format(duration=duration))

        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)

        animator.set_stage(STAGE_RENDERING_VIDEO, percent=0)

        async def on_render_progress(percent: float) -> None:
            animator.set_stage(STAGE_RENDERING_VIDEO, percent=percent)

        if style == "album":
            animator.set_stage(STAGE_BUILDING_ALBUM)
            layout = compute_album_layout(config.DISC_SIZE)
            await asyncio.to_thread(
                build_album_cover, thumb_path, disc_path,
                layout["cover_size"], config.ALBUM_COVER_CORNER_RATIO,
            )
            animator.set_stage(STAGE_RENDERING_VIDEO, percent=0)
            await render_album(
                disc_path, get_developer_vinyl_path(uid), audio_path, out_path,
                rotation_seconds=get_user_rotation_seconds(uid),
                size=config.DISC_SIZE,
                disc_size=layout["disc_size"], disc_x=layout["disc_x"], disc_y=layout["disc_y"],
                cover_x=layout["cover_x"], cover_y=layout["cover_y"],
                fps=config.OUTPUT_FPS, max_duration=config.MAX_DURATION_SECONDS,
                on_progress=on_render_progress,
            )
        else:
            animator.set_stage(STAGE_BUILDING_DISC)
            await asyncio.to_thread(
                build_disc, thumb_path, get_developer_vinyl_path(uid), disc_path,
                config.HOLE_RATIO, config.DISC_SIZE,
            )
            animator.set_stage(STAGE_RENDERING_VIDEO, percent=0)
            await render_vinyl(
                disc_path, get_developer_shadow_path(uid), audio_path, out_path,
                rotation_seconds=get_user_rotation_seconds(uid),
                size=config.DISC_SIZE, fps=config.OUTPUT_FPS,
                max_duration=config.MAX_DURATION_SECONDS,
                on_progress=on_render_progress,
            )

        if not os.path.exists(out_path):
            raise FileNotFoundError(ERR_OUTPUT_NOT_CREATED)

        animator.set_stage(STAGE_UPLOADING_VIDEO, percent=100)
        await bot.send_chat_action(message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        await message.reply_video_note(FSInputFile(out_path), length=config.DISC_SIZE)
    except Exception as e:
        logger.exception(LOG_PROCESS_JOB_FAILED)
        error_text = str(e) or repr(e) or e.__class__.__name__
        try:
            await message.reply(MSG_PROCESSING_ERROR_FMT.format(error_text=error_text))
        except Exception:
            logger.exception(LOG_SEND_ERROR_FAILED)
    finally:
        await animator.stop()
        cleanup(audio_path, thumb_path, disc_path, out_path)
        try:
            await status.delete()
        except Exception:
            pass


def build_speed_keyboard(user_id: int) -> InlineKeyboardMarkup:
    current = get_user_rotation_seconds(user_id)
    labels = [
        (SPEED_LABEL_FULL, "full"),
        (SPEED_LABEL_8RPM, "8"),
        (SPEED_LABEL_33RPM, "33"),
        (SPEED_LABEL_45RPM, "45"),
    ]
    buttons = []
    for label, value in labels:
        if value == "full":
            selected = current in (None, 0)
        else:
            selected = current == (60 / float(value))
        mark = " ✅" if selected else ""
        buttons.append(InlineKeyboardButton(text=f"{label}{mark}", callback_data=f"speed:{value}"))

    style_mark = " ✅" if get_user_style(user_id) == "album" else ""
    style_row = [InlineKeyboardButton(text=f"{BTN_STYLE_OTHER}{style_mark}", callback_data="style_menu")]

    return InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:], style_row])


@router.message(F.text == "/dev")
async def on_dev(message: Message):
    if not message.from_user or message.from_user.id != config.DEVELOPER_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_VINYL_PINK, callback_data="vinyl:pink")],
        [InlineKeyboardButton(text=BTN_VINYL_DEFAULT, callback_data="vinyl:default")],
        [InlineKeyboardButton(text=BTN_VINYL_YELLOW, callback_data="vinyl:yellow")],
        [InlineKeyboardButton(text=BTN_VINYL_BLUE, callback_data="vinyl:blue")],
        [InlineKeyboardButton(text=BTN_DEV_SET_STYLE_IMAGE, callback_data="dev_set_style_image")],
    ])
    await message.reply(MSG_DEV_CHOOSE_TEMPLATE, reply_markup=keyboard)


@router.message(F.text.in_({"/start", "/help"}))
async def on_start(message: Message):
    await message.reply(
        MSG_START_HELP,
        reply_markup=build_speed_keyboard(message.from_user.id if message.from_user else 0),
    )


@router.message(F.audio)
async def on_audio(message: Message, bot: Bot):
    if not os.path.exists(config.VINYL_PATH) or not os.path.exists(config.SHADOW_PATH):
        await message.reply(MSG_TEMPLATE_FILES_MISSING)
        return

    audio = message.audio
    if not audio.thumbnail:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BTN_ADD_IMAGE, callback_data="add_image")],
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="cancel_queue")],
        ])
        await message.reply(
            MSG_NO_THUMBNAIL_PROMPT,
            reply_markup=keyboard,
        )
        pending_audio[message.from_user.id] = {
            "audio": audio,
            "message": message,
            "expires_at": time.time() + 300,
            "job_id": uuid.uuid4().hex,
            "uid": message.from_user.id if message.from_user else 0,
        }
        pending_images[message.from_user.id] = {"audio_message_id": message.message_id}
        return

    if audio.file_size and audio.file_size > config.MAX_TELEGRAM_AUDIO_SIZE_BYTES:
        logger.info(LOG_FILE_TOO_LARGE)

    uid = message.from_user.id if message.from_user else 0
    job_id = uuid.uuid4().hex

    await start_job_worker(bot)

    job = {
        "message": message,
        "audio": audio,
        "uid": uid,
        "job_id": job_id,
    }
    tracked_jobs[job_id] = job
    user_pending_jobs.setdefault(uid, set()).add(job_id)
    enqueue_job(job)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_CANCEL, callback_data="cancel_queue")]])
    await message.reply(
        MSG_JOB_QUEUED,
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "cancel_queue")
async def on_cancel_queue(callback, bot: Bot):
    cancel_user_jobs(callback.from_user.id if callback.from_user else 0)
    await callback.message.edit_text(MSG_QUEUE_CANCELED_EDIT)
    await callback.answer(MSG_QUEUE_CANCELED_ANSWER)


@router.callback_query(F.data == "add_image")
async def on_add_image(callback, bot: Bot):
    await callback.message.reply(MSG_SEND_IMAGE_NOW)
    pending_images[callback.from_user.id] = {"waiting_for_image": True}
    await callback.answer()


@router.message(F.photo)
async def on_photo_for_audio(message: Message, bot: Bot):
    uid = message.from_user.id if message.from_user else 0

    if uid == config.DEVELOPER_ID and uid in pending_dev_style_photo:
        pending_dev_style_photo.discard(uid)
        photo = message.photo[-1]
        os.makedirs(config.ASSETS_DIR, exist_ok=True)
        await download_with_retries(bot, photo.file_id, config.ALBUM_STYLE_IMAGE_PATH, timeout_seconds=60, retries=2)
        await message.reply(MSG_STYLE_IMAGE_SAVED)
        return

    pending = pending_images.get(message.from_user.id)
    if not pending:
        return

    if pending.get("waiting_for_image"):
        photo = message.photo[-1]
        pending_entry = pending_audio.get(message.from_user.id)
        if not pending_entry:
            await message.reply(MSG_NO_PENDING_AUDIO)
            return

        if time.time() > pending_entry["expires_at"]:
            pending_audio.pop(message.from_user.id, None)
            pending_images.pop(message.from_user.id, None)
            await message.reply(MSG_AUDIO_EXPIRED)
            return

        pending_images[message.from_user.id] = {"photo_file_id": photo.file_id, "audio_message_id": pending.get("audio_message_id")}

        audio = pending_entry["audio"]
        job = pending_entry
        job["thumbnail_file_id"] = photo.file_id
        job["message"] = pending_entry["message"]
        job["uid"] = message.from_user.id if message.from_user else 0
        job["job_id"] = pending_entry["job_id"]

        pending_audio.pop(message.from_user.id, None)
        pending_images.pop(message.from_user.id, None)

        await start_job_worker(bot)
        await message.reply(MSG_IMAGE_RECEIVED)
        enqueue_job(job)
        return


@router.callback_query(F.data.startswith("vinyl:"))
async def on_vinyl_choice(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    choice = callback.data.split(":", 1)[1]
    if choice in ("pink", "blue", "yellow"):
        developer_vinyl_choice[callback.from_user.id] = choice
    else:
        developer_vinyl_choice.pop(callback.from_user.id, None)
    await callback.message.edit_text(MSG_VINYL_CHOICE_SAVED_EDIT)
    await callback.answer(MSG_VINYL_CHOICE_SAVED_ANSWER)


@router.callback_query(F.data == "dev_set_style_image")
async def on_dev_set_style_image(callback, bot: Bot):
    if not callback.from_user or callback.from_user.id != config.DEVELOPER_ID:
        await callback.answer(MSG_DEV_ONLY_OPTION)
        return
    pending_dev_style_photo.add(callback.from_user.id)
    await callback.message.reply(MSG_DEV_SET_STYLE_IMAGE_PROMPT)
    await callback.answer()


@router.callback_query(F.data == "style_menu")
async def on_style_menu(callback, bot: Bot):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_STYLE_ALBUM, callback_data="style:album")],
        [InlineKeyboardButton(text=BTN_STYLE_CLASSIC, callback_data="style:classic")],
    ])
    if os.path.exists(config.ALBUM_STYLE_IMAGE_PATH):
        await callback.message.answer_photo(
            FSInputFile(config.ALBUM_STYLE_IMAGE_PATH),
            caption=MSG_STYLE_INTRO,
            reply_markup=keyboard,
        )
    else:
        await callback.message.answer(
            MSG_STYLE_INTRO + MSG_STYLE_INTRO_NO_IMAGE_NOTE,
            reply_markup=keyboard,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("style:"))
async def on_style_choice(callback, bot: Bot):
    choice = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    if choice == "album":
        user_style_choice[user_id] = "album"
        await callback.message.edit_caption(caption=MSG_STYLE_ALBUM_SAVED_EDIT) \
            if callback.message.photo else await callback.message.edit_text(MSG_STYLE_ALBUM_SAVED_EDIT)
        await callback.answer(MSG_STYLE_ALBUM_SAVED_ANSWER)
    else:
        user_style_choice.pop(user_id, None)
        await callback.message.edit_caption(caption=MSG_STYLE_CLASSIC_SAVED_EDIT) \
            if callback.message.photo else await callback.message.edit_text(MSG_STYLE_CLASSIC_SAVED_EDIT)
        await callback.answer(MSG_STYLE_CLASSIC_SAVED_ANSWER)


@router.callback_query(F.data.startswith("speed:"))
async def on_speed_selected(callback, bot: Bot):
    data = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    if data == "full":
        user_rotation_seconds[user_id] = 0.0
    else:
        user_rotation_seconds[user_id] = 60 / float(data)
    await callback.message.edit_reply_markup(reply_markup=build_speed_keyboard(user_id))
    await callback.answer(MSG_SPEED_SAVED_ANSWER)


@router.message(F.video | F.voice | F.document)
async def on_wrong_type(message: Message):
    await message.reply(MSG_WRONG_TYPE)
