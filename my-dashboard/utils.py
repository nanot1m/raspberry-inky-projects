import json
import time
from datetime import datetime
from urllib.request import Request, urlopen

from PIL import Image

PALETTE_COLORS = [
    (0, 0, 0),        # black (index 0)
    (255, 255, 255),  # white (index 1)
    (0, 128, 0),      # green (index 2)
    (0, 0, 255),      # blue (index 3)
    (255, 0, 0),      # red (index 4)
    (255, 255, 0),    # yellow (index 5)
    (255, 165, 0),    # orange (index 6)
]
PALETTE_IMAGE = Image.new("P", (1, 1))
_palette = []
for color in PALETTE_COLORS:
    _palette.extend(color)
_palette.extend([0, 0, 0] * (256 - len(PALETTE_COLORS)))
PALETTE_IMAGE.putpalette(_palette)


_FETCH_CACHE = {}


def fetch_json(url, timeout=10, retries=3, delay=10, cache_ttl=None):
    if cache_ttl:
        cached = _FETCH_CACHE.get(url)
        if cached:
            expires_at, data = cached
            if time.time() < expires_at:
                return data
    req = Request(url, headers={"User-Agent": "inky-dashboard/1.0"})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as response:
                data = json.load(response)
                if data in (None, {}, []):
                    raise ValueError("Empty response")
                if cache_ttl:
                    _FETCH_CACHE[url] = (time.time() + cache_ttl, data)
                return data
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(delay)

def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def truncate_text(draw, text, max_width, font):
    if text_size(draw, text, font)[0] <= max_width:
        return text
    if max_width <= 0:
        return ""
    ellipsis = "…"
    cut = text
    while cut and text_size(draw, cut + ellipsis, font)[0] > max_width:
        cut = cut[:-1]
    return cut + ellipsis if cut else ""


def parse_when(when):
    if not when:
        return "--:--"
    try:
        return datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except ValueError:
        return "--:--"


def format_updated(when):
    if not when:
        return ""
    try:
        return datetime.fromisoformat(when).strftime("%H:%M")
    except ValueError:
        return when
