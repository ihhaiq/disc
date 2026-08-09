import os
from dotenv import load_dotenv

from texts import ERR_MISSING_BOT_TOKEN

load_dotenv()  # يقرأ ملف .env تلقائياً إذا موجود

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError(ERR_MISSING_BOT_TOKEN)

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", 3))
DEVELOPER_ID = int(os.environ.get("DEVELOPER_ID", 0))
ROTATION_SECONDS = float(os.environ.get("ROTATION_SECONDS", 4))
OUTPUT_FPS = int(os.environ.get("OUTPUT_FPS", 30))
DISC_SIZE = int(os.environ.get("DISC_SIZE", 640))
HOLE_RATIO = float(os.environ.get("HOLE_RATIO", 0.42))

MAX_DURATION_SECONDS = float(os.environ.get("MAX_DURATION_SECONDS", 60))  # حد تليكرام لفيديو نوت

# --- Local Bot API Server (telegram-bot-api) ---
# لو محدد، البوت يتصل بسيرفر تليكرام محلي بدل api.telegram.org
# عشان يرفع حد تنزيل/رفع الملفات من 20 ميجا إلى 2 جيجا.
# API_ID / API_HASH يُستخدمان من طرف حاوية telegram-bot-api نفسها (سيرفس منفصل على Railway)،
# مو من كود بايثون هذا مباشرة - لكن نتحقق من وجودهم هنا فقط للتأكد أن الإعداد مكتمل.
API_ID = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
LOCAL_BOT_API_URL = os.environ.get("LOCAL_BOT_API_URL", "").rstrip("/")
USE_LOCAL_BOT_API = bool(LOCAL_BOT_API_URL)

MAX_TELEGRAM_AUDIO_SIZE_BYTES = int(os.environ.get(
    "MAX_TELEGRAM_AUDIO_SIZE_BYTES",
    2 * 1024 * 1024 * 1024 if USE_LOCAL_BOT_API else 20 * 1024 * 1024,
))

# --- الحد اليومي لعدد الأقراص + اشتراك نجوم تليكرام ---
FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_LIMIT", 3))          # عدد الأقراص المجانية كل 24 ساعة
PREMIUM_DAILY_LIMIT = int(os.environ.get("PREMIUM_DAILY_LIMIT", 50))   # الحد بعد الاشتراك
STARS_SUBSCRIPTION_PRICE = int(os.environ.get("STARS_SUBSCRIPTION_PRICE", 50))  # سعر الاشتراك بنجوم تليكرام
STARS_SUBSCRIPTION_DAYS = int(os.environ.get("STARS_SUBSCRIPTION_DAYS", 30))    # مدة الاشتراك (يوم)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
VINYL_PATH = os.path.join(ASSETS_DIR, "vinyl.png")
VINYL_PINK_PATH = os.path.join(ASSETS_DIR, "vinyl_pink.png")
VINYL_BLUE_PATH = os.path.join(ASSETS_DIR, "vinyl_blue.png")
SHADOW_PATH = os.path.join(ASSETS_DIR, "shadow.png")
SHADOW_PINK_PATH = os.path.join(ASSETS_DIR, "shadow_pink.png")
SHADOW_BLUE_PATH = os.path.join(ASSETS_DIR, "shadow_blue.png")
VINYL_YELLOW_PATH = os.path.join(ASSETS_DIR, "vinyl_yellow.png")
SHADOW_YELLOW_PATH = os.path.join(ASSETS_DIR, "shadow_yellow.png")
VINYL_RED_PATH = os.path.join(ASSETS_DIR, "vinyl_red.png")
VINYL_GREEN_PATH = os.path.join(ASSETS_DIR, "vinyl_green.png")
SHADOW_GREEN_PATH = os.path.join(ASSETS_DIR, "shadow_green.png")
SHADOW_RED_PATH = os.path.join(ASSETS_DIR, "shadow_red.png")
VINYL_BLOODY_PATH = os.path.join(ASSETS_DIR, "vinyl_bloody.png")
VINYL_ROSE_PATH = os.path.join(ASSETS_DIR, "vinyl_rose.png")
SHADOW_ROSE_PATH = os.path.join(ASSETS_DIR, "shadow_rose.png")
VINYL_EMERALD_PATH = os.path.join(ASSETS_DIR, "vinyl_emerald.png")
VINYL_KOI_PATH = os.path.join(ASSETS_DIR, "vinyl_koi.png")
VINYL_KISS_PATH = os.path.join(ASSETS_DIR, "vinyl_kiss.png")
FRAME_SILVER_PATH = os.path.join(ASSETS_DIR, "frame_silver.png")
# قطر القرص بعد تصغيره ليدخل بالكامل داخل الفتحة الداخلية للإطار الفضي.
# 0.70 من 640 = 448px، مع ترك حافة فضية ظاهرة من جميع الجهات.
FRAME_SILVER_DISC_RATIO = 0.855

TEMP_DIR = os.path.join(BASE_DIR, "temp")

# --- مجلد التخزين الدائم (لازم يكون مربوط بـ Railway Volume) ---
# يخزّن هنا حدود الاستخدام والاشتراكات والقائمة البيضاء عشان ما تنمسح مع كل ديبلوي.
# لو ما ضبطت DATA_DIR كمتغير بيئة يشاور على مسار الـ Volume، البيانات بتضيع
# مع أي إعادة نشر لأن باقي مجلدات المشروع مؤقتة وتتصفر مع كل Deploy.
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
