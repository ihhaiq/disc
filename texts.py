# -*- coding: utf-8 -*-
"""
كل النصوص المستخدمة في المشروع (رسائل تليكرام، نصوص الأزرار، ورسائل السجل)
مجمّعة هنا كمتغيرات حتى يسهل تعديلها بدون البحث داخل كل ملف.
"""
import re
from html.parser import HTMLParser


# ============================================================
# دوال تحويل النصوص والـ HTML
# ============================================================

class HTMLToTelegramParser(HTMLParser):
    """محوّل HTML إلى صيغة Telegram المدعومة (<b>, <i>, <code>, إلخ)"""
    
    def __init__(self):
        super().__init__()
        self.text = ""
        self.open_tags = []
    
    def handle_starttag(self, tag, attrs):
        # فقط الـ tags المدعومة (+ tg-emoji للإيموجي البريميوم، مدعومة أصلاً بـ Telegram HTML)
        if tag in ('b', 'strong', 'i', 'em', 'code', 'pre', 'u', 's', 'a', 'tg-emoji'):
            self.open_tags.append(tag)
            if tag in ('b', 'strong'):
                self.text += '<b>'
            elif tag in ('i', 'em'):
                self.text += '<i>'
            elif tag == 'code':
                self.text += '<code>'
            elif tag == 'pre':
                self.text += '<pre>'
            elif tag == 'u':
                self.text += '<u>'
            elif tag == 's':
                self.text += '<s>'
            elif tag == 'a':
                href = dict(attrs).get('href', '#')
                self.text += f'<a href="{href}">'
            elif tag == 'tg-emoji':
                # نحافظ على emoji-id كما هو (أرقام فقط لحماية إضافية) حتى لا يضيع
                # ونقدر لاحقًا نبني منه custom_emoji entity صحيح
                emoji_id = dict(attrs).get('emoji-id', '')
                emoji_id = emoji_id if emoji_id.isdigit() else ''
                self.text += f'<tg-emoji emoji-id="{emoji_id}">'
    
    def handle_endtag(self, tag):
        if tag in ('b', 'strong', 'i', 'em', 'code', 'pre', 'u', 's', 'a', 'tg-emoji'):
            if self.open_tags and self.open_tags[-1] in (tag, 'strong' if tag == 'b' else tag, 'em' if tag == 'i' else tag):
                self.open_tags.pop()
            if tag in ('b', 'strong'):
                self.text += '</b>'
            elif tag in ('i', 'em'):
                self.text += '</i>'
            elif tag == 'code':
                self.text += '</code>'
            elif tag == 'pre':
                self.text += '</pre>'
            elif tag == 'u':
                self.text += '</u>'
            elif tag == 's':
                self.text += '</s>'
            elif tag == 'a':
                self.text += '</a>'
            elif tag == 'tg-emoji':
                self.text += '</tg-emoji>'
    
    def handle_data(self, data):
        self.text += data


def clean_html(html_text: str) -> str:
    """تحويل HTML الخام إلى Telegram HTML صحيح (شيل tags غير مدعومة)"""
    # شيل أي tags غير مدعومة
    html_text = re.sub(r'</?h[1-6][^>]*>', '', html_text)  # شيل h1-h6
    html_text = re.sub(r'</?p[^>]*>', '', html_text)  # شيل p
    html_text = re.sub(r'</?div[^>]*>', '', html_text)  # شيل div
    html_text = re.sub(r'</?footer[^>]*>', '', html_text)  # شيل footer
    html_text = re.sub(r'</?span[^>]*>', '', html_text)  # شيل span
    html_text = re.sub(r'</?section[^>]*>', '', html_text)  # شيل section
    html_text = re.sub(r'</?article[^>]*>', '', html_text)  # شيل article
    html_text = re.sub(r'</?main[^>]*>', '', html_text)  # شيل main
    
    # حوّل الفواصل الفارغة إلى newlines
    html_text = re.sub(r'\n\s*\n+', '\n\n', html_text)  # دمج newlines متكررة
    
    parser = HTMLToTelegramParser()
    try:
        parser.feed(html_text)
        return parser.text.strip()
    except:
        # لو فشل التحليل، أرجع النص مع شيل tags فقط
        return re.sub(r'<[^>]+>', '', html_text).strip()


def text_to_bold(text: str) -> str:
    """حوّل نص عادي إلى عريض"""
    return f"<b>{text}</b>"


def text_to_italic(text: str) -> str:
    """حوّل نص عادي إلى مائل"""
    return f"<i>{text}</i>"


def text_to_code(text: str) -> str:
    """حوّل نص عادي إلى كود"""
    return f"<code>{text}</code>"


def text_to_underline(text: str) -> str:
    """حوّل نص عادي إلى مسطر"""
    return f"<u>{text}</u>"


def text_to_strikethrough(text: str) -> str:
    """حوّل نص عادي إلى مشطوب"""
    return f"<s>{text}</s>"

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

MSG_TEMPLATE_FILES_MISSING = (
    "⚠️ ملفات القالب (vinyl.png / shadow.png) غير موجودة في مجلد assets/. "
    "ضعها ثم أعد المحاولة."
)

MSG_NO_THUMBNAIL_PROMPT = (
    "⚠️ هذا الملف الصوتي لا يحتوي صورة مصغرة (thumbnail). "
    "يمكنك الضغط على الزر أدناه لإضافة صورة ثم سأستخدمها مع الملف الصوتي."
)

MSG_JOB_QUEUED = (
    "🧵 تم إضافة الملف إلى الطابور، وسيتم معالجته بمجرد انتهاء الملفات السابقة. "
    "سيتم استعمال أول دقيقة فقط من الملف."
)

MSG_QUEUE_CANCELED_EDIT = "🗑️ تم إلغاء الأعمال المعلقة لهذا المستخدم وإخلاء الطابور الخاص به."
MSG_QUEUE_CANCELED_ANSWER = "✅ تم إلغاء الطلبات المعلقة"

MSG_SEND_IMAGE_NOW = "📷 أرسل لي الصورة الآن وسأستخدمها مع الملف الصوتي."
MSG_NO_PENDING_AUDIO = "⚠️ لا يوجد ملف صوتي معلق مرتبط بهذه الصورة بعد."
MSG_AUDIO_EXPIRED = "⏰ انتهت مدة انتظار الملف الصوتي. أرسل الملف الصوتي مرة أخرى."
MSG_IMAGE_RECEIVED = (
    "✅ تم استلام الصورة، وسيبدأ البوت الآن بالعمل على الملف الصوتي "
    "بدون الحاجة لإرساله مرة أخرى."
)

MSG_DEV_ONLY_OPTION = "هذا الخيار للمطور فقط"
MSG_VINYL_CHOICE_SAVED_EDIT = "🎨 تم حفظ اختيار قالب القرص للمطور فقط"
MSG_VINYL_CHOICE_SAVED_ANSWER = "✅ تم حفظ الاختيار"
MSG_SPEED_SAVED_ANSWER = "✅ تم حفظ سرعة القرص لهذا المستخدم"

MSG_WRONG_TYPE = "📌 أرسل ملف صوتي (Audio) وليس فيديو أو مستند، حتى تكو صورته المصغرة موجودة."

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
BTN_VINYL_BLACK = "🖤 "
BTN_VINYL_ROSE = "ROSE💮"
BTN_VINYL_GREEN = "اخضر تجريبي"
BTN_VINYL_BLOODY = "🩸"
BTN_BACK = "🔙 رجوع"

SPEED_LABEL_FULL = "دورة كاملة"
SPEED_LABEL_8RPM = "8 RPM"
SPEED_LABEL_33RPM = "33 RPM"
SPEED_LABEL_45RPM = "45 RPM"

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
BTN_LANG = "🇮🇶 اللغة"

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
    "BTN_VINYL_BLACK": "🖤 ",
    "BTN_VINYL_GREEN": "Green (beta)",
    "BTN_VINYL_BLOODY": "🩸",
    "BTN_VINYL_ROSE" : "💮 ROSE",
    "BTN_BACK": "🔙 Back",
    "SPEED_LABEL_FULL": "Full turn",
    "SPEED_LABEL_8RPM": "8 RPM",
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
    "MSG_SEND_IMAGE_NOW": "📷 Send me the image now and I'll use it with the audio file.",
    "MSG_NO_PENDING_AUDIO": "⚠️ No pending audio file linked to this image yet.",
    "MSG_AUDIO_EXPIRED": "⏰ The audio file wait time expired. Please send the audio file again.",
    "MSG_IMAGE_RECEIVED": (
        "✅ Image received, the bot will now start working on the audio file "
        "without needing to send it again."
    ),
    "MSG_DEV_ONLY_OPTION": "This option is for the developer only",
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
