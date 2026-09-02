import re
from html.parser import HTMLParser


class HTMLToTelegramParser(HTMLParser):
    """Keep the subset of HTML supported by Telegram messages."""

    SUPPORTED_TAGS = frozenset(
        {"b", "strong", "i", "em", "code", "pre", "u", "s", "a", "tg-emoji"}
    )

    def __init__(self):
        super().__init__()
        self.text = ""
        self.open_tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SUPPORTED_TAGS:
            self.open_tags.append(tag)
            if tag in ("b", "strong"):
                self.text += "<b>"
            elif tag in ("i", "em"):
                self.text += "<i>"
            elif tag in ("code", "pre", "u", "s"):
                self.text += f"<{tag}>"
            elif tag == "a":
                href = dict(attrs).get("href", "#")
                self.text += f'<a href="{href}">'
            elif tag == "tg-emoji":
                emoji_id = dict(attrs).get("emoji-id") or ""
                emoji_id = emoji_id if emoji_id.isdigit() else ""
                self.text += f'<tg-emoji emoji-id="{emoji_id}">'

    def handle_endtag(self, tag):
        if tag in self.SUPPORTED_TAGS:
            equivalent_tags = (
                tag,
                "strong" if tag == "b" else tag,
                "em" if tag == "i" else tag,
            )
            if self.open_tags and self.open_tags[-1] in equivalent_tags:
                self.open_tags.pop()
            if tag in ("b", "strong"):
                self.text += "</b>"
            elif tag in ("i", "em"):
                self.text += "</i>"
            elif tag in ("code", "pre", "u", "s", "a", "tg-emoji"):
                self.text += f"</{tag}>"

    def handle_data(self, data):
        self.text += data


def clean_html(html_text: str) -> str:
    """Normalize HTML to the subset accepted by Telegram."""
    for tag in (r"h[1-6]", "p", "div", "footer", "span", "section", "article", "main"):
        html_text = re.sub(rf"</?{tag}[^>]*>", "", html_text)
    html_text = re.sub(r"\n\s*\n+", "\n\n", html_text)

    parser = HTMLToTelegramParser()
    try:
        parser.feed(html_text)
        return parser.text.strip()
    except Exception:
        return re.sub(r"<[^>]+>", "", html_text).strip()


# ============================================================
# config.py
# ============================================================
ERR_MISSING_BOT_TOKEN = "ضع التوكن في متغير البيئة BOT_TOKEN (أو في ملف .env)"


# ============================================================
# main.py
# ============================================================
LOG_BOT_RUNNING = "البوت شغال..."
LOG_USING_LOCAL_BOT_API = "🔌 يتم الاتصال بسيرفر تليكرام المحلي: %s"


# ============================================================
# handlers.py - نصوص الحالة المتحركة (StatusAnimator)
# ============================================================
STAGE_PREPARING = "جاري التجهيز"
STAGE_DOWNLOADING_AUDIO = "جارٍ تنزيل الملف الصوتي"
STAGE_DOWNLOADING_THUMBNAIL = "جارٍ تنزيل صورة الغلاف"
STAGE_BUILDING_DISC = "جارٍ بناء تصميم القرص"
STAGE_RENDERING_VIDEO = "جارٍ تحويل الفيديو"
STAGE_UPLOADING_VIDEO = "جارٍ رفع الفيديو وإرساله"


# ============================================================
# handlers.py - رسالة الحالة الغنية (Rich Status Message)
# ============================================================
MSG_RICH_STATUS_INTRO = "أقوم بإعداد فيديو لك. يرجى مراجعة الحالة لاحقاً..."


# ============================================================
# handlers.py - رسائل السجل (logger)
# ============================================================
LOG_PROGRESS_UPDATE_FAILED = "فشل تحديث رسالة التقدّم"
LOG_DELETE_FAILED_FMT = "تعذر حذف {p}: {e}"
LOG_DOWNLOAD_RETRY_FAILED_FMT = "محاولة تنزيل الملف %s/%s فشلت: %s: %s"
LOG_NO_DETAIL_MESSAGE = "(بدون رسالة تفصيلية)"
LOG_QUEUE_PROCESS_FAILED = "فشل معالجة الطلب في الطابور"
LOG_PROCESS_JOB_FAILED = "فشل معالجة الطلب"
LOG_SEND_ERROR_FAILED = "فشل إرسال رسالة الخطأ للمستخدم"
LOG_FILE_TOO_LARGE = "الملف كبير جدًا، سيتم محاولة المعالجة ثم اقتطاع أول دقيقة منه"
LOG_JOB_TIMEOUT = "انتهت مهلة معالجة الطلب (timeout) وتم إلغاؤه حتى لا يعلّق باقي الطابور"
LOG_TEMP_CLEANUP_STARTUP_FMT = "🧹 تنظيف بدء التشغيل: تم حذف %s ملف/مجلد قديم من TEMP_DIR"
MSG_PROCESSING_TIMEOUT_FMT = "⏱️ استغرقت معالجة هذا الملف وقتًا أطول من المسموح ({minutes:.0f} دقيقة) وتم إلغاؤها. جرب ملفًا أصغر أو حاول مرة أخرى."


# ============================================================
# handlers.py - أخطاء داخلية (Exceptions)
# ============================================================
ERR_NO_THUMBNAIL_AVAILABLE = "لا توجد صورة مصغرة أو صورة بديلة متاحة"
ERR_OUTPUT_NOT_CREATED = "لم يتم إنشاء ملف الفيديو الناتج"


# ============================================================
# handlers.py - رسائل تليكرام للمستخدم
# ============================================================
MSG_AUDIO_RECEIVED = (
    "⏳ تم استلام الملف الصوتي، وسيتم تحويله الآن. "
    "سيتم استعمال أول دقيقة فقط من الملف."
)

MSG_DURATION_TOO_LONG_FMT = (
    "⚠️ الملف أطول من المسموح! {duration:.0f} ثانية. "
    "الحد الأقصى (دقيقة واحدة). "
    "سأرسل لك فيديو لمدة دقيقة واحدة."
)

MSG_PROCESSING_ERROR_FMT = "❌ صار خطأ أثناء المعالجة:\n<code>{error_text}</code>"  # صحيح ✅

MSG_DEV_CHOOSE_TEMPLATE = "🎨 اختر قالب القرص للمطور فقط:"

MSG_VINYL_COLOR_INFO = (
    "🎨 اختر لون القرص:\n"
    "⚫ الأسود\n"
    "💗 وردي \n"
    "🔵 أزرق \n"
    "🟡 أصفر \n"
    "🟥 bloody red"
)

MSG_DEV_SEND_MENU_IMAGE = "🖼️ أرسل الصورة اللي تريدها تظهر بقائمة اختيار اللون:"
MSG_DEV_MENU_IMAGE_SAVED = "✅ تم حفظ صورة القائمة."

BTN_DEV_SET_MENU_IMAGE = "🖼️ تغيير صورة القائمة"
MSG_START_HELP = (
    "<b>I'm making a vinyl Disc 💽🎶</b>\n\n"
    "💽 أرسل لي ملف صوتي (audio) يحتوي صورة مصغرة، "
    "وراح أرجع لك فيديو قرص دوّار (vinyl) بصورتك وصوتك 💽⚡️\n\n"
    "<b>🎶 اختر سرعة دوران القرص:</b>\n"
    "<i>هذا لا يغيّر سرعة الصوت أو الملف</i>"
)

MSG_JOB_QUEUED = (
    "🧵 تم إضافة الملف إلى الطابور، وسيتم معالجته بمجرد انتهاء الملفات السابقة. "
    "سيتم استعمال أول دقيقة فقط من الملف."
)

MSG_QUEUE_CANCELED_EDIT = "🗑️ تم إلغاء الأعمال المعلقة لهذا المستخدم وإخلاء الطابور الخاص به."
MSG_QUEUE_CANCELED_ANSWER = "✅ تم إلغاء الطلبات المعلقة"

# --- الطابور المرئي ---
MSG_QUEUE_POSITION_NEXT = "🔜 دورك جاي! بيبدأ العمل على طلبك خلال لحظات."
MSG_QUEUE_POSITION_FMT = "📊 أنت بالمرتبة {position} بالطابور، وراح نبدأ فور ما يخلص اللي قبلك."

# --- المعاينة السريعة ---
BTN_WIZ_PREVIEW = "🔍 معاينة سريعة (٣ ثواني)"
MSG_PREVIEW_STARTING = "🔍 جارٍ تجهيز معاينة سريعة (٣ ثواني بجودة مخفّضة)..."
MSG_PREVIEW_READY_CAPTION = "🔍 هذي معاينة سريعة بجودة منخفضة (٣ ثواني) — النسخة النهائية بجودة كاملة."
BTN_WIZ_CONFIRM_FULL = "🚀 إنشاء الفيديو الكامل"
MSG_WIZ_REVIEW = "✅ جاهزين! تقدر تطلب معاينة سريعة أولاً، أو تنشئ الفيديو الكامل مباشرة."

# --- معاينة الألوان (قبل الاختيار) ---
BTN_VINYL_COLOR_PREVIEW = "معاينة"

MSG_SEND_IMAGE_NOW = "📷 أرسل لي الصورة الآن وسأستخدمها مع الملف الصوتي."
MSG_NO_PENDING_AUDIO = "⚠️ لا يوجد ملف صوتي معلق مرتبط بهذه الصورة بعد."
MSG_AUDIO_EXPIRED = "⏰ انتهت مدة انتظار الملف الصوتي. أرسل الملف الصوتي مرة أخرى."
MSG_IMAGE_RECEIVED = (
    "✅ تم استلام الصورة، وسيبدأ البوت الآن بالعمل على الملف الصوتي "
    "بدون الحاجة لإرساله مرة أخرى."
)

MSG_DEV_ONLY_OPTION = "هذا الخيار للمطور فقط"
MSG_VINYL_CHOICE_SAVED_ANSWER = "✅ تم حفظ الاختيار"
MSG_SPEED_SAVED_ANSWER = "✅ تم حفظ سرعة القرص لهذا المستخدم"

# --- لوحة المطور: تحديد الأقراص المدفوعة (Premium-only colors) ---
BTN_DEV_LIMITS_MENU = "🔒 الحدود"
MSG_DEV_LIMITS_HEADER = (
    "🔒 الأقراص المتوفرة:\n"
    "اضغط على أي قرص لتبديل حالته بين 🆓 مجاني و 💎 مدفوع.\n"
    "الأقراص المدفوعة ما تشتغل إلا للمشتركين (أو القائمة البيضاء أو المطور)."
)
BTN_DEV_LIMITS_FREE_SUFFIX = "🆓"
BTN_DEV_LIMITS_PAID_SUFFIX = "💎"
MSG_DEV_LIMITS_TOGGLED_PAID_FMT = "💎 صار «{name}» قرص مدفوع."
MSG_DEV_LIMITS_TOGGLED_FREE_FMT = "🆓 صار «{name}» قرص مجاني."
MSG_COLOR_PREMIUM_ONLY = (
    "💎 هذا اللون متاح فقط للمشتركين بالاشتراك المدفوع.\n"
    "اضغط زر الاشتراك بالرسالة الرئيسية لتفعيله."
)

MSG_WRONG_TYPE = "📌 أرسل ملف صوتي (Audio) وليس فيديو أو مستند، حتى تكو صورته المصغرة موجودة."
MSG_CHANNEL_ADMIN_ONLY = "🚫 هذا التحكم متاح فقط لمشرفي القناة."
MSG_CHANNEL_ASK_IMAGE_REPLY = (
    "🖼 رجاءً ردّ على هذي الرسالة بصورة الغلاف المطلوبة (اضغط على الرسالة "
    "واختر «رد» ثم أرفق الصورة)."
)
MSG_CHANNEL_ASK_IMAGE_REPLY_WITH_SKIP = (
    "🖼 رجاءً ردّ على هذي الرسالة بصورة الغلاف الجديدة (إن أردت استبدالها)، "
    "أو اضغط تخطي للاحتفاظ بالصورة الأصلية."
)

# --- Wizard: quick vs customize ---
MSG_CHOOSE_MODE = "📀 وصلني الملف! اختار شلون نسويلك القرص:"
BTN_QUICK_CREATE = "⚡ إنشاء سريع"
BTN_CUSTOMIZE = "🎛 تخصيص"

MSG_WIZ_CHOOSE_COLOR = "🎨 اختار لون القرص:"
MSG_WIZ_CHOOSE_SPEED = "🎚 اختار سرعة الدوران:"
MSG_WIZ_CHOOSE_IMAGE = (
    "🖼 أرسل صورة الغلاف الجديدة (تستبدل الحالية لو موجودة)،"
    "\nأو اضغط تخطي للاحتفاظ بالصورة الأصلية."
)
BTN_WIZ_SKIP_IMAGE = "⏭ تخطي (استخدم الصورة الأصلية)"
MSG_WIZ_NO_IMAGE_TO_SKIP = "⚠️ الملف ما فيه صورة أصلية، لازم ترسل صورة."
MSG_WIZ_CHOOSE_SEGMENT = "⏱ الملف مدته أطول من دقيقة، اختار الدقيقة المراد تسجيلها:"
MSG_WIZ_STARTING = "🚀 تمام، جار الإنشاء بالإعدادات المختارة..."
MSG_WIZ_EXPIRED = "⌛ انتهت صلاحية الجلسة، أرسل الملف من جديد."
BTN_WIZ_SEGMENT_FMT = "⏱ الدقيقة {n}"
MSG_QUICK_NEED_IMAGE = (
    "⚡ إنشاء سريع: هذا الملف ما فيه صورة مصغرة، أرسل الصورة الآن وسأكمل تلقائيًا."
)
# ============================================================
# handlers.py - نصوص الأزرار (Inline Keyboard buttons)
# ============================================================
BTN_ADD_IMAGE = "➕ إضافة صورة"
BTN_CANCEL = "❌ إلغاء"

BTN_VINYL_PINK = "💗  "
BTN_VINYL_DEFAULT = "🔙 استخدم العادي"
BTN_VINYL_YELLOW = " 💛 "
BTN_VINYL_BLUE = " 💙"
BTN_VINYL_SILVER = "🩶" 
BTN_VINYL_COLOR_MENU = "🎨 لون القرص"
BTN_VINYL_RED = "❤️" 
BTN_VINYL_BLACK = " "
BTN_VINYL_ROSE = "ROSE💮"
BTN_VINYL_GREEN = "اخضر تجريبي"
BTN_VINYL_BLOODY = "🩸"
BTN_VINYL_EMERALD = "EMERALD"
BTN_VINYL_KOI = "  "
BTN_VINYL_KISS = "KISS"
BTN_VINYL_ALI = "علي رشم"
BTN_BACK = "🔙 رجوع"

SPEED_LABEL_FULL = "دورة كاملة"
SPEED_LABEL_8RPM = "8 دورة في الدقيقة"
SPEED_LABEL_19RPM = " 19 دورة في الدقيقة "
SPEED_LABEL_33RPM = "33 دورة في الدقيقة"
SPEED_LABEL_45RPM = "45 دورة في الدقيقة"

# ============================================================
# handlers.py / limits.py - الحد اليومي + اشتراك نجوم تليكرام
# ============================================================
MSG_LIMIT_REACHED_FMT = (
    "🚫 وصلت للحد اليومي المجاني ({limit} أقراص كل 24 ساعة).\n"
    "⏳ راح يتجدد الحد خلال {hours} ساعة تقريبًا.\n\n"
    "⭐ أو اشترك الآن وارفع حدك اليومي إلى {premium_limit} قرص باليوم "
    "مقابل {price} نجمة تليكرام شهريًا."
)

BTN_BUY_STARS = "⭐ اشتراك {price} نجمة / شهر"

MSG_INVOICE_TITLE = "اشتراك شهري - رفع الحد اليومي"
MSG_INVOICE_DESCRIPTION_FMT = (
    "يرفع هذا الاشتراك حدك اليومي من إنشاء الأقراص إلى {limit} قرص كل 24 ساعة، "
    "لمدة 30 يوم من لحظة الدفع."
)
MSG_INVOICE_LABEL = "اشتراك شهري"
MSG_INVOICE_PAYLOAD_PREFIX = "sub"

MSG_PAYMENT_SUCCESS_FMT = (
    "✅ تم تفعيل الاشتراك بنجاح!\n"
    "🔓 حدك اليومي الآن {limit} قرص كل 24 ساعة، لمدة 30 يوم."
)

LOG_PAYMENT_RECORDED = "تم تسجيل دفعة نجوم وتفعيل الاشتراك للمستخدم %s"

MSG_NEW_SUBSCRIBER_ADMIN_FMT = (
    "⭐ اشتراك جديد!\n\n"
    "👤 الاسم: {full_name}\n"
    "🔗 اليوزر: {username}\n"
    "🆔 آيدي: {user_id}\n"
    "💰 المبلغ: {amount} نجمة\n"
    "📅 المدة: {days} يوم\n"
    "🔓 الحد الجديد: {limit} قرص/يوم"
)

# ============================================================
# نظام اللغات (Language System)
# ============================================================
# زر اللغة (يظهر بجانب زر لون القرص بالرسالة الرئيسية)
BTN_LANG = "🇮🇶 Language"

# قاموس الترجمة الإنجليزية — أي متغيّر مو موجود هنا يرجع تلقائيًا للنص العربي
# (استخدم نفس أسماء المتغيرات الموجودة فوق كمفاتيح)
TEXTS_EN: dict[str, str] = {
    "MSG_START_HELP": (
        "<b>I'm making a vinyl Disc 💽🎶</b>\n\n"
        "💽 Send me an audio file that has a thumbnail, "
        "and I'll turn it into a spinning vinyl video note with your picture and sound 💽⚡️\n\n"
        "<b>🎶 Choose the disc rotation speed:</b>\n"
        "<i>This doesn't change the audio or file speed</i>"
    ),
    "MSG_CHOOSE_MODE": "📀 Got the file! Choose how you'd like your disc made:",
    "BTN_QUICK_CREATE": "⚡ Quick create",
    "BTN_CUSTOMIZE": "🎛 Customize",
    "MSG_WIZ_CHOOSE_COLOR": "🎨 Choose the disc color:",
    "MSG_WIZ_CHOOSE_SPEED": "🎚 Choose the rotation speed:",
    "MSG_WIZ_CHOOSE_IMAGE": (
        "🖼 Send the new cover image (replaces the current one if any),"
        "\nor tap skip to keep the original image."
    ),
    "BTN_WIZ_SKIP_IMAGE": "⏭ Skip (use original image)",
    "MSG_WIZ_NO_IMAGE_TO_SKIP": "⚠️ This file has no original image, you must send one.",
    "MSG_WIZ_CHOOSE_SEGMENT": "⏱ The file is longer than a minute, choose which minute to use:",
    "MSG_WIZ_STARTING": "🚀 Alright, creating your disc with the chosen settings...",
    "MSG_WIZ_EXPIRED": "⌛ Session expired, please send the file again.",
    "BTN_WIZ_SEGMENT_FMT": "⏱ Minute {n}",
    "MSG_QUICK_NEED_IMAGE": (
        "⚡ Quick create: this file has no thumbnail, send an image now and I'll continue automatically."
    ),
    "BTN_ADD_IMAGE": "➕ Add image",
    "BTN_CANCEL": "❌ Cancel",
    "BTN_VINYL_PINK": "💗  ",
    "BTN_VINYL_DEFAULT": "🔙 Use default",
    "BTN_VINYL_YELLOW": " 💛 ",
    "BTN_VINYL_BLUE": " 💙",
    "BTN_VINYL_SILVER": "🩶",
    "BTN_VINYL_COLOR_MENU": "🎨 Disc color",
    "BTN_VINYL_RED": "❤️",
    "BTN_VINYL_BLACK": " ",
    "BTN_VINYL_GREEN": "Green (beta)",
    "BTN_VINYL_BLOODY": "🩸",
    "BTN_VINYL_ROSE": "💮 ROSE",
    "BTN_VINYL_KOI": "  ",
    "BTN_VINYL_KISS": "KISS",
    "BTN_VINYL_ALI": "ALI",
    "BTN_BACK": "🔙 Back",
    "SPEED_LABEL_FULL": "Full turn",
    "SPEED_LABEL_8RPM": "8 RPM",
    "SPEED_LABEL_19RPM": "19 RPM",
    "SPEED_LABEL_33RPM": "33 RPM",
    "SPEED_LABEL_45RPM": "45 RPM",
    "MSG_VINYL_COLOR_INFO": (
        "🎨 Choose the disc color:\n"
        "⚫ Black\n"
        "💗 Pink\n"
        "🔵 Blue\n"
        "🟡 Yellow\n"
        "🟥 Bloody red"
    ),
    "MSG_WRONG_TYPE": "📌 Send an audio file, not a video or document, so its thumbnail is available.",
    "MSG_AUDIO_RECEIVED": (
        "⏳ Audio file received, converting it now. "
        "Only the first minute of the file will be used."
    ),
    "MSG_DURATION_TOO_LONG_FMT": (
        "⚠️ The file is longer than allowed! {duration:.0f} seconds. "
        "Maximum is one minute. "
        "I'll send you a one-minute video."
    ),
    "MSG_PROCESSING_ERROR_FMT": "❌ An error occurred while processing:\n<code>{error_text}</code>",
    "MSG_JOB_QUEUED": (
        "🧵 The file was added to the queue and will be processed once previous files are done. "
        "Only the first minute of the file will be used."
    ),
    "MSG_QUEUE_CANCELED_EDIT": "🗑️ Your pending jobs were canceled and your queue was cleared.",
    "MSG_QUEUE_CANCELED_ANSWER": "✅ Pending requests canceled",
    "MSG_QUEUE_POSITION_NEXT": "🔜 You're up next! Work on your request starts in a moment.",
    "MSG_QUEUE_POSITION_FMT": "📊 You're number {position} in the queue, we'll start once it's your turn.",
    "BTN_WIZ_PREVIEW": "🔍 Quick preview (3s)",
    "MSG_PREVIEW_STARTING": "🔍 Preparing a quick low-quality preview (3 seconds)...",
    "MSG_PREVIEW_READY_CAPTION": "🔍 This is a quick low-quality preview (3s) — the final version will be full quality.",
    "BTN_WIZ_CONFIRM_FULL": "🚀 Create the full video",
    "MSG_WIZ_REVIEW": "✅ All set! You can request a quick preview first, or create the full video right away.",
    "BTN_VINYL_COLOR_PREVIEW": "Preview",
    "MSG_SEND_IMAGE_NOW": "📷 Send me the image now and I'll use it with the audio file.",
    "MSG_NO_PENDING_AUDIO": "⚠️ No pending audio file linked to this image yet.",
    "MSG_AUDIO_EXPIRED": "⏰ The audio file wait time expired. Please send the audio file again.",
    "MSG_IMAGE_RECEIVED": (
        "✅ Image received, the bot will now start working on the audio file "
        "without needing to send it again."
    ),
    "MSG_DEV_ONLY_OPTION": "This option is for the developer only",
    "BTN_DEV_LIMITS_MENU": "🔒 Limits",
    "MSG_DEV_LIMITS_HEADER": (
        "🔒 Available discs:\n"
        "Tap any disc to toggle it between 🆓 Free and 💎 Paid.\n"
        "Paid discs only work for subscribers (or whitelist/developer)."
    ),
    "BTN_DEV_LIMITS_FREE_SUFFIX": "🆓",
    "BTN_DEV_LIMITS_PAID_SUFFIX": "💎",
    "MSG_DEV_LIMITS_TOGGLED_PAID_FMT": "💎 \"{name}\" is now a paid disc.",
    "MSG_DEV_LIMITS_TOGGLED_FREE_FMT": "🆓 \"{name}\" is now a free disc.",
    "MSG_COLOR_PREMIUM_ONLY": (
        "💎 This color is only available for paid subscribers.\n"
        "Tap the subscribe button on the main message to unlock it."
    ),
    "MSG_VINYL_CHOICE_SAVED_ANSWER": "✅ Choice saved",
    "MSG_SPEED_SAVED_ANSWER": "✅ Disc speed saved for this user",
    "STAGE_PREPARING": "Preparing",
    "STAGE_DOWNLOADING_AUDIO": "Downloading the audio file",
    "STAGE_DOWNLOADING_THUMBNAIL": "Downloading the cover image",
    "STAGE_BUILDING_DISC": "Building the disc design",
    "STAGE_RENDERING_VIDEO": "Rendering the video",
    "STAGE_UPLOADING_VIDEO": "Uploading and sending the video",
    "MSG_LIMIT_REACHED_FMT": (
        "🚫 You've reached the free daily limit ({limit} discs every 24 hours).\n"
        "⏳ Your limit resets in about {hours} hour(s).\n\n"
        "⭐ Or subscribe now and raise your daily limit to {premium_limit} discs/day "
        "for {price} Telegram Stars per month."
    ),
    "BTN_BUY_STARS": "⭐ Subscribe {price} stars / month",
    "MSG_PAYMENT_SUCCESS_FMT": (
        "✅ Subscription activated successfully!\n"
        "🔓 Your daily limit is now {limit} discs every 24 hours, for 30 days."
    ),
    "BTN_LANG": "🇮🇶 Language",
    "MSG_RICH_STATUS_INTRO": "I'm preparing a video for you. Please check the status later...",
}
