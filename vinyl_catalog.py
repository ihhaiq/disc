"""Single source of truth for vinyl templates and their visual settings."""

from dataclasses import dataclass
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True, slots=True)
class VinylStyle:
    key: str
    text_key: str
    vinyl_filename: str
    shadow_filename: str
    hole_ratio_override: float | None = None

    @property
    def vinyl_path(self) -> str:
        return str(ASSETS_DIR / self.vinyl_filename)

    @property
    def shadow_path(self) -> str:
        return str(ASSETS_DIR / self.shadow_filename)


VINYL_STYLES: tuple[VinylStyle, ...] = (
    VinylStyle("default", "BTN_VINYL_BLACK", "vinyl.png", "shadow.png"),
    VinylStyle("pink", "BTN_VINYL_PINK", "vinyl_pink.png", "shadow_pink.png"),
    VinylStyle("blue", "BTN_VINYL_BLUE", "vinyl_blue.png", "shadow_blue.png"),
    VinylStyle("yellow", "BTN_VINYL_YELLOW", "vinyl_yellow.png", "shadow_yellow.png"),
    VinylStyle("red", "BTN_VINYL_RED", "vinyl_red.png", "shadow_red.png"),
    VinylStyle("green", "BTN_VINYL_GREEN", "vinyl_green.png", "shadow_green.png"),
    VinylStyle("bloody", "BTN_VINYL_BLOODY", "vinyl_bloody.png", "shadow_pink.png"),
    VinylStyle("rose", "BTN_VINYL_ROSE", "vinyl_rose.png", "shadow_rose.png"),
    VinylStyle("emerald", "BTN_VINYL_EMERALD", "vinyl_emerald.png", "shadow_rose.png"),
    VinylStyle("koi", "BTN_VINYL_KOI", "vinyl_koi.png", "shadow_rose.png"),
    VinylStyle("kiss", "BTN_VINYL_KISS", "vinyl_kiss.png", "shadow_rose.png", 0.39),
    VinylStyle("ali", "BTN_VINYL_ALI", "vinyl_ali.png", "shadow_rose.png"),
)

VINYL_STYLE_BY_KEY = {style.key: style for style in VINYL_STYLES}


def get_vinyl_style(key: str | None) -> VinylStyle:
    return VINYL_STYLE_BY_KEY.get((key or "default").lower(), VINYL_STYLE_BY_KEY["default"])


def validate_assets() -> list[str]:
    """Return catalog asset paths that are missing from disk."""
    missing: list[str] = []
    for style in VINYL_STYLES:
        for path in (style.vinyl_path, style.shadow_path):
            if not Path(path).is_file() and path not in missing:
                missing.append(path)
    return missing
