from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from utils import PALETTE_IMAGE, fetch_json, text_size, truncate_text

try:
    from cairosvg import svg2png
    SVG_AVAILABLE = True
except Exception:
    svg2png = None
    SVG_AVAILABLE = False

ICON_CACHE = {}
BASE_DIR = Path(__file__).resolve().parents[1]
ICON_DIR = BASE_DIR / "assets" / "weather-icons"
ICON_FILES = {
    "clear_day": "wi-day-sunny.svg",
    "clear_night": "wi-night-clear.svg",
    "partly_cloudy_day": "wi-day-cloudy.svg",
    "partly_cloudy_night": "wi-night-alt-partly-cloudy.svg",
    "cloudy": "wi-cloudy.svg",
    "fog_day": "wi-day-fog.svg",
    "fog_night": "wi-fog.svg",
    "drizzle_day": "wi-day-sprinkle.svg",
    "drizzle_night": "wi-night-alt-sprinkle.svg",
    "freezing_drizzle_day": "wi-day-sleet.svg",
    "freezing_drizzle_night": "wi-night-sleet.svg",
    "rain_day": "wi-day-rain-wind.svg",
    "rain_night": "wi-night-rain-wind.svg",
    "rain_heavy_day": "wi-day-rain-wind.svg",
    "rain_heavy_night": "wi-night-rain-wind.svg",
    "freezing_rain_day": "wi-day-sleet.svg",
    "freezing_rain_night": "wi-night-sleet.svg",
    "snow_day": "wi-day-snow.svg",
    "snow_night": "wi-night-alt-snow-wind.svg",
    "snow_heavy_day": "wi-snow-wind.svg",
    "snow_heavy_night": "wi-night-alt-snow-wind.svg",
    "snow_showers_day": "wi-day-snow.svg",
    "snow_showers_night": "wi-night-alt-snow-wind.svg",
    "snow_grains": "wi-snowflake-cold.svg",
    "hail": "wi-hail.svg",
    "thunder_day": "wi-thunderstorm.svg",
    "thunder_night": "wi-night-alt-lightning.svg",
    "thunder_hail_day": "wi-thunderstorm.svg",
    "thunder_hail_night": "wi-night-alt-lightning.svg",
}

DEFAULT_LAT = 52.52
DEFAULT_LON = 13.41
DEFAULT_TZ = "Europe/Berlin"

DEFAULT_WEATHER_CONFIG = {
    "lat": DEFAULT_LAT,
    "lon": DEFAULT_LON,
    "tz": DEFAULT_TZ,
    "variant": "split",
    "city": "Berlin",
}

WEATHER_SCHEMA = {
    "lat": {"type": "number", "label": "Latitude", "step": 0.0001},
    "lon": {"type": "number", "label": "Longitude", "step": 0.0001},
    "tz": {"type": "string", "label": "Timezone"},
    "variant": {"type": "enum", "label": "Layout", "options": ["split", "card", "panel"]},
    "city": {"type": "string", "label": "City"},
}


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


def get_berlin_weather(lat=DEFAULT_LAT, lon=DEFAULT_LON, tz=DEFAULT_TZ):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,weather_code,windspeed_10m,is_day"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
        f"&hourly=temperature_2m"
        f"&timezone={quote(tz)}"
    )
    data = fetch_json(url, cache_ttl=300)
    if not data:
        return {
            "error": "Weather unavailable",
            "current_temp": None,
            "code": None,
            "min_temp": None,
            "max_temp": None,
            "rain_chance": None,
            "wind_speed": None,
            "is_day": None,
            "updated": None,
            "hourly": [],
        }
    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    code = current.get("weather_code")
    is_day = current.get("is_day")
    wind_speed = current.get("windspeed_10m")
    updated = current.get("time")

    min_list = daily.get("temperature_2m_min") or []
    max_list = daily.get("temperature_2m_max") or []
    rain_list = daily.get("precipitation_probability_max") or []
    daily_codes = daily.get("weather_code") or []
    daily_times = daily.get("time") or []

    hourly = data.get("hourly", {})
    hourly_times = hourly.get("time") or []
    hourly_temps = hourly.get("temperature_2m") or []

    return {
        "error": None,
        "current_temp": temp,
        "feels_temp": feels,
        "code": code,
        "min_temp": min_list[0] if min_list else None,
        "max_temp": max_list[0] if max_list else None,
        "rain_chance": rain_list[0] if rain_list else None,
        "wind_speed": wind_speed,
        "is_day": is_day,
        "updated": updated,
        "hourly": list(zip(hourly_times, hourly_temps)),
        "daily": list(zip(daily_times, daily_codes, max_list, min_list)),
    }


def get_stub_weather():
    return {
        "error": None,
        "current_temp": 2,
        "feels_temp": 1,
        "code": 1,
        "min_temp": -3,
        "max_temp": 4,
        "rain_chance": 20,
        "wind_speed": 10,
        "is_day": 1,
        "updated": None,
        "hourly": [],
        "daily": [
            ("Tue", 1, 3, -2),
            ("Wed", 2, 4, -1),
            ("Thu", 3, 5, 0),
            ("Fri", 45, 2, -1),
            ("Sat", 61, 1, -2),
        ],
    }


def weather_icon_key(code, is_day=None):
    is_day = True if is_day is None else bool(is_day)
    if code in (0, 1):
        return "clear_day" if is_day else "clear_night"
    if code == 2:
        return "partly_cloudy_day" if is_day else "partly_cloudy_night"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog_day" if is_day else "fog_night"
    if code in (51, 53, 55):
        return "drizzle_day" if is_day else "drizzle_night"
    if code in (56, 57):
        return "freezing_drizzle_day" if is_day else "freezing_drizzle_night"
    if code in (61, 63):
        return "rain_day" if is_day else "rain_night"
    if code == 65:
        return "rain_heavy_day" if is_day else "rain_heavy_night"
    if code in (66, 67):
        return "freezing_rain_day" if is_day else "freezing_rain_night"
    if code in (71, 73):
        return "snow_day" if is_day else "snow_night"
    if code == 75:
        return "snow_heavy_day" if is_day else "snow_heavy_night"
    if code == 77:
        return "snow_grains"
    if code in (80, 81):
        return "drizzle_day" if is_day else "drizzle_night"
    if code == 82:
        return "rain_heavy_day" if is_day else "rain_heavy_night"
    if code == 85:
        return "snow_showers_day" if is_day else "snow_showers_night"
    if code == 86:
        return "snow_heavy_day" if is_day else "snow_heavy_night"
    if code == 95:
        return "thunder_day" if is_day else "thunder_night"
    if code in (96, 99):
        return "thunder_hail_day" if is_day else "thunder_hail_night"
    return None


def quantize_to_palette(img):
    return img.convert("RGB").quantize(palette=PALETTE_IMAGE, dither=Image.NONE)


def load_svg_icon(icon_name, size):
    cache_key = (icon_name, size)
    if cache_key in ICON_CACHE:
        return ICON_CACHE[cache_key]
    if not SVG_AVAILABLE:
        return None
    icon_path = ICON_DIR / icon_name
    if not icon_path.exists():
        return None
    png_data = svg2png(url=str(icon_path), output_width=size)
    icon_rgba = Image.open(BytesIO(png_data)).convert("RGBA")
    alpha = icon_rgba.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        icon_rgba = icon_rgba.crop(bbox)
        alpha = icon_rgba.split()[3]
        w, h = icon_rgba.size
        scale = size / max(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        icon_rgba = icon_rgba.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        paste_x = (size - new_w) // 2
        paste_y = (size - new_h) // 2
        canvas.paste(icon_rgba, (paste_x, paste_y), icon_rgba)
        icon_rgba = canvas
        alpha = icon_rgba.split()[3]
    icon = quantize_to_palette(icon_rgba)
    ICON_CACHE[cache_key] = (icon, alpha)
    return ICON_CACHE[cache_key]


def draw_weather_icon(img, draw, x, y, size, code, is_day, inky):
    key = weather_icon_key(code, is_day)
    if key:
        icon_name = ICON_FILES.get(key)
        if icon_name:
            cached = load_svg_icon(icon_name, size)
            if cached:
                icon, alpha = cached
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

    sun_color = getattr(inky, "ORANGE", inky.YELLOW)

    if code in (0, 1):
        draw_sun(sun_color)
    elif code in (2, 3):
        draw_sun(sun_color)
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


def draw_temp_with_degree(draw, x, y, temp_value, font, inky):
    temp_text = f"{temp_value:.0f}"
    draw.text((x, y), temp_text, inky.BLACK, font=font)
    temp_w, _ = text_size(draw, temp_text, font)
    degree_text = "°"
    degree_x = x + temp_w + 2
    draw.text((degree_x, y), degree_text, inky.BLACK, font=font)


def draw_dotted_line(draw, x, y0, y1, color, dash=6, gap=4, width=1):
    y = y0
    while y < y1:
        draw.line((x, y, x, min(y + dash, y1)), fill=color, width=width)
        y += dash + gap


def draw_raindrop(draw, x, y, size, color):
    draw.ellipse((x, y, x + size, y + size), outline=color, fill=color)
    tip = (x + size // 2, y - size)
    draw.polygon([tip, (x, y + size // 2), (x + size, y + size // 2)], outline=color, fill=color)


def line_height(draw, font):
    try:
        return sum(font.getmetrics())
    except AttributeError:
        return text_size(draw, "Ag", font)[1]


def draw_weather_tile_split(ctx, bbox, config):
    img = ctx["img"]
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_temp = fonts["temp"]
    font_meta = fonts["meta"]
    now = ctx["now"]

    pad = 12
    x0, y0, x1, y1 = bbox
    wx = x0 + pad
    wy = y0 + pad
    w_width = x1 - x0 - (pad * 2)
    w_height = y1 - y0 - (pad * 2)

    if ctx.get("preview_stub"):
        weather = get_stub_weather()
    else:
        weather = get_berlin_weather(
            lat=config.get("lat", DEFAULT_LAT),
            lon=config.get("lon", DEFAULT_LON),
            tz=config.get("tz", DEFAULT_TZ),
        )

    left_col_w = max(0, int(w_width * 0.45))
    gutter = 12
    right_x = wx + left_col_w + gutter
    right_w = max(0, x1 - pad - right_x)

    # Left side: icon + label
    icon_size = min(110, max(48, w_height - 70), max(0, left_col_w - 8))
    icon_x = wx + 4
    icon_y = wy + 4
    draw_weather_icon(
        img,
        draw,
        icon_x,
        icon_y,
        icon_size,
        weather.get("code"),
        weather.get("is_day"),
        inky,
    )

    label = weather_label(weather.get("code")) if weather.get("code") is not None else "Unknown"
    label_max_w = max(0, left_col_w - 8)
    label = truncate_text(draw, label, label_max_w, font_body)
    label_w, _ = text_size(draw, label, font_body)
    label_y = icon_y + icon_size + 8
    label_x = icon_x + max(0, (icon_size - label_w) // 2)
    draw.text((label_x, label_y), label, inky.BLACK, font=font_body)

    # Right side: big temp + range + extras
    current_temp = weather.get("current_temp")
    if current_temp is not None:
        temp_text = f"{current_temp:.0f}"
        temp_h = line_height(draw, font_temp)
        body_line_h = line_height(draw, font_body)
        meta_line_h = line_height(draw, font_meta)
        min_temp = weather.get("min_temp")
        max_temp = weather.get("max_temp")
        if min_temp is not None and max_temp is not None:
            range_text = f"{min_temp:.0f}° · {max_temp:.0f}°"
        else:
            range_text = "-- - --"
        rain_chance = weather.get("rain_chance")
        rain_text = None
        if rain_chance is not None:
            rain_text = f"Rain {rain_chance:.0f}%"
        temp_y = wy + 4
        draw_temp_with_degree(draw, right_x, temp_y, current_temp, font_temp, inky)

        range_y = temp_y + temp_h + 8
        draw.text((right_x, range_y), range_text, inky.BLACK, font=font_body)

        if rain_text:
            drop_size = 8
            rain_y = range_y + body_line_h + 6
            try:
                ascent, _ = font_meta.getmetrics()
            except AttributeError:
                ascent = meta_line_h
            text_y = rain_y
            baseline_y = text_y + ascent
            drop_y = baseline_y - drop_size + 2
            draw_raindrop(draw, right_x, drop_y, drop_size, inky.BLACK)
            draw.text((right_x + drop_size + 6, text_y), rain_text, inky.BLACK, font=font_meta)
    else:
        empty_text = "No data"
        _, empty_h = text_size(draw, empty_text, font_sub)
        temp_y = wy + max(0, (w_height - empty_h) // 2)
        draw.text((right_x, temp_y), "No data", inky.BLACK, font=font_sub)
    _ = now


def draw_weather_tile_card(ctx, bbox, config):
    img = ctx["img"]
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_temp = fonts["temp"]
    font_meta = fonts["meta"]
    now = ctx["now"]

    pad = 12
    x0, y0, x1, y1 = bbox
    wx = x0 + pad
    wy = y0 + pad
    w_width = x1 - x0 - (pad * 2)
    w_height = y1 - y0 - (pad * 2)

    if ctx.get("preview_stub"):
        weather = get_stub_weather()
    else:
        weather = get_berlin_weather(
            lat=config.get("lat", DEFAULT_LAT),
            lon=config.get("lon", DEFAULT_LON),
            tz=config.get("tz", DEFAULT_TZ),
        )

    left_w = max(0, int(w_width * 0.38))
    right_w = max(0, int(w_width * 0.26))
    gutter = 10
    center_w = max(0, w_width - left_w - right_w - (gutter * 2))
    left_x = wx + 4
    center_x = left_x + left_w + gutter
    right_x = center_x + center_w + gutter

    meta_line_h = line_height(draw, font_meta)
    body_line_h = line_height(draw, font_body)
    sub_line_h = line_height(draw, font_sub)
    forecast_h = max(44, meta_line_h + body_line_h + 18)
    content_bottom = y1 - pad - forecast_h

    city = str(config.get("city") or "").strip() or "Weather"
    city_text = truncate_text(draw, city.upper(), left_w, font_sub)
    city_y = wy + 4
    draw.text((left_x, city_y), city_text, inky.BLACK, font=font_sub)

    day_text = datetime.now().strftime("%A").upper()
    day_text = truncate_text(draw, day_text, left_w, font_body)
    day_y = city_y + sub_line_h + 6
    draw.text((left_x, day_y), day_text, inky.BLACK, font=font_body)

    now_dt = datetime.now()
    date_text = f"{now_dt.day} {now_dt.strftime('%b')}"
    date_y = day_y + body_line_h + 4
    draw.text((left_x, date_y), date_text, inky.BLACK, font=font_meta)

    left_y = date_y + meta_line_h + 8
    _ = weather.get("wind_speed")

    rain_chance = weather.get("rain_chance")
    if rain_chance is not None:
        drop_size = 6
        rain_text = f"{rain_chance:.0f}%"
        try:
            ascent, _ = font_meta.getmetrics()
        except AttributeError:
            ascent = meta_line_h
        baseline_y = left_y + ascent
        drop_y = baseline_y - drop_size + 1
        draw_raindrop(draw, left_x, drop_y, drop_size, inky.BLACK)
        draw.text((left_x + drop_size + 6, left_y), rain_text, inky.BLACK, font=font_meta)

    icon_size = min(96, max(48, center_w), max(48, content_bottom - wy - 40))
    desired_center = x0 + (x1 - x0) // 2
    min_icon_x = center_x
    max_icon_x = max(min_icon_x, right_x - 6 - icon_size)
    icon_x = max(min_icon_x, min(desired_center - icon_size // 2, max_icon_x))
    icon_y = wy + max(6, (content_bottom - wy - icon_size) // 2 - 2)
    draw_weather_icon(
        img,
        draw,
        icon_x,
        icon_y,
        icon_size,
        weather.get("code"),
        weather.get("is_day"),
        inky,
    )

    label = weather_label(weather.get("code")) if weather.get("code") is not None else "Unknown"
    label = truncate_text(draw, label.upper(), center_w, font_body)
    label_w, _ = text_size(draw, label, font_body)
    label_y = icon_y + icon_size + 2
    label_y = min(label_y, content_bottom - body_line_h)
    label_x = icon_x + max(0, (icon_size - label_w) // 2)
    draw.text((label_x, label_y), label, inky.BLACK, font=font_body)

    current_temp = weather.get("current_temp")
    if current_temp is not None:
        temp_text = f"{current_temp:.0f}"
        temp_h = line_height(draw, font_temp)
        temp_y = wy + max(6, (content_bottom - wy - temp_h) // 2 - 6)
        draw_temp_with_degree(draw, right_x, temp_y, current_temp, font_temp, inky)

        min_temp = weather.get("min_temp")
        max_temp = weather.get("max_temp")
        if min_temp is not None and max_temp is not None:
            range_text = f"{min_temp:.0f}° · {max_temp:.0f}°"
        else:
            range_text = "-- - --"
        range_w, _ = text_size(draw, range_text, font_meta)
        range_x = x1 - pad - range_w
        range_y = wy + 6
        draw.text((range_x, range_y), range_text, inky.BLACK, font=font_meta)
    else:
        empty_text = "No data"
        _, empty_h = text_size(draw, empty_text, font_sub)
        temp_y = wy + max(0, (w_height - empty_h) // 2)
        draw.text((right_x, temp_y), "No data", inky.BLACK, font=font_sub)

    _ = now

    daily = weather.get("daily") or []
    if daily:
        divider_y = y1 - pad - forecast_h
        draw.line((wx, divider_y, x1 - pad, divider_y), fill=inky.BLACK, width=1)
        forecast_y0 = divider_y + 8
        forecast_y1 = y1 - pad - 8
        slots = min(5, len(daily))
        if slots > 0:
            col_w = max(1, w_width // slots)
            for idx in range(slots):
                entry = daily[idx]
                max_t = None
                _min_t = None
                day_label = "--"
                if isinstance(entry, dict):
                    dt = entry.get("date")
                    code = entry.get("code")
                    max_t = entry.get("max_temp")
                    _min_t = entry.get("min_temp")
                    if isinstance(dt, datetime):
                        day_label = dt.strftime("%a").upper()
                else:
                    ts, code, max_t, _min_t = entry
                    try:
                        day_label = datetime.fromisoformat(ts).strftime("%a").upper()
                    except Exception:
                        day_label = str(ts).upper() if ts else "--"
                col_x = wx + idx * col_w
                day_w, _ = text_size(draw, day_label, font_meta)
                day_x = col_x + max(0, (col_w - day_w) // 2)
                draw.text((day_x, forecast_y0), day_label, inky.BLACK, font=font_meta)

                icon_size_sm = 32
                icon_x = col_x + max(0, (col_w - icon_size_sm) // 2)
                icon_y = forecast_y0 + meta_line_h + 4
                draw_weather_icon(
                    img,
                    draw,
                    icon_x,
                    icon_y,
                    icon_size_sm,
                    code,
                    True,
                    inky,
                )

                if max_t is not None and _min_t is not None:
                    temp_text = f"{max_t:.0f}°/{_min_t:.0f}°"
                elif max_t is not None:
                    temp_text = f"{max_t:.0f}°"
                elif _min_t is not None:
                    temp_text = f"{_min_t:.0f}°"
                else:
                    temp_text = None
                if temp_text:
                    temp_w, _ = text_size(draw, temp_text, font_meta)
                    temp_x = col_x + max(0, (col_w - temp_w) // 2)
                    temp_y = icon_y + icon_size_sm + 4
                    if temp_y + meta_line_h <= forecast_y1:
                        draw.text((temp_x, temp_y), temp_text, inky.BLACK, font=font_meta)


def draw_weather_tile_panel(ctx, bbox, config):
    img = ctx["img"]
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_temp = fonts["temp"]
    font_meta = fonts["meta"]
    now = ctx["now"]

    pad = 12
    x0, y0, x1, y1 = bbox
    wx = x0 + pad
    wy = y0 + pad
    w_width = x1 - x0 - (pad * 2)
    w_height = y1 - y0 - (pad * 2)

    if ctx.get("preview_stub"):
        weather = get_stub_weather()
    else:
        weather = get_berlin_weather(
            lat=config.get("lat", DEFAULT_LAT),
            lon=config.get("lon", DEFAULT_LON),
            tz=config.get("tz", DEFAULT_TZ),
        )

    meta_line_h = line_height(draw, font_meta)
    body_line_h = line_height(draw, font_body)
    top_h = max(34, meta_line_h + meta_line_h + 10)
    band_h = max(24, meta_line_h + 8)
    content_top = wy + top_h
    content_bottom = y1 - pad - band_h
    right_x = wx + max(0, int(w_width * 0.55))

    label = weather_label(weather.get("code")) if weather.get("code") is not None else "Unknown"
    label = truncate_text(draw, label, max(0, right_x - wx - 36), font_meta)
    icon_size = 44
    icon_x = wx
    icon_y = wy + 4
    draw_weather_icon(
        img,
        draw,
        icon_x,
        icon_y,
        icon_size,
        weather.get("code"),
        weather.get("is_day"),
        inky,
    )
    draw.text((icon_x + icon_size + 8, wy + 8), label, inky.BLACK, font=font_meta)

    now_dt = datetime.now()
    date_text = f"{now_dt.day} {now_dt.strftime('%b')}"
    date_text = date_text.upper()
    date_w, _ = text_size(draw, date_text, font_meta)
    draw.text((x1 - pad - date_w, wy + 6), date_text, inky.BLACK, font=font_meta)

    current_temp = weather.get("current_temp")
    if current_temp is not None:
        temp_text = f"{current_temp:.0f}"
        temp_h = line_height(draw, font_temp)
        temp_y = content_top + max(0, (content_bottom - content_top - temp_h) // 2 - 2)
        draw_temp_with_degree(draw, wx, temp_y, current_temp, font_temp, inky)

        min_temp = weather.get("min_temp")
        max_temp = weather.get("max_temp")
        if min_temp is not None and max_temp is not None:
            range_text = f"{min_temp:.0f}° / {max_temp:.0f}°"
        else:
            range_text = "-- / --"
        range_y = temp_y + temp_h + 4
        draw.text((wx, range_y), range_text, inky.BLACK, font=font_meta)
    else:
        empty_text = "No data"
        _, empty_h = text_size(draw, empty_text, font_sub)
        temp_y = content_top + max(0, (content_bottom - content_top - empty_h) // 2)
        draw.text((wx, temp_y), "No data", inky.BLACK, font=font_sub)

    city = str(config.get("city") or "").strip() or "Weather"
    city_text = truncate_text(draw, city, max(0, x1 - pad - right_x), font_body)
    city_w, city_h = text_size(draw, city_text, font_body)
    city_y = content_top + max(0, (content_bottom - content_top - body_line_h) // 2)
    draw.text((x1 - pad - city_w, city_y), city_text, inky.BLACK, font=font_body)

    band_y0 = y1 - pad - band_h
    band_y1 = y1 - pad
    band_color = inky.BLUE
    draw.rectangle((wx, band_y0, x1 - pad, band_y1), fill=band_color)

    rain_chance = weather.get("rain_chance")
    band_text = []
    if rain_chance is not None:
        band_text.append(f"Rain {rain_chance:.0f}%")
    if band_text:
        band_msg = " · ".join(band_text)
    else:
        band_msg = "Forecast"
    band_msg = truncate_text(draw, band_msg, max(0, w_width - 8), font_meta)
    draw.text((wx + 4, band_y0 + 4), band_msg, inky.WHITE, font=font_meta)

    _ = now


def draw_weather_tile(ctx, bbox, config):
    variant = str(config.get("variant") or "split").lower()
    if variant == "card":
        draw_weather_tile_card(ctx, bbox, config)
    elif variant == "panel":
        draw_weather_tile_panel(ctx, bbox, config)
    else:
        draw_weather_tile_split(ctx, bbox, config)
