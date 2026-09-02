import os

from dotenv import load_dotenv

from texts import ERR_MISSING_BOT_TOKEN
from vinyl_catalog import ASSETS_DIR as ASSETS_PATH
from vinyl_catalog import get_vinyl_style

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

MAX_TELEGRAM_AUDIO_SIZE_BYTES = int(os.environ.get(
    "MAX_TELEGRAM_AUDIO_SIZE_BYTES",
    2 * 1024 * 1024 * 1024 if USE_LOCAL_BOT_API else 20 * 1024 * 1024,
))

FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_LIMIT", 3))
PREMIUM_DAILY_LIMIT = int(os.environ.get("PREMIUM_DAILY_LIMIT", 50))
STARS_SUBSCRIPTION_PRICE = int(os.environ.get("STARS_SUBSCRIPTION_PRICE", 50))
STARS_SUBSCRIPTION_DAYS = int(os.environ.get("STARS_SUBSCRIPTION_DAYS", 30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = str(ASSETS_PATH)

# Compatibility exports. New code should query vinyl_catalog directly.
VINYL_PATH = get_vinyl_style("default").vinyl_path
VINYL_PINK_PATH = get_vinyl_style("pink").vinyl_path
VINYL_BLUE_PATH = get_vinyl_style("blue").vinyl_path
VINYL_YELLOW_PATH = get_vinyl_style("yellow").vinyl_path
VINYL_RED_PATH = get_vinyl_style("red").vinyl_path
VINYL_GREEN_PATH = get_vinyl_style("green").vinyl_path
VINYL_BLOODY_PATH = get_vinyl_style("bloody").vinyl_path
VINYL_ROSE_PATH = get_vinyl_style("rose").vinyl_path
VINYL_EMERALD_PATH = get_vinyl_style("emerald").vinyl_path
VINYL_KOI_PATH = get_vinyl_style("koi").vinyl_path
VINYL_KISS_PATH = get_vinyl_style("kiss").vinyl_path
VINYL_ALI_PATH = get_vinyl_style("ali").vinyl_path

SHADOW_PATH = get_vinyl_style("default").shadow_path
SHADOW_PINK_PATH = get_vinyl_style("pink").shadow_path
SHADOW_BLUE_PATH = get_vinyl_style("blue").shadow_path
SHADOW_YELLOW_PATH = get_vinyl_style("yellow").shadow_path
SHADOW_RED_PATH = get_vinyl_style("red").shadow_path
SHADOW_GREEN_PATH = get_vinyl_style("green").shadow_path
SHADOW_ROSE_PATH = get_vinyl_style("rose").shadow_path

TEMP_DIR = os.path.join(BASE_DIR, "temp")

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
