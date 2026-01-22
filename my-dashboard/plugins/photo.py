from io import BytesIO
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

from utils import PALETTE_IMAGE

PHOTO_DIR = Path(__file__).resolve().parents[1] / "photos"

DEFAULT_PHOTO_CONFIG = {
    "path": "",
    "fit": "cover",
}

PHOTO_SCHEMA = {
    "path": {
        "type": "string",
        "label": "Photo Path (optional)",
        "help": "Relative to photos/ or absolute path.",
    },
    "upload": {"type": "file", "label": "Upload Photo", "target": "path"},
    "fit": {"type": "enum", "label": "Fit", "options": ["cover", "contain"]},
}


def _load_photo(path):
    img = Image.open(path)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if "icc_profile" in img.info:
        try:
            srgb = ImageCms.createProfile("sRGB")
            src = ImageCms.ImageCmsProfile(BytesIO(img.info["icc_profile"]))
            img = ImageCms.profileToProfile(img, src, srgb, outputMode="RGB")
        except Exception:
            img = img.convert("RGB")
    else:
        img = img.convert("RGB")
    return img.convert("RGB")


def _select_photo(path_value):
    if path_value:
        path = Path(path_value)
        if not path.is_absolute():
            path = PHOTO_DIR / path
        if path.exists():
            return path
        return None
    if not PHOTO_DIR.exists():
        return None
    candidates = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        candidates.extend(PHOTO_DIR.glob(ext))
    candidates = [p for p in candidates if not p.name.startswith("._")]
    if not candidates:
        return None
    return sorted(candidates)[0]


def _fit_cover(img, target_w, target_h):
    img_w, img_h = img.size
    if img_w == 0 or img_h == 0:
        return None
    scale = max(target_w / img_w, target_h / img_h)
    new_w = max(1, int(img_w * scale))
    new_h = max(1, int(img_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _fit_contain(img, target_w, target_h):
    img_w, img_h = img.size
    if img_w == 0 or img_h == 0:
        return None
    scale = min(target_w / img_w, target_h / img_h)
    new_w = max(1, int(img_w * scale))
    new_h = max(1, int(img_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    background = Image.new("RGB", (target_w, target_h), "white")
    left = (target_w - new_w) // 2
    top = (target_h - new_h) // 2
    background.paste(img, (left, top))
    return background


def draw_photo_tile(ctx, bbox, config):
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_body = fonts["body"]
    x0, y0, x1, y1 = bbox
    target_w = max(1, x1 - x0)
    target_h = max(1, y1 - y0)

    path = _select_photo(str(config.get("path") or "").strip())
    if not path:
        draw.rectangle((x0, y0, x1, y1), outline=inky.BLACK, fill=inky.WHITE)
        draw.text((x0 + 6, y0 + 6), "No photo found", inky.BLACK, font=font_body)
        return

    try:
        img = _load_photo(path)
    except Exception:
        draw.rectangle((x0, y0, x1, y1), outline=inky.BLACK, fill=inky.WHITE)
        draw.text((x0 + 6, y0 + 6), "Photo load error", inky.BLACK, font=font_body)
        return

    fit = str(config.get("fit") or "cover").lower()
    if fit == "contain":
        fitted = _fit_contain(img, target_w, target_h)
    else:
        fitted = _fit_cover(img, target_w, target_h)
    if not fitted:
        draw.rectangle((x0, y0, x1, y1), outline=inky.BLACK, fill=inky.WHITE)
        draw.text((x0 + 6, y0 + 6), "Photo invalid", inky.BLACK, font=font_body)
        return

    quantized = fitted.quantize(palette=PALETTE_IMAGE, dither=Image.FLOYDSTEINBERG)
    ctx["img"].paste(quantized, (x0, y0))
