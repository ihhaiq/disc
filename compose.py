"""
دمج صورة الغلاف (thumbnail) داخل ثقب القرص الدوّار.
النتيجة: صورة PNG واحدة (القرص + الصورة الملصقة بداخله) جاهزة للتدوير في processor.py
"""
from PIL import Image, ImageDraw


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
