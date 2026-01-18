from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from utils import PALETTE_IMAGE, fetch_json, format_updated, text_size

try:
    from cairosvg import svg2png
    SVG_AVAILABLE = True
except Exception:
    svg2png = None
    SVG_AVAILABLE = False

ICON_CACHE = {}
ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "weather-icons"
ICON_FILES = {
    "clear": "wi-day-sunny.svg",
    "partly_cloudy": "wi-day-cloudy.svg",
    "cloudy": "wi-cloudy.svg",
    "fog": "wi-fog.svg",
    "drizzle": "wi-sprinkle.svg",
    "rain": "wi-rain.svg",
    "rain_heavy": "wi-rain-wind.svg",
    "freezing_drizzle": "wi-sleet.svg",
    "freezing_rain": "wi-rain-mix.svg",
    "snow": "wi-snow.svg",
    "snow_heavy": "wi-snow-wind.svg",
    "snow_showers": "wi-snow.svg",
    "hail": "wi-hail.svg",
    "thunder": "wi-thunderstorm.svg",
}

DEFAULT_LAT = 52.52
DEFAULT_LON = 13.41
DEFAULT_TZ = "Europe/Berlin"

DEFAULT_WEATHER_CONFIG = {
    "lat": DEFAULT_LAT,
    "lon": DEFAULT_LON,
    "tz": DEFAULT_TZ,
    "pad": 12,
}

WEATHER_SCHEMA = {
    "lat": {"type": "number", "label": "Latitude", "step": 0.0001},
    "lon": {"type": "number", "label": "Longitude", "step": 0.0001},
    "tz": {"type": "string", "label": "Timezone"},
    "pad": {"type": "number", "label": "Padding", "min": 0, "max": 30},
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
        f"&current=temperature_2m,apparent_temperature,weather_code"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
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
            "updated": None,
            "hourly": [],
        }
    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
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
        "feels_temp": feels,
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
    if code in (51, 53, 55):
        return "drizzle"
    if code in (56, 57):
        return "freezing_drizzle"
    if code in (61, 63, 80, 81):
        return "rain"
    if code in (65, 82):
        return "rain_heavy"
    if code in (66, 67):
        return "freezing_rain"
    if code in (71, 73):
        return "snow"
    if code in (75, 77):
        return "snow_heavy"
    if code in (85, 86):
        return "snow_showers"
    if code in (96, 99):
        return "hail"
    if code == 95:
        return "thunder"
    return None


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
    icon_rgb = icon_rgba.convert("RGB")
    icon = icon_rgb.quantize(palette=PALETTE_IMAGE, dither=Image.NONE)
    ICON_CACHE[cache_key] = (icon, alpha)
    return ICON_CACHE[cache_key]


def draw_weather_icon(img, draw, x, y, size, code, inky):
    key = weather_icon_key(code)
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


def draw_temp_with_degree(draw, x, y, temp_value, font, inky):
    temp_text = f"{temp_value:.0f}"
    draw.text((x, y), temp_text, inky.BLACK, font=font)
    temp_w, temp_h = text_size(draw, temp_text, font)
    radius = max(5, temp_h // 5)
    circle_x = x + temp_w + 6
    circle_y = y + radius + 4
    draw.ellipse(
        (circle_x - radius, circle_y - radius, circle_x + radius, circle_y + radius),
        outline=inky.BLACK,
        fill=inky.WHITE,
    )


def draw_weather_tile(ctx, bbox, config):
    img = ctx["img"]
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_temp = fonts["temp"]
    font_meta = fonts["meta"]
    now = ctx["now"]

    pad = config.get("pad", 12)
    if pad is None:
        pad = 12
    else:
        pad = int(pad)
    x0, y0, x1, y1 = bbox
    wx = x0 + pad
    wy = y0 + pad
    w_height = y1 - y0 - (pad * 2)

    weather = get_berlin_weather(
        lat=config.get("lat", DEFAULT_LAT),
        lon=config.get("lon", DEFAULT_LON),
        tz=config.get("tz", DEFAULT_TZ),
    )

    # Left side: Weather icon
    icon_size = min(100, w_height - 20)
    icon_x = wx + 10
    icon_y = wy + (w_height - icon_size) // 2
    draw_weather_icon(img, draw, icon_x, icon_y, icon_size, weather.get("code"), inky)

    # Vertical separator line
    separator_x = wx + icon_size + 30
    separator_y0 = wy + 10
    separator_y1 = wy + w_height - 10
    draw.line((separator_x, separator_y0, separator_x, separator_y1), fill=inky.BLACK, width=1)

    # Right side: Temperature and info
    info_x = separator_x + 15
    current_temp = weather.get("current_temp")
    if current_temp is not None:
        temp_text = f"{current_temp:.0f}"
        temp_w, temp_h = text_size(draw, temp_text, font_temp)
        temp_y = wy + 10
        draw_temp_with_degree(draw, info_x, temp_y, current_temp, font_temp, inky)

        label = weather_label(weather.get("code")) if weather.get("code") is not None else "Unknown"
        label_y = temp_y + temp_h + 16
        draw.text((info_x, label_y), label, inky.BLACK, font=font_sub)

        min_temp = weather.get("min_temp")
        max_temp = weather.get("max_temp")
        if min_temp is not None and max_temp is not None:
            range_text = f"{min_temp:.0f}° - {max_temp:.0f}°"
        else:
            range_text = "-- - --"
        range_y = label_y + 32
        draw.text((info_x, range_y), range_text, inky.BLACK, font=font_body)

        rain_chance = weather.get("rain_chance")
        if rain_chance is not None:
            rain_text = f"Rain {rain_chance:.0f}%"
            rain_y = range_y + 32
            draw.text((info_x, rain_y), rain_text, inky.BLACK, font=font_meta)
    else:
        temp_y = wy + w_height // 2
        draw.text((info_x, temp_y), "No data", inky.BLACK, font=font_sub)

    updated = format_updated(weather.get("updated")) or now
    updated_text = f"Updated {updated}"
    text_w, text_h = text_size(draw, updated_text, font_meta)
    meta_x = x1 - 6 - text_w
    meta_y = y1 - 6 - text_h
    draw.text((meta_x, meta_y), updated_text, inky.BLACK, font=font_meta)
