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
MAX_TELEGRAM_AUDIO_SIZE_BYTES = int(os.environ.get("MAX_TELEGRAM_AUDIO_SIZE_BYTES", 20 * 1024 * 1024))

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
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# ============================================================
# نمط "ألبوم" (بطاقة غلاف مربعة + طرف القرص الأسود يدور خلفها)
# ============================================================
# صورة مرجعية توضيحية تظهر داخل رسالة "نمط آخر" (يعينها المطور من /dev)
ALBUM_STYLE_IMAGE_PATH = os.path.join(ASSETS_DIR, "album_style_reference.jpg")

# نسب التخطيط (كلها نسبة إلى DISC_SIZE) لتوليد فيديو نمط الألبوم
ALBUM_COVER_RATIO = 0.72          # حجم بطاقة الغلاف المربعة
ALBUM_COVER_CORNER_RATIO = 0.06   # استدارة زوايا بطاقة الغلاف (نسبة إلى حجمها)
ALBUM_COVER_OFFSET_X_RATIO = 0.0  # إزاحة بطاقة الغلاف أفقيًا
ALBUM_COVER_OFFSET_Y_RATIO = 0.12 # إزاحة بطاقة الغلاف عموديًا

ALBUM_DISC_RATIO = 0.80           # قطر القرص الدوّار خلف البطاقة
ALBUM_DISC_VISIBLE_RATIO = 0.42   # أي جزء من القرص يبقى ظاهر خارج البطاقة (أفقيًا)
ALBUM_DISC_OFFSET_Y_RATIO = 0.10  # إزاحة القرص عموديًا
