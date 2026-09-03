import os

from dotenv import load_dotenv

from texts import ERR_MISSING_BOT_TOKEN

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError(ERR_MISSING_BOT_TOKEN)

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", 2))
DEVELOPER_ID = int(os.environ.get("DEVELOPER_ID", 0))
ROTATION_SECONDS = float(os.environ.get("ROTATION_SECONDS", 4))
OUTPUT_FPS = int(os.environ.get("OUTPUT_FPS", 30))
DISC_SIZE = int(os.environ.get("DISC_SIZE", 640))
HOLE_RATIO = float(os.environ.get("HOLE_RATIO", 0.42))

MAX_DURATION_SECONDS = float(os.environ.get("MAX_DURATION_SECONDS", 60))

LOCAL_BOT_API_URL = os.environ.get("LOCAL_BOT_API_URL", "").rstrip("/")
USE_LOCAL_BOT_API = bool(LOCAL_BOT_API_URL)

MAX_TELEGRAM_AUDIO_SIZE_BYTES = int(
    os.environ.get(
        "MAX_TELEGRAM_AUDIO_SIZE_BYTES",
        2 * 1024 * 1024 * 1024 if USE_LOCAL_BOT_API else 20 * 1024 * 1024,
    )
)

FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_LIMIT", 3))
PREMIUM_DAILY_LIMIT = int(os.environ.get("PREMIUM_DAILY_LIMIT", 50))
STARS_SUBSCRIPTION_PRICE = int(os.environ.get("STARS_SUBSCRIPTION_PRICE", 50))
STARS_SUBSCRIPTION_DAYS = int(os.environ.get("STARS_SUBSCRIPTION_DAYS", 30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
