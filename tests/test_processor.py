from processor import _parse_ffmpeg_timestamp, compute_bitrate_budget


def test_ffmpeg_timestamp_parser():
    assert _parse_ffmpeg_timestamp("01:02:03.5") == 3723.5
    assert _parse_ffmpeg_timestamp("invalid") == 0.0


def test_bitrate_budget_stays_positive():
    video_bps, audio_bps = compute_bitrate_budget(60)

    assert video_bps >= 250_000
    assert 64_000 <= audio_bps <= 128_000
