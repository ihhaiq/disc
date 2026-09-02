"""Build the static disc image used by the video renderer."""

from PIL import Image, ImageDraw


def _open_rgba(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def load_vinyl_template(vinyl_path: str, size: int = 640) -> Image.Image:
    template = _open_rgba(vinyl_path)
    if template.size != (size, size):
        template = template.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    template.putalpha(mask)
    return template


def build_disc(
    thumb_path: str,
    vinyl_path: str,
    out_path: str,
    hole_ratio: float = 0.44,
    size: int = 640,
) -> str:
    vinyl = load_vinyl_template(vinyl_path, size)
    hole_d = int(size * hole_ratio)

    label = _open_rgba(thumb_path)
    w, h = label.size
    m = min(w, h)
    left = (w - m) // 2
    top = (h - m) // 2
    label = label.crop((left, top, left + m, top + m))

    max_label_size = max(1, int(hole_d * 0.96))
    label = label.resize((max_label_size, max_label_size))

    mask = Image.new("L", label.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, max_label_size, max_label_size), fill=255)
    label.putalpha(mask)

    pos = ((size - max_label_size) // 2, (size - max_label_size) // 2)
    vinyl.alpha_composite(label, pos)
    vinyl.save(out_path)
    return out_path
