from datetime import datetime
import time
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from inky.auto import auto
from PIL import Image, ImageDraw, ImageFont

inky = auto()
w, h = inky.resolution

# Safe area margins from calibrate_safe_area.py
M_LEFT = 60
M_TOP = 35
M_RIGHT = 55
M_BOTTOM = 10

EXPECTED_W = 800
EXPECTED_H = 480

BERLIN_LAT = 52.52
BERLIN_LON = 13.41
BERLIN_TZ = "Europe/Berlin"
TRAM_REQUESTS = [
    ("Genslerstr"),
    ("Werneuchener Str"),
]
BUS_REQUESTS = [
    ("Werneuchener Str./Große-Leege-Str."),
]

ICON_DIR = Path(__file__).resolve().parent / "assets" / "weather"
ICON_FILES = {
    "clear": "clear-day.svg",
    "partly_cloudy": "cloudy-2-day.svg",
    "cloudy": "cloudy.svg",
    "fog": "fog.svg",
    "drizzle": "rainy-1.svg",
    "rain": "rainy-2.svg",
    "snow": "snowy-1.svg",
    "thunder": "thunderstorms.svg",
}

try:
    from cairosvg import svg2png
    SVG_AVAILABLE = True
except Exception:
    svg2png = None
    SVG_AVAILABLE = False

ICON_CACHE = {}
PALETTE_COLORS = [
    (255, 255, 255),  # white
    (0, 0, 0),        # black
    (255, 0, 0),      # red
    (0, 128, 0),      # green
    (0, 0, 255),      # blue
    (255, 255, 0),    # yellow
    (255, 165, 0),    # orange
]
PALETTE_IMAGE = Image.new("P", (1, 1))
_palette = []
for color in PALETTE_COLORS:
    _palette.extend(color)
_palette.extend([0, 0, 0] * (256 - len(PALETTE_COLORS)))
PALETTE_IMAGE.putpalette(_palette)

def fetch_json(url, timeout=10, retries=3, delay=10):
    req = Request(url, headers={"User-Agent": "inky-dashboard/1.0"})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(delay)


def weather_label(code):
    mapping = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Rime fog",
        51: "Drizzle",
        53: "Drizzle",
        55: "Drizzle",
        56: "Freezing drizzle",
        57: "Freezing drizzle",
        61: "Rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Freezing rain",
        71: "Snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Showers",
        81: "Showers",
        82: "Heavy showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunder",
        96: "Thunder hail",
        99: "Thunder hail",
    }
    return mapping.get(code, f"Code {code}")


def get_berlin_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={BERLIN_LAT}&longitude={BERLIN_LON}"
        f"&current=temperature_2m,weather_code"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        f"&hourly=temperature_2m"
        f"&timezone={quote(BERLIN_TZ)}"
    )
    data = fetch_json(url)
    if not data:
        return {
            "error": "Weather unavailable",
            "current_temp": None,
            "code": None,
            "min_temp": None,
            "max_temp": None,
            "rain_chance": None,
            "updated": None,
            "hourly": [],
        }
    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m")
    code = current.get("weather_code")
    updated = current.get("time")

    min_list = daily.get("temperature_2m_min") or []
    max_list = daily.get("temperature_2m_max") or []
    rain_list = daily.get("precipitation_probability_max") or []

    hourly = data.get("hourly", {})
    hourly_times = hourly.get("time") or []
    hourly_temps = hourly.get("temperature_2m") or []

    return {
        "error": None,
        "current_temp": temp,
        "code": code,
        "min_temp": min_list[0] if min_list else None,
        "max_temp": max_list[0] if max_list else None,
        "rain_chance": rain_list[0] if rain_list else None,
        "updated": updated,
        "hourly": list(zip(hourly_times, hourly_temps)),
    }


def weather_icon_key(code):
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly_cloudy"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    return None


def draw_weather_icon(img, draw, x, y, size, code, inky):
    key = weather_icon_key(code)
    if key:
        icon_name = ICON_FILES.get(key)
        if icon_name:
            icon_path = ICON_DIR / icon_name
            cache_key = (str(icon_path), size)
            if cache_key in ICON_CACHE:
                icon, alpha = ICON_CACHE[cache_key]
                img.paste(icon, (x, y + (size - icon.height) // 2), alpha)
                return
            if SVG_AVAILABLE and icon_path.exists():
                png_data = svg2png(url=str(icon_path), output_width=size)
                icon_rgba = Image.open(BytesIO(png_data)).convert("RGBA")
                alpha = icon_rgba.split()[3]
                icon_rgb = icon_rgba.convert("RGB")
                icon = icon_rgb.quantize(palette=PALETTE_IMAGE, dither=Image.NONE)
                ICON_CACHE[cache_key] = (icon, alpha)
                img.paste(icon, (x, y + (size - icon.height) // 2), alpha)
                return

    if code is None:
        draw.rectangle((x, y, x + size, y + size), outline=inky.BLACK)
        draw.line((x, y, x + size, y + size), fill=inky.BLACK)
        draw.line((x + size, y, x, y + size), fill=inky.BLACK)
        return

    cx = x + size // 2
    cy = y + size // 2
    r = size // 4

    def draw_sun(color):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, fill=color)
        rays = [
            (0, -(r + 14)),
            (0, r + 14),
            (r + 14, 0),
            (-(r + 14), 0),
            (r + 10, r + 10),
            (-(r + 10), r + 10),
            (r + 10, -(r + 10)),
            (-(r + 10), -(r + 10)),
        ]
        for dx, dy in rays:
            draw.line((cx, cy, cx + dx, cy + dy), fill=color, width=2)

    def draw_cloud(color):
        cloud_w = int(size * 0.7)
        cloud_h = int(size * 0.35)
        left = x + int(size * 0.15)
        top = y + int(size * 0.5)
        right = left + cloud_w
        bottom = top + cloud_h
        draw.ellipse((left, top - cloud_h, left + cloud_h, top + cloud_h), outline=color, fill=color)
        draw.ellipse((left + cloud_h, top - cloud_h * 1.2, left + cloud_h * 2.3, top + cloud_h * 0.8), outline=color, fill=color)
        draw.ellipse((right - cloud_h * 1.2, top - cloud_h, right + cloud_h * 0.2, top + cloud_h), outline=color, fill=color)
        draw.rectangle((left, top, right, bottom), outline=color, fill=color)

    def draw_raindrops(color):
        drop_y = y + int(size * 0.78)
        for i in range(3):
            dx = int(size * 0.2) + i * int(size * 0.18)
            draw.line((x + dx, drop_y, x + dx - 6, drop_y + 12), fill=color, width=2)

    def draw_snow(color):
        dot_y = y + int(size * 0.78)
        for i in range(3):
            dx = int(size * 0.2) + i * int(size * 0.18)
            draw.ellipse((x + dx - 3, dot_y - 3, x + dx + 3, dot_y + 3), outline=color, fill=color)

    def draw_thunder(color):
        bolt_x = x + int(size * 0.5)
        bolt_y = y + int(size * 0.62)
        points = [
            (bolt_x - 6, bolt_y),
            (bolt_x + 6, bolt_y),
            (bolt_x - 4, bolt_y + 18),
            (bolt_x + 10, bolt_y + 18),
            (bolt_x - 8, bolt_y + 40),
        ]
        draw.line(points, fill=color, width=3)

    def draw_fog(color):
        fog_y = y + int(size * 0.6)
        for i in range(3):
            draw.line((x + 6, fog_y + i * 10, x + size - 6, fog_y + i * 10), fill=color, width=2)

    if code in (0, 1):
        draw_sun(inky.RED)
    elif code in (2, 3):
        draw_sun(inky.RED)
        draw_cloud(inky.BLACK)
    elif code in (45, 48):
        draw_cloud(inky.BLACK)
        draw_fog(inky.BLACK)
    elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        draw_cloud(inky.BLACK)
        draw_raindrops(inky.BLACK)
    elif code in (71, 73, 75):
        draw_cloud(inky.BLACK)
        draw_snow(inky.BLACK)
    elif code in (95, 96, 99):
        draw_cloud(inky.BLACK)
        draw_thunder(inky.RED)
    else:
        draw_cloud(inky.BLACK)


def parse_when(when):
    if not when:
        return "--:--"
    try:
        return datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except ValueError:
        return "--:--"


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_temp_with_degree(draw, x, y, temp_value, font, inky):
    temp_text = f"{temp_value:.0f}"
    draw.text((x, y), temp_text, inky.BLACK, font=font)
    temp_w, temp_h = text_size(draw, temp_text, font)
    radius = max(5, temp_h // 6)
    circle_x = x + temp_w + 6
    circle_y = y + radius + 4
    draw.ellipse(
        (circle_x - radius, circle_y - radius, circle_x + radius, circle_y + radius),
        outline=inky.BLACK,
        fill=inky.WHITE,
    )


def temp_with_degree_width(draw, temp_value, font):
    temp_text = f"{temp_value:.0f}"
    temp_w, temp_h = text_size(draw, temp_text, font)
    radius = max(5, temp_h // 6)
    return temp_w + 6 + (radius * 2)


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


def draw_tram_table(draw, x, y, width, title, rows, fonts, inky, title_color, line_bg, line_text_color):
    font_title, font_sub, font_body, font_meta = fonts
    title_text = truncate_text(draw, title, width, font=font_body)
    draw.text((x, y), title_text, title_color, font=font_body)
    y += 20

    table_left = x
    table_right = x + width
    col_time = 70
    col_line = 50
    col_dir = table_right - table_left - col_time - col_line - 8

    draw.line((table_left, y, table_right, y), fill=inky.BLACK)
    y += 8

    if not rows:
        draw.text((table_left, y), "No departures", inky.BLACK, font=font_body)
        return y + 28

    for when, line, direction in rows[:5]:
        draw.text((table_left, y), when, inky.BLACK, font=font_body)
        line_x = table_left + col_time
        line_text = truncate_text(draw, line, col_line - 8, font=font_body)
        line_w, line_h = text_size(draw, line_text, font=font_body)
        box_w = min(col_line - 4, line_w + 10)
        box_h = line_h + 4
        box_y = y + 2
        draw.rectangle(
            (line_x, box_y, line_x + box_w, box_y + box_h),
            fill=line_bg,
            outline=line_bg,
        )
        draw.text((line_x + 5, y), line_text, line_text_color, font=font_body)
        dir_text = truncate_text(draw, direction, col_dir, font=font_body)
        draw.text((table_left + col_time + col_line, y), dir_text, inky.BLACK, font=font_body)
        y += 20

    return y + 10


def format_updated(when):
    if not when:
        return ""
    try:
        return datetime.fromisoformat(when).strftime("%H:%M")
    except ValueError:
        return when


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


def draw_temp_graph(draw, x, y, width, height, hourly, fonts, inky, label_space=14):
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

    def scale_x(idx):
        return left + int(idx * (width - 2) / max(1, len(hourly) - 1)) + 1

    def scale_y(temp):
        return top + int((t_max - temp) * (height - 2) / (t_max - t_min)) + 1

    points = []
    for idx, (_, temp) in enumerate(hourly):
        points.append((scale_x(idx), scale_y(temp)))
    if len(points) >= 2:
        draw.line(points, fill=inky.RED, width=2)
    for px, py in points[::3]:
        draw.ellipse((px - 1, py - 1, px + 1, py + 1), fill=inky.BLACK, outline=inky.BLACK)

    min_text = f"{t_min:.0f}"
    max_text = f"{t_max:.0f}"
    draw.text((left + 4, bottom - 18), min_text, inky.BLACK, font=fonts[3])
    max_w, _ = text_size(draw, max_text, fonts[3])
    draw.text((right - 4 - max_w, top + 2), max_text, inky.BLACK, font=fonts[3])

    hour_index = {}
    for idx, (hour, _) in enumerate(hourly):
        hour_index.setdefault(hour, idx)
    for hour in (0, 6, 12, 18, 23):
        if hour not in hour_index:
            continue
        hx = scale_x(hour_index[hour])
        draw.line((hx, bottom - 3, hx, bottom), fill=inky.BLACK)
        label = f"{hour:02d}"
        label_w, _ = text_size(draw, label, fonts[3])
        draw.text((hx - label_w // 2, bottom + 2), label, inky.BLACK, font=fonts[3])


def get_tram_departures(stop_query, line_filter=None, product_key="tram"):
    stops_url = (
        "https://v6.bvg.transport.rest/stops"
        f"?query={quote(stop_query)}&results=1"
    )
    stops = fetch_json(stops_url)
    if not stops:
        return stop_query, ["No stop data"]

    stop = stops[0]
    stop_id = stop.get("id")
    stop_name = stop.get("name", stop_query)
    if not stop_id:
        return stop_name, ["No stop ID"]
    stop_id = stop_id.split(":")[2] if ":" in stop_id else stop_id

    dep_url = (
        f"https://v6.bvg.transport.rest/stops/{stop_id}/departures"
        f"?duration=1440&products[{product_key}]=true"
    )
    departures = fetch_json(dep_url)
    if not departures:
        label = line_filter or "Tram"
        return stop_name, [f"No {label} data"]
    if isinstance(departures, dict):
        departures = departures.get("departures", [])
    if not isinstance(departures, list):
        label = line_filter or "Tram"
        return stop_name, [f"No {label} data"]
    lines = []
    for dep in departures:
        line = dep.get("line", {}).get("name", "Tram")
        if line_filter and line != line_filter:
            continue
        direction = dep.get("direction", "")
        when = parse_when(dep.get("when") or dep.get("plannedWhen"))
        if direction:
            lines.append(f"{when} {line} {direction}")
        else:
            lines.append(f"{when} {line}")
        if len(lines) >= 5:
            break
    if not lines:
        label = line_filter or "Tram"
        lines.append(f"No {label} departures")
    return stop_name, lines


img = Image.new("P", (w, h))
draw = ImageDraw.Draw(img)

# Warn if the detected resolution is not the expected 800x480.
if (w, h) != (EXPECTED_W, EXPECTED_H):
    print(f"warning: expected {EXPECTED_W}x{EXPECTED_H}, got {w}x{h}")

# Fonts (fall back to default bitmap font if truetype is unavailable)
try:
    font_title = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 20)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 17)
    font_temp = ImageFont.truetype("DejaVuSans.ttf", 46)
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
draw.rectangle((x0, y0, x1, y1), outline=inky.BLACK, fill=inky.WHITE)

gutter = 12
col_w = (x1 - x0 - gutter) // 2
left_col = (x0, y0, x0 + col_w, y1)
right_col = (x0 + col_w + gutter, y0, x1, y1)
divider_x = x0 + col_w + (gutter // 2)
draw.line((divider_x, y0, divider_x, y1), fill=inky.BLACK)

left_x = left_col[0] + 14
right_x = right_col[0] + 14
top_y = y0 + 14

now = datetime.now().strftime("%Y-%m-%d %H:%M")

weather = get_berlin_weather()

# Left column: tram schedule (separate tables)
line_y = top_y
table_width = left_col[2] - left_x - 14

for stop_query in TRAM_REQUESTS:
    stop_name, tram_lines = get_tram_departures(stop_query)
    rows = []
    for entry in tram_lines:
        parts = entry.split(" ", 2)
        if len(parts) == 3:
            when, line, direction = parts
        elif len(parts) == 2:
            when, line = parts
            direction = ""
        else:
            when, line, direction = "--:--", line_name, ""
        rows.append((when, line, direction))
    title = f"{stop_name}"
    line_y = draw_tram_table(
        draw,
        left_x,
        line_y,
        table_width,
        title,
        rows,
        (font_title, font_sub, font_body, font_meta),
        inky,
        inky.RED,
        inky.RED,
        inky.WHITE,
    )

# Bus table
for stop_query in BUS_REQUESTS:
    stop_name, bus_lines = get_tram_departures(stop_query, product_key="bus")
    rows = []
    for entry in bus_lines:
        parts = entry.split(" ", 2)
        if len(parts) == 3:
            when, line, direction = parts
        elif len(parts) == 2:
            when, line = parts
            direction = ""
        else:
            when, line, direction = "--:--", line_name, ""
        rows.append((when, line, direction))
    title = f"{stop_name}"
    line_y = draw_tram_table(
        draw,
        left_x,
        line_y,
        table_width,
        title,
        rows,
        (font_title, font_sub, font_body, font_meta),
        inky,
        inky.BLUE,
        inky.BLUE,
        inky.WHITE,
    )

# Right column: weather
icon_size = 192
icon_y = top_y
draw_weather_icon(img, draw, right_x, icon_y, icon_size, weather.get("code"), inky)

temp_x = right_x + icon_size + 14
current_temp = weather.get("current_temp")
if current_temp is not None:
    temp_text = f"{current_temp:.0f}"
    temp_w, temp_h = text_size(draw, temp_text, font_temp)
    temp_y = icon_y + (icon_size - temp_h) // 2
    draw_temp_with_degree(draw, temp_x, temp_y, current_temp, font_temp, inky)
else:
    temp_y = icon_y + (icon_size - 20) // 2
    draw.text((temp_x, temp_y), "No data", inky.BLACK, font=font_sub)

label = weather_label(weather.get("code")) if weather.get("code") is not None else "Unknown"
label_y = icon_y + icon_size + 10
label_w, _ = text_size(draw, label, font_sub)
label_x = right_x + ((right_col[2] - right_x - 14) - label_w) // 2
draw.text((label_x, label_y), label, inky.BLUE, font=font_sub)

min_temp = weather.get("min_temp")
max_temp = weather.get("max_temp")
minmax_y = label_y + 28
if min_temp is not None and max_temp is not None:
    min_label = "Min"
    max_label = "Max"
    min_label_w, _ = text_size(draw, min_label, font_sub)
    max_label_w, _ = text_size(draw, max_label, font_sub)
    min_temp_w = temp_with_degree_width(draw, min_temp, font_sub)
    max_temp_w = temp_with_degree_width(draw, max_temp, font_sub)
    gap = 12

    rain_chance = weather.get("rain_chance")
    rain_label = f"{rain_chance:.0f}%" if rain_chance is not None else "--"
    rain_label_w, _ = text_size(draw, rain_label, font_sub)
    rain_icon_w = 10
    rain_block_w = rain_icon_w + 6 + rain_label_w

    total_w = (
        min_label_w + 6 + min_temp_w +
        gap +
        max_label_w + 6 + max_temp_w +
        gap +
        rain_block_w
    )
    start_x = right_x + ((right_col[2] - right_x - 14) - total_w) // 2

    x = start_x
    draw.text((x, minmax_y), min_label, inky.BLACK, font=font_sub)
    x += min_label_w + 6
    draw_temp_with_degree(draw, x, minmax_y - 2, min_temp, font_sub, inky)
    x += min_temp_w + gap
    draw.text((x, minmax_y), max_label, inky.BLACK, font=font_sub)
    x += max_label_w + 6
    draw_temp_with_degree(draw, x, minmax_y - 2, max_temp, font_sub, inky)
    x += max_temp_w + gap

    icon_y = minmax_y + 8
    draw.line((x + 1, icon_y, x + 4, icon_y + 6), fill=inky.BLUE, width=2)
    draw.line((x + 6, icon_y, x + 9, icon_y + 6), fill=inky.BLUE, width=2)
    draw.ellipse((x + 2, icon_y + 5, x + 5, icon_y + 8), fill=inky.BLUE, outline=inky.BLUE)
    x += rain_icon_w + 6
    draw.text((x, minmax_y), rain_label, inky.BLACK, font=font_sub)
else:
    draw.text((right_x, minmax_y), "Min/Max unavailable", inky.BLACK, font=font_sub)

updated = format_updated(weather.get("updated")) or now
updated_text = f"Updated {updated}"
text_w, text_h = text_size(draw, updated_text, font_meta)
meta_x = right_col[2] - 14 - text_w
meta_y = right_col[3] - 14 - text_h

graph_y = minmax_y + 32
graph_height = max(40, meta_y - graph_y - 24)
graph_width = right_col[2] - right_x - 14
hourly = todays_hourly_temps(weather.get("hourly", []))
draw_temp_graph(draw, right_x, graph_y, graph_width, graph_height, hourly, (font_title, font_sub, font_body, font_meta), inky)

draw.text((meta_x, meta_y), updated_text, inky.BLACK, font=font_meta)

inky.set_image(img)
inky.show()
print("done")
