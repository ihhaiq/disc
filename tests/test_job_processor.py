from services.job_processor import (
    JOB_TIMEOUT_MAX_SECONDS,
    JOB_TIMEOUT_SECONDS,
    compute_job_timeout_seconds,
)


def test_job_timeout_uses_base_for_unknown_size():
    assert compute_job_timeout_seconds(None) == JOB_TIMEOUT_SECONDS
    assert compute_job_timeout_seconds(0) == JOB_TIMEOUT_SECONDS


def test_job_timeout_is_capped_for_large_files():
    huge_file = 10 * 1024 * 1024 * 1024
    assert compute_job_timeout_seconds(huge_file) == JOB_TIMEOUT_MAX_SECONDS
