"""
دمج صورة الغلاف (thumbnail) داخل ثقب القرص الدوّار.
النتيجة: صورة PNG واحدة (القرص + الصورة الملصقة بداخله) جاهزة للتدوير في processor.py
"""
import hashlib
import logging
import os
import threading

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# قفل يحمي بناء/قراءة كاش معاينات الألوان الثابتة من التداخل بين عدة threads
# (build_disc_static_preview تُستدعى غالبًا عبر asyncio.to_thread).
_preview_cache_lock = threading.Lock()


def load_vinyl_template(vinyl_path: str, size: int = 640) -> Image.Image:
    template = Image.open(vinyl_path).convert("RGBA")
    if template.size != (size, size):
        template = template.resize((size, size))

    # نفرض قناع دائري نظيف بغض النظر عن حواف الرسمة الأصلية (حتى لو ممزّقة/غير منتظمة)
    # أو كون الملف الأصلي بلا قناة شفافية حقيقية إطلاقًا. هذا يضمن عدم تسرّب أي
    # خلفية بيضاء عند أي زاوية دوران.
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    template.putalpha(mask)

    return template


def build_disc(thumb_path: str, vinyl_path: str, out_path: str,
                hole_ratio: float = 0.44, size: int = 640) -> str:
    vinyl = load_vinyl_template(vinyl_path, size)

    hole_d = int(size * hole_ratio)

    label = Image.open(thumb_path).convert("RGBA")
    w, h = label.size
    m = min(w, h)
    label = label.crop(((w - m) // 2, (h - m) // 2, (w - m) // 2 + m, (h - m) // 2 + m))

    max_label_size = max(1, int(hole_d * 0.96))
    label = label.resize((max_label_size, max_label_size))

    mask = Image.new("L", label.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, max_label_size, max_label_size), fill=255)
    label.putalpha(mask)

    pos = ((size - max_label_size) // 2, (size - max_label_size) // 2)
    vinyl.alpha_composite(label, pos)

    vinyl.save(out_path)
    return out_path


def _preview_cache_key(thumb_path: str, vinyl_path: str, shadow_path: str,
                        hole_ratio: float, size: int) -> str:
    """
    مفتاح كاش ثابت لمعاينة لون معيّنة: يعتمد على محتوى صورة الغلاف (hash)
    + مسارات القالب/الظل + hole_ratio + size. نفس صورة الغلاف + نفس اللون
    تنتج دائمًا نفس الصورة النهائية، فلا داعي لإعادة بنائها بـ PIL في كل مرة
    (خصوصًا الكاروسيل اللي يعرض كل الألوان مرة وحدة لكل مستخدم).
    """
    try:
        with open(thumb_path, "rb") as f:
            thumb_hash = hashlib.sha1(f.read()).hexdigest()[:16]
    except OSError:
        # لو تعذّر قراءة الصورة (نادر)، نرجع مفتاح غير قابل لإعادة الاستخدام
        # حتى لا نخزّن كاش مبني على بيانات غير موثوقة.
        return ""
    return f"{thumb_hash}_{os.path.basename(vinyl_path)}_{os.path.basename(shadow_path)}_{hole_ratio}_{size}"


def build_disc_static_preview(thumb_path: str, vinyl_path: str, shadow_path: str,
                               out_path: str, hole_ratio: float = 0.44,
                               size: int = 640, cache_dir: str | None = None) -> str:
    """
    يبني صورة ثابتة تمثّل الشكل النهائي الفعلي للقرص كما يظهر بالفيديو
    (نفس ما يسويه processor.py وقت التصدير، بس لإطار واحد ثابت بزاوية
    دوران صفر): القالب + صورة الغلاف ملصوقة داخل الثقب (عبر build_disc)،
    ثم الظل المخصص لنفس اللون يُركّب فوقها بنفس ترتيب overlay بالفيديو
    (shadow فوق disc). تُستخدم لمعاينة الألوان (الكاروسيل) بدل عرض
    القالب الفارغ وحده.

    لو مُرِّر cache_dir: نتحقق أولاً من وجود نتيجة محفوظة مسبقًا لنفس
    (صورة الغلاف + اللون) ونسخها مباشرة بدل إعادة بنائها بـ PIL — يوفّر
    عمليات فتح/تدوير/تركيب صور مكررة عند عرض قائمة الألوان لكل مستخدم.
    """
    cache_path = None
    if cache_dir:
        key = _preview_cache_key(thumb_path, vinyl_path, shadow_path, hole_ratio, size)
        if key:
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{key}.png")
            with _preview_cache_lock:
                if os.path.exists(cache_path):
                    with open(cache_path, "rb") as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                    return out_path

    build_disc(thumb_path, vinyl_path, out_path, hole_ratio, size)

    disc = Image.open(out_path).convert("RGBA")
    shadow = Image.open(shadow_path).convert("RGBA")
    if shadow.size != disc.size:
        shadow = shadow.resize(disc.size)

    disc.alpha_composite(shadow, (0, 0))
    disc.save(out_path)

    if cache_path:
        with _preview_cache_lock:
            try:
                with open(out_path, "rb") as src, open(cache_path, "wb") as dst:
                    dst.write(src.read())
            except OSError:
                logger.warning("فشل حفظ كاش معاينة اللون (سيُعاد بناؤها كل مرة): %s", cache_path)

    return out_path


def build_placeholder_square(out_path: str, size: int = 640,
                              fill: tuple[int, int, int, int] = (60, 60, 66, 255)) -> str:
    """
    يبني صورة مربعة بلون خالٍ تُستخدم بدل صورة الغلاف عند عدم توفر أي
    صورة حقيقية (لا صورة مستخدم ولا صورة بوت) — تفادي انهيار build_disc
    اللي يتوقع مسار صورة فعلي.
    """
    placeholder = Image.new("RGBA", (size, size), fill)
    placeholder.save(out_path)
    return out_path


def build_album_cover(thumb_path: str, out_path: str, size: int,
                       corner_ratio: float = 0.06) -> str:
    """
    يحوّل صورة المصغّرة (thumbnail) إلى بطاقة غلاف مربعة بزوايا مستديرة
    على خلفية شفافة، لاستخدامها في نمط "ألبوم" (بدل وضعها داخل ثقب القرص).
    """
    cover = Image.open(thumb_path).convert("RGBA")
    w, h = cover.size
    m = min(w, h)
    cover = cover.crop(((w - m) // 2, (h - m) // 2, (w - m) // 2 + m, (h - m) // 2 + m))
    cover = cover.resize((size, size))

    radius = max(1, int(size * corner_ratio))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    cover.putalpha(mask)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(cover, (0, 0))
    canvas.save(out_path)
    return out_path
