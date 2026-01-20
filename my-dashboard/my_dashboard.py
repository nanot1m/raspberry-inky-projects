from datetime import datetime
import time
import math
from io import BytesIO
from pathlib import Path

import json

from plugins import TileSpec, layout_tiles, PLUGIN_DEFAULTS, PLUGIN_REGISTRY
from utils import PALETTE_IMAGE, text_size, truncate_text

from inky.auto import auto
from PIL import Image, ImageDraw, ImageFont
try:
    from PIL import ImageCms
except Exception:
    ImageCms = None

EXPECTED_W = 800
EXPECTED_H = 480


class PreviewInky:
    BLACK = 0
    WHITE = 1
    GREEN = 2
    BLUE = 3
    RED = 4
    YELLOW = 5
    ORANGE = 6

    def __init__(self, resolution):
        self.resolution = resolution

def get_inky(upload):
    if not upload:
        return PreviewInky(resolution=(EXPECTED_W, EXPECTED_H))
    try:
        inky = auto()
        cs_pin = getattr(inky, "cs_pin", None)
        if cs_pin is not None:
            try:
                import gpiod

                info = gpiod.Chip("/dev/gpiochip0").get_line_info(cs_pin)
                if info.used and info.consumer == "spi0 CS0":
                    from inky.inky_ac073tc1a import Inky as InkyImpression
                    import gpiodevice
                    from gpiod.line import Direction, Value, Edge
                    from datetime import timedelta

                    class HardwareCSInky(InkyImpression):
                        def _spi_write(self, dc, values):
                            self._gpio.set_value(self.dc_pin, Value.ACTIVE if dc else Value.INACTIVE)
                            if isinstance(values, str):
                                values = [ord(c) for c in values]
                            for byte_value in values:
                                self._spi_bus.xfer([byte_value])

                        def setup(self):
                            if not self._gpio_setup:
                                if self._gpio is None:
                                    gpiochip = gpiodevice.find_chip_by_platform()
                                    gpiodevice.friendly_errors = True
                                    if gpiodevice.check_pins_available(gpiochip, {
                                        "Data/Command": self.dc_pin,
                                        "Reset": self.reset_pin,
                                        "Busy": self.busy_pin,
                                    }):
                                        self.dc_pin = gpiochip.line_offset_from_id(self.dc_pin)
                                        self.reset_pin = gpiochip.line_offset_from_id(self.reset_pin)
                                        self.busy_pin = gpiochip.line_offset_from_id(self.busy_pin)
                                        self._gpio = gpiochip.request_lines(consumer="inky", config={
                                            self.dc_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
                                            self.reset_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
                                            self.busy_pin: gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.RISING, debounce_period=timedelta(milliseconds=10)),
                                        })

                                if self._spi_bus is None:
                                    import spidev
                                    self._spi_bus = spidev.SpiDev()

                                self._spi_bus.open(0, self.cs_channel)
                                try:
                                    self._spi_bus.no_cs = False
                                except OSError:
                                    pass
                                self._spi_bus.max_speed_hz = 5000000

                                self._gpio_setup = True

                            self._gpio.set_value(self.reset_pin, Value.INACTIVE)
                            time.sleep(0.1)
                            self._gpio.set_value(self.reset_pin, Value.ACTIVE)
                            time.sleep(0.1)

                            self._gpio.set_value(self.reset_pin, Value.INACTIVE)
                            time.sleep(0.1)
                            self._gpio.set_value(self.reset_pin, Value.ACTIVE)

                            self._busy_wait(1.0)

                            self._send_command(0x00, [0x49, 0x55, 0x20, 0x08, 0x09, 0x18])
                            self._send_command(0x01, [0x3F, 0x00, 0x32, 0x2A, 0x0E, 0x2A])
                            self._send_command(0x03, [0x5F, 0x69])
                            self._send_command(0x04, [0x00, 0x54, 0x00, 0x44])
                            self._send_command(0x06, [0x40, 0x1F, 0x1F, 0x2C])
                            self._send_command(0x07, [0x6F, 0x1F, 0x16, 0x25])
                            self._send_command(0x08, [0x6F, 0x1F, 0x1F, 0x22])
                            self._send_command(0x0B, [0x00, 0x04])
                            self._send_command(0x30, [0x02])
                            self._send_command(0x41, [0x00])
                            self._send_command(0x50, [0x3F])
                            self._send_command(0x60, [0x02, 0x00])
                            self._send_command(0x61, [0x03, 0x20, 0x01, 0xE0])
                            self._send_command(0x82, [0x1E])
                            self._send_command(0x84, [0x00])
                            self._send_command(0x86, [0x00])
                            self._send_command(0xE3, [0x2F])
                            self._send_command(0xE0, [0x00])
                            self._send_command(0xE5, [0x00])

                    return HardwareCSInky(resolution=(EXPECTED_W, EXPECTED_H), colour="multi")
            except Exception:
                pass
        return inky
    except RuntimeError:
        from inky.inky_e673 import Inky

        return Inky(resolution=(EXPECTED_W, EXPECTED_H), colour="multi")


# Safe area margins from calibrate_safe_area.py
M_LEFT = 60
M_TOP = 35
M_RIGHT = 55
M_BOTTOM = 10

TRAM_REQUESTS = ["Genslerstr", "Werneuchener Str"]
BUS_REQUESTS = ["Werneuchener Str./Große-Leege-Str."]

PHOTO_DIR = Path(__file__).resolve().parent / "photos"
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.default.json"
CONFIG_VERSION = 1


def temp_with_degree_width(draw, temp_value, font):
    temp_text = f"{temp_value:.0f}"
    temp_w, temp_h = text_size(draw, temp_text, font)
    radius = max(5, temp_h // 5)
    return temp_w + 6 + (radius * 2)


def draw_dotted_rounded_rect(draw, bbox, radius, dot, gap, color):
    x0, y0, x1, y1 = bbox
    step = dot + gap
    # Top and bottom edges
    x = x0 + radius
    while x < x1 - radius:
        draw.rectangle((x, y0, x + dot, y0 + dot), fill=color)
        draw.rectangle((x, y1 - dot, x + dot, y1), fill=color)
        x += step
    # Left and right edges
    y = y0 + radius
    while y < y1 - radius:
        draw.rectangle((x0, y, x0 + dot, y + dot), fill=color)
        draw.rectangle((x1 - dot, y, x1, y + dot), fill=color)
        y += step
    # Rounded corners with even dot spacing along the arc
    if radius > 0:
        angle_step = step / radius
        for corner_x, corner_y, start_deg in [
            (x0 + radius, y0 + radius, 180),
            (x1 - radius, y0 + radius, 270),
            (x1 - radius, y1 - radius, 0),
            (x0 + radius, y1 - radius, 90),
        ]:
            start_rad = math.radians(start_deg)
            end_rad = start_rad + (math.pi / 2)
            angle = start_rad
            while angle < end_rad:
                cx = int(corner_x + math.cos(angle) * radius)
                cy = int(corner_y + math.sin(angle) * radius)
                draw.rectangle((cx, cy, cx + dot, cy + dot), fill=color)
                angle += angle_step


def draw_rounded_rect_outline(draw, bbox, radius, color, width=1):
    if width <= 0:
        return
    x0, y0, x1, y1 = bbox
    for offset in range(width):
        ox0 = x0 + offset
        oy0 = y0 + offset
        ox1 = x1 - offset
        oy1 = y1 - offset
        r = max(0, radius - offset)
        if r <= 0:
            draw.rectangle((ox0, oy0, ox1, oy1), outline=color)
            continue
        # Corners
        draw.arc((ox0, oy0, ox0 + 2 * r, oy0 + 2 * r), 180, 270, fill=color)
        draw.arc((ox1 - 2 * r, oy0, ox1, oy0 + 2 * r), 270, 360, fill=color)
        draw.arc((ox1 - 2 * r, oy1 - 2 * r, ox1, oy1), 0, 90, fill=color)
        draw.arc((ox0, oy1 - 2 * r, ox0 + 2 * r, oy1), 90, 180, fill=color)
        # Edges
        draw.line((ox0 + r, oy0, ox1 - r, oy0), fill=color)
        draw.line((ox0 + r, oy1, ox1 - r, oy1), fill=color)
        draw.line((ox0, oy0 + r, ox0, oy1 - r), fill=color)
        draw.line((ox1, oy0 + r, ox1, oy1 - r), fill=color)


def load_photo_for_box(box_size):
    if not PHOTO_DIR.exists():
        return None
    candidates = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        candidates.extend(PHOTO_DIR.glob(ext))
    candidates = [p for p in candidates if not p.name.startswith("._")]
    if not candidates:
        return None
    path = sorted(candidates)[0]
    img = Image.open(path)
    if ImageCms and "icc_profile" in img.info:
        try:
            srgb = ImageCms.createProfile("sRGB")
            src = ImageCms.ImageCmsProfile(BytesIO(img.info["icc_profile"]))
            img = ImageCms.profileToProfile(img, src, srgb, outputMode="RGB")
        except Exception:
            img = img.convert("RGB")
    else:
        img = img.convert("RGB")
    target_w, target_h = box_size
    img_w, img_h = img.size
    if img_w == 0 or img_h == 0:
        return None
    scale = max(target_w / img_w, target_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def apply_rounded_mask(img, radius):
    if radius <= 0:
        return img
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    rounded = Image.new("RGBA", (w, h))
    rounded.paste(img.convert("RGBA"), (0, 0), mask)
    return rounded


def prepare_photo_for_paste(photo, radius):
    rounded = apply_rounded_mask(photo, radius)
    bg = Image.new("RGB", rounded.size, "white")
    bg.paste(rounded, (0, 0), rounded)
    return bg.quantize(palette=PALETTE_IMAGE, dither=Image.NONE)


def todays_hourly_temps(hourly_pairs):
    today = datetime.now().date()
    result = []
    for ts, temp in hourly_pairs:
        if not ts or temp is None:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt.date() == today:
            result.append((dt.hour, temp))
    return result


def draw_temp_graph(draw, x, y, width, height, hourly, fonts, inky):
    if not hourly:
        draw.text((x, y), "Temp graph unavailable", inky.BLACK, font=fonts[3])
        return
    temps = [t for _, t in hourly]
    t_min = min(temps)
    t_max = max(temps)
    if t_max == t_min:
        t_max += 1

    left = x
    right = x + width
    top = y
    bottom = y + height
    draw.rectangle((left, top, right, bottom), outline=inky.BLACK)
    draw.line((left + 1, bottom - 1, right - 1, bottom - 1), fill=inky.BLACK)

    def scale_x(idx):
        return left + int(idx * (width - 2) / max(1, len(hourly) - 1)) + 1

    def scale_y(temp):
        return top + int((t_max - temp) * (height - 2) / (t_max - t_min)) + 1

    points = []
    for idx, (_, temp) in enumerate(hourly):
        points.append((scale_x(idx), scale_y(temp)))
    if len(points) >= 2:
        draw.line(points, fill=inky.RED, width=2)
    for px, py in points[::2]:
        draw.ellipse((px - 1, py - 1, px + 1, py + 1), fill=inky.BLACK, outline=inky.BLACK)

    min_text = f"{t_min:.0f}"
    max_text = f"{t_max:.0f}"
    min_w, _ = text_size(draw, min_text, fonts[3])
    max_w, _ = text_size(draw, max_text, fonts[3])
    draw.text((left - 4 - min_w, bottom - 14), min_text, inky.BLACK, font=fonts[3])
    draw.text((left - 4 - max_w, top + 2), max_text, inky.BLACK, font=fonts[3])

    hour_index = {}
    for idx, (hour, _) in enumerate(hourly):
        hour_index.setdefault(hour, idx)
    now_hour = datetime.now().hour
    if now_hour in hour_index:
        hx = scale_x(hour_index[now_hour])
        draw.line((hx, top + 1, hx, bottom - 1), fill=inky.BLUE, width=1)

    for hour in (0, 6, 12, 18, 23):
        if hour not in hour_index:
            continue
        hx = scale_x(hour_index[hour])
        draw.line((hx, bottom - 3, hx, bottom), fill=inky.BLACK)
        label = f"{hour:02d}"
        label_w, _ = text_size(draw, label, fonts[3])
        draw.text((hx - label_w // 2, bottom + 2), label, inky.BLACK, font=fonts[3])


def normalize_config(cfg):
    if not isinstance(cfg, dict):
        return default_config()
    if "version" not in cfg:
        cfg = {**cfg, "version": CONFIG_VERSION}
    return cfg


def default_config():
    if DEFAULT_CONFIG_PATH.exists():
        try:
            return normalize_config(json.loads(DEFAULT_CONFIG_PATH.read_text()))
        except Exception:
            pass
    return normalize_config({
        "update_interval_minutes": 15,
        "update_schedule": "*/15 * * * *",
        "layout": {
            "cols": 2,
            "rows": 2,
            "gutter": 12,
            "border": {
                "width": 1,
                "radius": 0,
                "style": "solid",
                "color": "black",
            },
            "tiles": [
                {
                    "plugin": "transit",
                    "col": 0,
                    "row": 0,
                    "colspan": 1,
                    "rowspan": 2,
                    "config": {
                        **PLUGIN_DEFAULTS["transit"],
                        "stops": TRAM_REQUESTS,
                        "title_color": "red",
                        "line_bg": "red",
                        "line_text_color": "white",
                    },
                },
                {
                    "plugin": "weather",
                    "col": 1,
                    "row": 0,
                    "colspan": 1,
                    "rowspan": 1,
                    "config": {**PLUGIN_DEFAULTS["weather"]},
                },
                {
                    "plugin": "transit",
                    "col": 1,
                    "row": 1,
                    "colspan": 1,
                    "rowspan": 1,
                    "config": {
                        **PLUGIN_DEFAULTS["transit"],
                        "stops": BUS_REQUESTS,
                        "title_color": "blue",
                        "line_bg": "blue",
                        "line_text_color": "white",
                    },
                },
            ],
        },
    })


def load_config():
    if not CONFIG_PATH.exists():
        return default_config()
    try:
        return normalize_config(json.loads(CONFIG_PATH.read_text()))
    except Exception:
        return default_config()


def build_tile_specs(config):
    layout = config.get("layout", {})
    tiles = []
    for tile in layout.get("tiles", []):
        tiles.append(
            TileSpec(
                plugin=tile.get("plugin", ""),
                col=int(tile.get("col", 0)),
                row=int(tile.get("row", 0)),
                colspan=int(tile.get("colspan", 1)),
                rowspan=int(tile.get("rowspan", 1)),
                config=tile.get("config", {}),
            )
        )
    return tiles


def wrap_text(draw, text, max_width, font):
    words = str(text).replace("\n", " ").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return [truncate_text(draw, line, max_width, font) for line in lines]


def draw_tile_error(ctx, bbox, message):
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_title = fonts["sub"]
    font_body = fonts["body"]
    x0, y0, x1, y1 = bbox
    pad = 6
    draw.rectangle((x0, y0, x1, y1), outline=inky.BLACK, fill=inky.WHITE)
    draw.text((x0 + pad, y0 + pad), "Error", inky.RED, font=font_title)
    title_h = text_size(draw, "Ag", font_title)[1]
    y = y0 + pad + title_h + 4
    line_h = text_size(draw, "Ag", font_body)[1] + 2
    max_width = max(0, (x1 - x0) - (pad * 2))
    max_y = y1 - pad
    for line in wrap_text(draw, message, max_width, font_body):
        if y + line_h > max_y:
            break
        draw.text((x0 + pad, y), line, inky.BLACK, font=font_body)
        y += line_h


def render_dashboard(config=None, output_path=None, upload=False):
    cfg = config or default_config()
    layout = cfg.get("layout", {})

    inky = get_inky(upload)
    w, h = inky.resolution
    img = Image.new("P", (w, h))
    img.putpalette(PALETTE_IMAGE.getpalette())
    draw = ImageDraw.Draw(img)

    # Warn if the detected resolution is not the expected 800x480.
    if (w, h) != (EXPECTED_W, EXPECTED_H):
        print(f"warning: expected {EXPECTED_W}x{EXPECTED_H}, got {w}x{h}")

    # Fonts (fall back to default bitmap font if truetype is unavailable)
    try:
        font_title = ImageFont.truetype("DejaVuSans.ttf", 28)
        font_sub = ImageFont.truetype("DejaVuSans.ttf", 20)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 17)
        font_temp = ImageFont.truetype("DejaVuSans.ttf", 56)
        font_meta = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_temp = ImageFont.load_default()
        font_meta = ImageFont.load_default()

    # Background and safe area frame
    draw.rectangle((0, 0, w - 1, h - 1), inky.WHITE)

    x0, y0 = M_LEFT, M_TOP
    x1, y1 = w - 1 - M_RIGHT, h - 1 - M_BOTTOM
    layout_area = (x0, y0, x1, y1)

    tiles = build_tile_specs(cfg)
    gutter = int(layout.get("gutter", 12))
    cols = int(layout.get("cols", 2))
    rows = int(layout.get("rows", 2))

    ctx = {
        "img": img,
        "draw": draw,
        "inky": inky,
        "fonts": {
            "title": font_title,
            "sub": font_sub,
            "body": font_body,
            "temp": font_temp,
            "meta": font_meta,
        },
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    border_cfg = layout.get("border") or {}
    try:
        border_width = int(border_cfg.get("width", 1))
    except (TypeError, ValueError):
        border_width = 1
    try:
        border_radius = int(border_cfg.get("radius", 0))
    except (TypeError, ValueError):
        border_radius = 0
    border_width = max(0, border_width)
    border_radius = max(0, border_radius)
    border_style = str(border_cfg.get("style", "solid")).lower()
    if border_style not in ("solid", "dotted"):
        border_style = "solid"
    orange = getattr(inky, "ORANGE", inky.YELLOW)
    color_map = {
        "black": inky.BLACK,
        "white": inky.WHITE,
        "green": inky.GREEN,
        "blue": inky.BLUE,
        "red": inky.RED,
        "yellow": inky.YELLOW,
        "orange": orange,
    }
    border_color = color_map.get(str(border_cfg.get("color", "black")).lower(), inky.BLACK)

    for spec, bbox in layout_tiles(layout_area, cols=cols, rows=rows, gutter=gutter, tile_layout=tiles):
        left, top, right, bottom = bbox
        tile_w = max(1, right - left + 1)
        tile_h = max(1, bottom - top + 1)
        tile_img = Image.new("P", (tile_w, tile_h))
        tile_img.putpalette(PALETTE_IMAGE.getpalette())
        tile_draw = ImageDraw.Draw(tile_img)
        tile_bbox = (0, 0, tile_w - 1, tile_h - 1)
        tile_draw.rectangle(tile_bbox, fill=inky.WHITE)

        tile_ctx = {
            **ctx,
            "img": tile_img,
            "draw": tile_draw,
        }

        renderer = PLUGIN_REGISTRY.get(spec.plugin)
        if renderer:
            try:
                renderer(tile_ctx, tile_bbox, spec.config)
            except Exception as exc:
                draw_tile_error(tile_ctx, tile_bbox, str(exc))
        else:
            draw_tile_error(tile_ctx, tile_bbox, f"Unknown plugin: {spec.plugin}")

        tile_border_width = min(border_width, (min(tile_w, tile_h) - 1) // 2)
        tile_radius = min(border_radius, (min(tile_w, tile_h) - 1) // 2)
        if tile_border_width > 0:
            if border_style == "dotted":
                dot = max(1, tile_border_width)
                gap = max(1, tile_border_width)
                draw_dotted_rounded_rect(tile_draw, tile_bbox, tile_radius, dot, gap, border_color)
            else:
                if hasattr(tile_draw, "rounded_rectangle") and tile_radius > 0:
                    tile_draw.rounded_rectangle(tile_bbox, radius=tile_radius, outline=border_color, width=tile_border_width)
                else:
                    if tile_radius > 0:
                        draw_rounded_rect_outline(tile_draw, tile_bbox, tile_radius, border_color, width=tile_border_width)
                    else:
                        tile_draw.rectangle(tile_bbox, outline=border_color, width=tile_border_width)

        img.paste(tile_img, (left, top))

    if output_path:
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            img.convert("RGB").save(output_path, format="PNG")
        except Exception:
            pass

    if upload:
        inky.set_image(img)
        inky.show()

    return img


def main():
    cfg = load_config()
    output_dir = Path(__file__).resolve().parent / ".generated"
    render_dashboard(cfg, output_path=output_dir / "dashboard.png", upload=True)
    print("done")


if __name__ == "__main__":
    main()
