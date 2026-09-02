import asyncio
from contextlib import suppress
import json
import os
from typing import Awaitable, Callable

ProgressCallback = Callable[[float], Awaitable[None]]

TELEGRAM_VIDEO_NOTE_MAX_BYTES = 12_582_912
SIZE_SAFETY_MARGIN = 0.92
MIN_VIDEO_BITRATE_BPS = 250_000
MIN_AUDIO_BITRATE_BPS = 64_000
MAX_AUDIO_BITRATE_BPS = 128_000


def _parse_ffmpeg_timestamp(value: str) -> float:
    try:
        hours, minutes, seconds = value.strip().split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, AttributeError):
        return 0.0


async def get_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {err.decode()[-300:]}")
    return float(json.loads(out)["format"]["duration"])


def compute_bitrate_budget(duration: float) -> tuple[int, int]:
    """Keep the combined streams below Telegram's video-note size limit."""
    duration = max(duration, 1.0)
    target_total_bits = TELEGRAM_VIDEO_NOTE_MAX_BYTES * 8 * SIZE_SAFETY_MARGIN
    target_total_bps = target_total_bits / duration

    audio_bps = min(
        MAX_AUDIO_BITRATE_BPS,
        max(MIN_AUDIO_BITRATE_BPS, int(target_total_bps * 0.15)),
    )
    video_bps = int(target_total_bps - audio_bps)

    if video_bps < MIN_VIDEO_BITRATE_BPS:
        video_bps = MIN_VIDEO_BITRATE_BPS
        audio_bps = MIN_AUDIO_BITRATE_BPS

    return video_bps, audio_bps


def _rotation_period(rotation_seconds: float | None, duration: float) -> float:
    if rotation_seconds is not None and rotation_seconds > 0:
        return rotation_seconds
    return duration if duration > 0 else 4


async def _trim_audio(
    audio_path: str,
    output_path: str,
    start_offset: float,
    duration: float,
    operation: str,
) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_offset),
        "-i", audio_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-t", str(duration),
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, error = await proc.communicate()
    if proc.returncode != 0:
        detail = error.decode(errors="replace")[-500:]
        raise RuntimeError(f"ffmpeg {operation} failed: {detail}")


def _remove_file(path: str) -> None:
    with suppress(OSError):
        os.remove(path)


async def render_preview(
    disc_path: str,
    shadow_path: str,
    audio_path: str,
    out_path: str,
    rotation_seconds: float | None = 4,
    native_size: int = 640,
    output_size: int = 320,
    fps: int = 15,
    preview_duration: float = 3.0,
    start_offset: float = 0.0,
) -> str:
    """Render a short, low-resolution preview."""
    full_duration = await get_duration(audio_path)
    start_offset = max(0.0, min(start_offset, max(0.0, full_duration - 1)))
    remaining = max(0.0, full_duration - start_offset)
    duration = min(remaining, preview_duration) if remaining > 0 else preview_duration
    duration = max(duration, 1.0)

    rotation_seconds = _rotation_period(rotation_seconds, duration)

    trimmed_audio_path = audio_path + ".preview.mp3"
    await _trim_audio(
        audio_path, trimmed_audio_path, start_offset, duration, "preview trim"
    )

    filt = (
        "[1:v]format=rgba,"
        f"rotate=2*PI*t/{rotation_seconds}:c=none:ow={native_size}:oh={native_size}"
        "[spin];"
        f"[spin][2:v]overlay=0:0:format=auto[merged];"
        f"[merged]scale={output_size}:{output_size}[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", trimmed_audio_path,
        "-loop", "1", "-i", disc_path,
        "-loop", "1", "-i", shadow_path,
        "-filter_complex", filt,
        "-map", "[vout]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-b:v", "400k",
        "-c:a", "aac", "-b:a", "64k",
        "-t", str(duration),
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        out_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            detail = err.decode(errors="replace")[-500:]
            raise RuntimeError(f"ffmpeg preview render failed: {detail}")
    finally:
        _remove_file(trimmed_audio_path)

    return out_path


async def render_vinyl(
    disc_path: str,
    shadow_path: str,
    audio_path: str,
    out_path: str,
    rotation_seconds: float | None = 4,
    size: int = 640,
    fps: int = 30,
    max_duration: float = 60.0,
    start_offset: float = 0.0,
    on_progress: ProgressCallback | None = None,
) -> str:
    full_duration = await get_duration(audio_path)
    start_offset = max(0.0, min(start_offset, max(0.0, full_duration - 1)))
    remaining = max(0.0, full_duration - start_offset)
    duration = min(remaining, max_duration)

    rotation_seconds = _rotation_period(rotation_seconds, duration)

    video_bps, audio_bps = compute_bitrate_budget(duration)

    trimmed_audio_path = audio_path + ".trim.mp3"
    await _trim_audio(audio_path, trimmed_audio_path, start_offset, duration, "trim")

    filt = (
        f"[1:v]format=rgba,"
        f"rotate=2*PI*t/{rotation_seconds}:c=none:ow={size}:oh={size}[spin];"
        f"[spin][2:v]overlay=0:0:format=auto[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", trimmed_audio_path,
        "-loop", "1", "-i", disc_path,
        "-loop", "1", "-i", shadow_path,
        "-filter_complex", filt,
        "-map", "[vout]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", str(video_bps), "-maxrate", str(int(video_bps * 1.15)),
        "-bufsize", str(video_bps * 2),
        "-c:a", "aac", "-b:a", str(audio_bps),
        "-t", str(duration),
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-color_range", "tv",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        out_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stderr_chunks: list[bytes] = []

        async def _drain_stderr() -> None:
            assert proc.stderr is not None
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        async def _read_progress() -> None:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="ignore").strip()
                if not on_progress:
                    continue
                if text.startswith("out_time="):
                    elapsed = _parse_ffmpeg_timestamp(text.split("=", 1)[1])
                    if duration > 0:
                        percent = max(0.0, min(99.0, (elapsed / duration) * 100))
                        with suppress(Exception):
                            await on_progress(percent)
                elif text == "progress=end":
                    with suppress(Exception):
                        await on_progress(100.0)

        await asyncio.gather(_drain_stderr(), _read_progress())
        returncode = await proc.wait()
        if returncode != 0:
            detail = b"".join(stderr_chunks).decode(errors="ignore")[-500:]
            raise RuntimeError(f"ffmpeg failed: {detail}")
    finally:
        _remove_file(trimmed_audio_path)

    actual_size = os.path.getsize(out_path)
    if actual_size > TELEGRAM_VIDEO_NOTE_MAX_BYTES:
        raise RuntimeError(
            f"حجم الفيديو الناتج ({actual_size} بايت) أكبر من حد تليكرام "
            f"({TELEGRAM_VIDEO_NOTE_MAX_BYTES} بايت) رغم ضبط البترّيت."
        )

    return out_path
