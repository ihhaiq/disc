import asyncio
import json
import os
from typing import Awaitable, Callable

ProgressCallback = Callable[[float], Awaitable[None]]

# حد تليكرام الرسمي لحجم فيديو النوت الدائري (12 ميجابايت بالضبط)
TELEGRAM_VIDEO_NOTE_MAX_BYTES = 12_582_912
# هامش أمان حتى ما نلامس الحد بالضبط (تفاوت بسيط بالحاويات/الرؤوس)
SIZE_SAFETY_MARGIN = 0.92
MIN_VIDEO_BITRATE_BPS = 250_000
MIN_AUDIO_BITRATE_BPS = 64_000
MAX_AUDIO_BITRATE_BPS = 128_000


def _parse_ffmpeg_timestamp(value: str) -> float:
    """يحول نص وقت ffmpeg مثل '00:00:04.500000' إلى ثواني."""
    try:
        hours, minutes, seconds = value.strip().split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, AttributeError):
        return 0.0


async def get_duration(path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "json", path]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {err.decode()[-300:]}")
    return float(json.loads(out)["format"]["duration"])


def compute_bitrate_budget(duration: float) -> tuple[int, int]:
    """يحسب بترّيت الفيديو والصوت (bps) بحيث الحجم الناتج يبقى تحت حد تليكرام."""
    duration = max(duration, 1.0)
    target_total_bits = TELEGRAM_VIDEO_NOTE_MAX_BYTES * 8 * SIZE_SAFETY_MARGIN
    target_total_bps = target_total_bits / duration

    audio_bps = min(MAX_AUDIO_BITRATE_BPS, max(MIN_AUDIO_BITRATE_BPS, int(target_total_bps * 0.15)))
    video_bps = int(target_total_bps - audio_bps)

    if video_bps < MIN_VIDEO_BITRATE_BPS:
        video_bps = MIN_VIDEO_BITRATE_BPS
        audio_bps = MIN_AUDIO_BITRATE_BPS

    return video_bps, audio_bps


async def render_vinyl(disc_path: str, shadow_path: str, audio_path: str,
                        out_path: str, rotation_seconds: float | None = 4,
                        size: int = 640, fps: int = 30,
                        max_duration: float = 60.0,
                        start_offset: float = 0.0,
                        on_progress: ProgressCallback | None = None) -> str:
    full_duration = await get_duration(audio_path)
    # نتأكد أن نقطة البداية المختارة ضمن حدود الملف الفعلية
    start_offset = max(0.0, min(start_offset, max(0.0, full_duration - 1)))
    remaining = max(0.0, full_duration - start_offset)
    duration = min(remaining, max_duration)  # حد تليكرام لفيديو نوت الدائري

    if rotation_seconds is None or rotation_seconds <= 0:
        rotation_seconds = duration if duration > 0 else 4

    video_bps, audio_bps = compute_bitrate_budget(duration)

    trimmed_audio_path = audio_path + ".trim.mp3"
    trim_cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_offset),
        "-i", audio_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-t", str(duration),
        trimmed_audio_path,
    ]
    trim_proc = await asyncio.create_subprocess_exec(
        *trim_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, trim_err = await trim_proc.communicate()
    if trim_proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed: {trim_err.decode()[-500:]}")

    filt = (
        f"[1:v]format=rgba,rotate=2*PI*t/{rotation_seconds}:c=none:ow={size}:oh={size}[spin];"
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
                        try:
                            await on_progress(percent)
                        except Exception:
                            pass
                elif text == "progress=end":
                    try:
                        await on_progress(100.0)
                    except Exception:
                        pass

        await asyncio.gather(_drain_stderr(), _read_progress())
        returncode = await proc.wait()
        if returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {b''.join(stderr_chunks).decode(errors='ignore')[-500:]}")
    finally:
        # ملف الصوت المقتوص وسيط داخلي فقط، احذفه دايمًا سواء نجحت المعالجة أو فشلت
        if os.path.exists(trimmed_audio_path):
            try:
                os.remove(trimmed_audio_path)
            except OSError:
                pass

    # حماية إضافية: لو الحجم النهائي طلع أكبر من حد تليكرام رغم كل شي (نادر)، نرفع خطأ واضح
    actual_size = os.path.getsize(out_path)
    if actual_size > TELEGRAM_VIDEO_NOTE_MAX_BYTES:
        raise RuntimeError(
            f"حجم الفيديو الناتج ({actual_size} بايت) أكبر من حد تليكرام "
            f"({TELEGRAM_VIDEO_NOTE_MAX_BYTES} بايت) رغم ضبط البترّيت."
        )

    return out_path
