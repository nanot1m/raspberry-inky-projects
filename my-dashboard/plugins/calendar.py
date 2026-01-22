from datetime import date, datetime, time, timedelta
import os
import time as time_mod
from urllib.parse import quote

from icalendar import Calendar
import recurring_ical_events

from utils import fetch_json, text_size, truncate_text
from .weather import get_berlin_weather, draw_weather_icon


DEFAULT_CALENDAR_CONFIG = {
    "view": "week",
    "calendars": [],
    "tz": "Europe/Berlin",
    "show_calendar": False,
    "days_in_week": 7,
    "location": "Berlin",
    "min_hour": 6,
    "max_hour": 20,
}

_CAL_CACHE = {}
_CAL_CACHE_TTL = 300

CALENDAR_SCHEMA = {
    "view": {"type": "enum", "label": "View", "options": ["month", "week", "day"]},
    "tz": {"type": "string", "label": "Timezone"},
    "show_calendar": {"type": "boolean", "label": "Show Calendar Name"},
    "days_in_week": {"type": "number", "label": "Days in Week View", "min": 3, "max": 7},
    "location": {"type": "string", "label": "Location"},
    "min_hour": {"type": "number", "label": "Grid Start Hour", "min": 0, "max": 23},
    "max_hour": {"type": "number", "label": "Grid End Hour", "min": 1, "max": 24},
    "calendars": {
        "type": "list",
        "label": "Calendars",
        "help": "Add one or more sources. Fill only the fields that match the selected Type.",
        "itemType": "object",
        "itemFields": [
            {"key": "type", "label": "Type", "type": "enum", "options": ["ical_url", "google", "local"]},
            {"key": "name", "label": "Name", "type": "text", "placeholder": "Label"},
            {"key": "color", "label": "Color", "type": "enum", "options": ["black", "blue", "red", "yellow", "orange", "green", "white"]},
            {"key": "url", "label": "iCal URL", "type": "text", "placeholder": "https://.../calendar.ics"},
            {"key": "path", "label": "Local .ics path", "type": "text", "placeholder": "/path/to/calendar.ics"},
            {"key": "calendar_id", "label": "Google Calendar ID", "type": "text", "placeholder": "calendar@group.calendar.google.com"},
            {"key": "api_key", "label": "Google API key", "type": "text", "placeholder": "API key"},
        ],
    },
}


def line_height(draw, font):
    try:
        return sum(font.getmetrics())
    except AttributeError:
        return text_size(draw, "Ag", font)[1]


def color_value(inky, name):
    name = (name or "black").lower()
    return getattr(inky, name.upper(), inky.BLACK)


def text_color_for(bg_name, inky):
    name = (bg_name or "black").lower()
    if name in ("yellow", "white"):
        return inky.BLACK
    return inky.WHITE


def get_timezone(name):
    try:
        from zoneinfo import ZoneInfo
    except Exception:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def ensure_fullscreen(ctx, bbox):
    if ctx.get("layout_cols") == 1 and ctx.get("layout_rows") == 1:
        return
    raise ValueError("Calendar plugin requires a fullscreen 1x1 layout")


def normalize_datetime(dt, tzinfo):
    if isinstance(dt, datetime):
        if dt.tzinfo is None and tzinfo:
            return dt.replace(tzinfo=tzinfo)
        if tzinfo:
            return dt.astimezone(tzinfo)
        return dt
    if isinstance(dt, date):
        return datetime.combine(dt, time.min, tzinfo)
    return None


def expand_event_dates(start_date, end_date):
    if end_date <= start_date:
        return [start_date]
    days = []
    cur = start_date
    while cur <= end_date:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def parse_ical_events(ical_text, tzinfo, start_dt, end_dt, cal_name=None, color=None):
    cal = Calendar.from_ical(ical_text)
    events = []
    for event in recurring_ical_events.of(cal).between(start_dt, end_dt):
        summary = str(event.get("summary") or "Untitled")
        dtstart = event.get("dtstart")
        dtend = event.get("dtend")
        if not dtstart:
            continue
        dtstart = dtstart.dt
        dtend = dtend.dt if dtend else None
        if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
            start_date = dtstart
            end_date = dtend - timedelta(days=1) if isinstance(dtend, date) else start_date
            for day in expand_event_dates(start_date, end_date):
                events.append(
                    {
                        "start": day,
                        "end": day,
                        "title": summary,
                        "calendar": cal_name,
                        "all_day": True,
                        "color": color,
                    }
                )
            continue
        start_dt_norm = normalize_datetime(dtstart, tzinfo)
        end_dt_norm = normalize_datetime(dtend, tzinfo) if dtend else start_dt_norm
        events.append(
            {
                "start": start_dt_norm,
                "end": end_dt_norm,
                "title": summary,
                "calendar": cal_name,
                "all_day": False,
                "color": color,
            }
        )
    return events


def parse_google_events(items, tzinfo, cal_name=None, color=None):
    events = []
    for item in items:
        if item.get("status") == "cancelled":
            continue
        summary = item.get("summary") or "Untitled"
        start = item.get("start", {})
        end = item.get("end", {})
        if "date" in start:
            start_date = date.fromisoformat(start["date"])
            end_date = date.fromisoformat(end.get("date", start["date"])) - timedelta(days=1)
            for day in expand_event_dates(start_date, end_date):
                events.append(
                    {
                        "start": day,
                        "end": day,
                        "title": summary,
                        "calendar": cal_name,
                        "all_day": True,
                        "color": color,
                    }
                )
            continue
        if "dateTime" in start:
            start_dt = datetime.fromisoformat(start["dateTime"])
            end_dt = datetime.fromisoformat(end.get("dateTime", start["dateTime"]))
            start_dt = normalize_datetime(start_dt, tzinfo)
            end_dt = normalize_datetime(end_dt, tzinfo)
            events.append(
                {
                    "start": start_dt,
                    "end": end_dt,
                    "title": summary,
                    "calendar": cal_name,
                    "all_day": False,
                    "color": color,
                }
            )
    return events


def fetch_events(calendars, tzinfo, start_dt, end_dt):
    events = []
    palette = ["blue", "red", "green", "orange", "yellow", "black"]
    for idx, cal in enumerate(calendars):
        if isinstance(cal, str):
            cal = {"type": "ical_url", "url": cal}
        if not isinstance(cal, dict):
            continue
        cal_type = (cal.get("type") or "").lower()
        cal_name = cal.get("name") or ""
        color = (cal.get("color") or "").lower() or None
        if not color:
            color = palette[idx % len(palette)]
        if cal_type == "ical_url":
            url = cal.get("url")
            if not url:
                continue
            if url.startswith("webcal://"):
                url = "https://" + url[len("webcal://"):]
            cache_key = f"url:{url}"
            cached = _CAL_CACHE.get(cache_key)
            if cached and time_mod.time() - cached["ts"] < _CAL_CACHE_TTL:
                ical_text = cached["data"]
            else:
                try:
                    import urllib.request

                    ical_text = urllib.request.urlopen(url, timeout=10).read()
                except Exception:
                    ical_text = None
                _CAL_CACHE[cache_key] = {"ts": time_mod.time(), "data": ical_text}
            if isinstance(ical_text, bytes):
                ical_text = ical_text.decode("utf-8", errors="ignore")
            if ical_text:
                events.extend(parse_ical_events(ical_text, tzinfo, start_dt, end_dt, cal_name=cal_name, color=color))
        elif cal_type == "local":
            path = cal.get("path")
            if not path:
                continue
            try:
                mtime = os.path.getmtime(path)
                cache_key = f"file:{path}"
                cached = _CAL_CACHE.get(cache_key)
                if cached and cached.get("mtime") == mtime:
                    ical_text = cached["data"]
                else:
                    with open(path, "rb") as handle:
                        ical_text = handle.read().decode("utf-8", errors="ignore")
                    _CAL_CACHE[cache_key] = {"ts": time_mod.time(), "data": ical_text, "mtime": mtime}
                events.extend(parse_ical_events(ical_text, tzinfo, start_dt, end_dt, cal_name=cal_name, color=color))
            except Exception:
                continue
        elif cal_type == "google":
            calendar_id = cal.get("calendar_id")
            api_key = cal.get("api_key")
            if not calendar_id or not api_key:
                continue
            time_min = quote(start_dt.isoformat())
            time_max = quote(end_dt.isoformat())
            url = (
                "https://www.googleapis.com/calendar/v3/calendars/"
                f"{quote(calendar_id)}/events?singleEvents=true&orderBy=startTime"
                f"&timeMin={time_min}&timeMax={time_max}&key={quote(api_key)}"
            )
            payload = fetch_json(url, cache_ttl=300)
            if not payload:
                continue
            items = payload.get("items", []) if isinstance(payload, dict) else []
            events.extend(parse_google_events(items, tzinfo, cal_name=cal_name, color=color))
    return events


def group_events_by_day(events, tzinfo):
    grouped = {}
    for event in events:
        start = event.get("start")
        if isinstance(start, datetime):
            day = start.astimezone(tzinfo).date() if tzinfo else start.date()
        else:
            day = start
        grouped.setdefault(day, []).append(event)
    for day in grouped:
        grouped[day].sort(key=lambda e: (not e.get("all_day"), e.get("start")))
    return grouped


def format_time(dt):
    if isinstance(dt, datetime):
        return dt.strftime("%H:%M")
    return ""


def draw_event_card(draw, x, y, w, h, text, bg_name, inky, font, radius=3):
    bg = color_value(inky, bg_name)
    fg = text_color_for(bg_name, inky)
    border = inky.BLACK
    try:
        draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=bg, outline=border)
    except AttributeError:
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=border)
    max_width = max(0, w - 6)
    line_h = line_height(draw, font)
    max_lines = max(1, min(2, (h - 2) // max(1, line_h)))
    words = str(text).split()
    if not words:
        return
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines and current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    lines = [truncate_text(draw, line, max_width, font=font) for line in lines]
    for idx, line in enumerate(lines):
        draw.text((x + 3, y + 1 + idx * line_h), line, fg, font=font)


def draw_month_view(ctx, bbox, events_by_day, tzinfo, config):
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_meta = fonts["meta"]

    x0, y0, x1, y1 = bbox
    pad = 12
    width = x1 - x0 - (pad * 2)
    height = y1 - y0 - (pad * 2)

    today = datetime.now(tzinfo).date() if tzinfo else datetime.now().date()
    month_start = today.replace(day=1)
    weather = get_berlin_weather()
    location = (config.get("location") or "Berlin").strip()
    date_text = today.strftime("%d %b").upper()
    min_temp = weather.get("min_temp") if weather else None
    max_temp = weather.get("max_temp") if weather else None
    temp_text = ""
    if min_temp is not None and max_temp is not None:
        temp_text = f"{min_temp:.0f}° — {max_temp:.0f}°"
    draw.text((x0 + pad, y0 + pad), date_text, inky.BLACK, font=font_sub)
    right_text = " ".join(part for part in [location.upper(), temp_text] if part)
    if right_text:
        right_w, _ = text_size(draw, right_text, font_sub)
        draw.text((x1 - pad - right_w, y0 + pad), right_text, inky.BLACK, font=font_sub)

    header_h = line_height(draw, font_sub) + 4
    weekday_h = line_height(draw, font_meta) + 4
    grid_top = y0 + pad + header_h + weekday_h
    grid_h = height - header_h - weekday_h

    cols = 7
    rows = 6
    cell_w = max(1, width // cols)
    cell_h = max(1, grid_h // rows)

    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for idx, label in enumerate(weekdays):
        lx = x0 + pad + idx * cell_w + 2
        draw.text((lx, y0 + pad + header_h), label, inky.BLACK, font=font_meta)

    start_weekday = month_start.weekday()
    day_cursor = month_start - timedelta(days=start_weekday)

    for row in range(rows):
        for col in range(cols):
            cell_x = x0 + pad + col * cell_w
            cell_y = grid_top + row * cell_h
            if day_cursor.weekday() >= 5:
                draw_dither_rect(
                    draw,
                    cell_x + 1,
                    cell_y + 1,
                    cell_x + cell_w - 2,
                    cell_y + cell_h - 2,
                    inky.RED,
                )
            draw_dither_line(draw, cell_x, cell_y, cell_x + cell_w, cell_y, inky.BLACK)
            draw_dither_line(draw, cell_x, cell_y, cell_x, cell_y + cell_h, inky.BLACK)
            draw_dither_line(draw, cell_x + cell_w, cell_y, cell_x + cell_w, cell_y + cell_h, inky.BLACK)
            draw_dither_line(draw, cell_x, cell_y + cell_h, cell_x + cell_w, cell_y + cell_h, inky.BLACK)
            day_text = str(day_cursor.day)
            draw.text((cell_x + 2, cell_y + 2), day_text, inky.BLACK, font=font_meta)
            if day_cursor == today:
                draw.rectangle(
                    (cell_x + 1, cell_y + 1, cell_x + cell_w - 2, cell_y + cell_h - 2),
                    outline=inky.BLACK,
                )
            events = events_by_day.get(day_cursor, [])
            max_events = 2
            card_h = line_height(draw, font_meta) + 2
            start_y = cell_y + 14
            for event in events[:max_events]:
                title = event.get("title", "")
                if config.get("show_calendar") and event.get("calendar"):
                    title = f"{event.get('calendar')}: {title}"
                draw_event_card(
                    draw,
                    cell_x + 2,
                    start_y,
                    cell_w - 4,
                    card_h,
                    title,
                    event.get("color"),
                    inky,
                    font_meta,
                )
                start_y += card_h + 2
                if start_y + card_h > cell_y + cell_h - 2:
                    break
            remaining = max(0, len(events) - max_events)
            if remaining:
                more_text = f"+{remaining}"
                draw.text((cell_x + 2, cell_y + cell_h - card_h - 2), more_text, inky.BLACK, font=font_meta)
            day_cursor += timedelta(days=1)


def event_time_bounds(event, tzinfo, start_hour, end_hour):
    start = event.get("start")
    end = event.get("end") or start
    if not isinstance(start, datetime):
        return None
    start_local = start.astimezone(tzinfo) if tzinfo else start
    end_local = end.astimezone(tzinfo) if tzinfo else end
    if end_local <= start_local:
        end_local = start_local + timedelta(minutes=30)
    start_float = start_local.hour + (start_local.minute / 60.0)
    end_float = end_local.hour + (end_local.minute / 60.0)
    if end_float <= start_hour or start_float >= end_hour:
        return None
    start_float = max(start_float, start_hour)
    end_float = min(end_float, end_hour)
    return start_local.date(), start_float, end_float


def assign_lanes(events, tzinfo, start_hour, end_hour):
    blocks = []
    for event in events:
        bounds = event_time_bounds(event, tzinfo, start_hour, end_hour)
        if not bounds:
            continue
        day, start_float, end_float = bounds
        blocks.append({
            "event": event,
            "day": day,
            "start": start_float,
            "end": end_float,
        })
    blocks.sort(key=lambda b: (b["day"], b["start"]))
    result = []
    for day in sorted({b["day"] for b in blocks}):
        day_blocks = [b for b in blocks if b["day"] == day]
        lanes = []
        for block in day_blocks:
            placed = False
            for lane_idx, lane_end in enumerate(lanes):
                if lane_end <= block["start"]:
                    lanes[lane_idx] = block["end"]
                    block["lane"] = lane_idx
                    placed = True
                    break
            if not placed:
                block["lane"] = len(lanes)
                lanes.append(block["end"])
            block["lanes"] = len(lanes)
            result.append(block)

        times = sorted({b["start"] for b in day_blocks} | {b["end"] for b in day_blocks})
        for block in day_blocks:
            max_overlap = 1
            for idx in range(len(times) - 1):
                mid = (times[idx] + times[idx + 1]) / 2.0
                if not (block["start"] <= mid < block["end"]):
                    continue
                active = sum(1 for b in day_blocks if b["start"] <= mid < b["end"])
                max_overlap = max(max_overlap, active)
            block["lanes"] = max_overlap
            if block["lanes"] == 1:
                block["lane"] = 0
            elif block["lane"] >= block["lanes"]:
                block["lane"] = block["lane"] % block["lanes"]
    return result


def draw_dither_line(draw, x0, y0, x1, y1, color, step=2):
    if x0 == x1:
        y_start = min(y0, y1)
        y_end = max(y0, y1)
        for y in range(y_start, y_end + 1, step):
            draw.point((x0, y), fill=color)
        return
    if y0 == y1:
        x_start = min(x0, x1)
        x_end = max(x0, x1)
        for x in range(x_start, x_end + 1, step):
            draw.point((x, y0), fill=color)
        return
    draw.line((x0, y0, x1, y1), fill=color)


def draw_dither_rect(draw, x0, y0, x1, y1, color, step=2):
    for y in range(y0, y1 + 1, step):
        for x in range(x0 + (y // step) % 2, x1 + 1, step * 2):
            draw.point((x, y), fill=color)


def draw_day_view(ctx, bbox, events_by_day, tzinfo, config):
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_meta = fonts["meta"]

    x0, y0, x1, y1 = bbox
    pad = 12
    width = x1 - x0 - (pad * 2)
    height = y1 - y0 - (pad * 2)

    today = datetime.now(tzinfo).date() if tzinfo else datetime.now().date()
    weather = get_berlin_weather()
    location = (config.get("location") or "Berlin").strip()
    date_text = today.strftime("%d %b").upper()
    min_temp = weather.get("min_temp") if weather else None
    max_temp = weather.get("max_temp") if weather else None
    temp_text = ""
    if min_temp is not None and max_temp is not None:
        temp_text = f"{min_temp:.0f}° — {max_temp:.0f}°"
    draw.text((x0 + pad, y0 + pad), date_text, inky.BLACK, font=font_sub)
    right_text = " ".join(part for part in [location.upper(), temp_text] if part)
    if right_text:
        right_w, _ = text_size(draw, right_text, font_sub)
        draw.text((x1 - pad - right_w, y0 + pad), right_text, inky.BLACK, font=font_sub)

    header_h = line_height(draw, font_sub) + 4
    all_day_h = line_height(draw, font_meta) + 4
    grid_top = y0 + pad + header_h + all_day_h
    grid_bottom = y1 - pad
    grid_h = max(1, grid_bottom - grid_top)

    start_hour = config.get("min_hour", 6)
    end_hour = config.get("max_hour", 20)
    try:
        start_hour = int(start_hour)
    except (TypeError, ValueError):
        start_hour = 6
    try:
        end_hour = int(end_hour)
    except (TypeError, ValueError):
        end_hour = 20
    start_hour = max(0, min(23, start_hour))
    end_hour = max(start_hour + 1, min(24, end_hour))
    hours = end_hour - start_hour
    hour_h = max(1, grid_h // hours)

    time_col_w = text_size(draw, f"{end_hour:02d}:00", font_meta)[0] + 6
    day_x = x0 + pad + time_col_w
    day_w = max(1, width - time_col_w)

    events = events_by_day.get(today, [])
    if today.weekday() in (5, 6):
        draw_dither_rect(
            draw,
            day_x,
            grid_top,
            x1 - pad,
            grid_bottom,
            inky.RED,
        )
    all_day = [e for e in events if e.get("all_day")]
    if all_day:
        title = all_day[0].get("title", "")
        if config.get("show_calendar") and all_day[0].get("calendar"):
            title = f"{all_day[0].get('calendar')}: {title}"
        draw_event_card(
            draw,
            day_x + 2,
            y0 + pad + header_h + 1,
            day_w - 4,
            all_day_h - 2,
            title,
            all_day[0].get("color"),
            inky,
            font_meta,
        )

    for h in range(hours + 1):
        y_line = grid_top + h * hour_h
        label = f"{start_hour + h:02d}:00"
        draw.text((x0 + pad, y_line - 6), label, inky.BLACK, font=font_meta)
        draw_dither_line(draw, day_x, y_line, x1 - pad, y_line, inky.BLACK)

    timed = [e for e in events if not e.get("all_day")]
    blocks = assign_lanes(timed, tzinfo, start_hour, end_hour)
    for block in blocks:
        if block["day"] != today:
            continue
        start_float = block["start"]
        end_float = block["end"]
        lane = block["lane"]
        lanes = max(1, block.get("lanes", 1))
        lane_w = max(1, (day_w - 4) // lanes)
        x = day_x + 2 + lane * lane_w
        y = grid_top + (start_float - start_hour) * hour_h
        h = max(1, (end_float - start_float) * hour_h)
        event = block["event"]
        title = event.get("title", "")
        if config.get("show_calendar") and event.get("calendar"):
            title = f"{event.get('calendar')}: {title}"
        row_text = truncate_text(draw, title, lane_w - 4, font=font_body)
        draw_event_card(
            draw,
            int(x),
            int(y) + 1,
            lane_w - 2,
            max(line_height(draw, font_body) + 2, int(h) - 2),
            row_text,
            event.get("color"),
            inky,
            font_body,
        )


def draw_week_view(ctx, bbox, events_by_day, tzinfo, config):
    draw = ctx["draw"]
    img = ctx["img"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_meta = fonts["meta"]

    x0, y0, x1, y1 = bbox
    pad = 12
    width = x1 - x0 - (pad * 2)
    height = y1 - y0 - (pad * 2)

    today = datetime.now(tzinfo).date() if tzinfo else datetime.now().date()
    week_start = today
    days_in_week = config.get("days_in_week") or 7
    try:
        days_in_week = int(days_in_week)
    except (TypeError, ValueError):
        days_in_week = 7
    days_in_week = max(3, min(7, days_in_week))
    weather = get_berlin_weather()
    location = (config.get("location") or "Berlin").strip()
    date_text = today.strftime("%d %b").upper()
    min_temp = weather.get("min_temp") if weather else None
    max_temp = weather.get("max_temp") if weather else None
    temp_text = ""
    if min_temp is not None and max_temp is not None:
        temp_text = f"{min_temp:.0f}° — {max_temp:.0f}°"
    draw.text((x0 + pad, y0 + pad), date_text, inky.BLACK, font=font_sub)
    right_text = " ".join(part for part in [location.upper(), temp_text] if part)
    if right_text:
        right_w, _ = text_size(draw, right_text, font=font_sub)
        draw.text((x1 - pad - right_w, y0 + pad), right_text, inky.BLACK, font=font_sub)

    header_h = line_height(draw, font_sub) + 4
    day_label_h = line_height(draw, font_meta) + 4
    forecast_h = 20
    all_day_h = line_height(draw, font_meta) + 4
    grid_top = y0 + pad + header_h + day_label_h + forecast_h + all_day_h
    grid_bottom = y1 - pad
    grid_h = max(1, grid_bottom - grid_top)

    start_hour = config.get("min_hour", 6)
    end_hour = config.get("max_hour", 20)
    try:
        start_hour = int(start_hour)
    except (TypeError, ValueError):
        start_hour = 6
    try:
        end_hour = int(end_hour)
    except (TypeError, ValueError):
        end_hour = 20
    start_hour = max(0, min(23, start_hour))
    end_hour = max(start_hour + 1, min(24, end_hour))
    hours = end_hour - start_hour
    hour_h = max(1, grid_h // hours)

    time_col_w = text_size(draw, f"{end_hour:02d}:00", font_meta)[0] + 6
    day_area_w = max(1, width - time_col_w)
    col_w = max(1, day_area_w // days_in_week)
    weather = get_berlin_weather()
    daily = weather.get("daily") if weather else []
    daily_map = {}
    if daily:
        for ts, code, max_t, _min_t in daily:
            daily_map[ts] = (code, max_t, _min_t)

    for idx in range(days_in_week):
        day = week_start + timedelta(days=idx)
        col_x = x0 + pad + time_col_w + idx * col_w
        if day.weekday() >= 5:
            draw_dither_rect(
                draw,
                col_x,
                grid_top,
                col_x + col_w,
                grid_bottom,
                inky.RED,
            )
        label = day.strftime("%a %d").upper()
        label_w, _ = text_size(draw, label, font_meta)
        draw.text((col_x + max(0, (col_w - label_w) // 2), y0 + pad + header_h), label, inky.BLACK, font=font_meta)

        day_key = day.isoformat()
        if day_key in daily_map:
            code, max_t, _min_t = daily_map[day_key]
            icon_size = 24
            line_y = y0 + pad + header_h + day_label_h
            temp_text = f"{max_t:.0f}°" if max_t is not None else ""
            temp_w, _ = text_size(draw, temp_text, font_meta) if temp_text else (0, 0)
            total_w = icon_size + (4 if temp_text else 0) + temp_w
            start_x = col_x + max(0, (col_w - total_w) // 2)
            icon_x = start_x
            icon_y = line_y
            draw_weather_icon(
                img,
                draw,
                icon_x,
                icon_y,
                icon_size,
                code,
                True,
                inky,
            )
            if temp_text:
                temp_x = start_x + icon_size + 4
                temp_y = line_y + 2
                draw.text((temp_x, temp_y), temp_text, inky.BLACK, font=font_meta)

        if idx > 0:
            draw_dither_line(draw, col_x, grid_top, col_x, grid_bottom, inky.BLACK)

        events = events_by_day.get(day, [])
        all_day = [e for e in events if e.get("all_day")]
        if all_day:
            title = all_day[0].get("title", "")
            if config.get("show_calendar") and all_day[0].get("calendar"):
                title = f"{all_day[0].get('calendar')}: {title}"
            draw_event_card(
                draw,
                col_x + 1,
                y0 + pad + header_h + day_label_h + 1,
                col_w - 2,
                all_day_h - 2,
                title,
                all_day[0].get("color"),
                inky,
                font_meta,
            )

    for h in range(hours + 1):
        y_line = grid_top + h * hour_h
        label = f"{start_hour + h:02d}:00"
        draw.text((x0 + pad, y_line - 6), label, inky.BLACK, font=font_meta)
        draw_dither_line(draw, x0 + pad + time_col_w, y_line, x1 - pad, y_line, inky.BLACK)

    timed_events = [e for day in events_by_day.values() for e in day if not e.get("all_day")]
    blocks = assign_lanes(timed_events, tzinfo, start_hour, end_hour)
    for block in blocks:
        day = block["day"]
        if day < week_start or day > week_start + timedelta(days=days_in_week - 1):
            continue
        day_idx = (day - week_start).days
        col_x = x0 + pad + time_col_w + day_idx * col_w
        start_float = block["start"]
        end_float = block["end"]
        lane = block["lane"]
        lanes = max(1, block.get("lanes", 1))
        lane_w = max(1, (col_w - 4) // lanes)
        x = col_x + 2 + lane * lane_w
        y = grid_top + (start_float - start_hour) * hour_h
        h = max(1, (end_float - start_float) * hour_h)
        event = block["event"]
        title = event.get("title", "")
        if config.get("show_calendar") and event.get("calendar"):
            title = f"{event.get('calendar')}: {title}"
        row_text = truncate_text(draw, title, lane_w - 4, font=font_body)
        draw_event_card(
            draw,
            int(x),
            int(y) + 1,
            lane_w - 2,
            max(line_height(draw, font_body) + 2, int(h) - 2),
            row_text,
            event.get("color"),
            inky,
            font_body,
        )


def draw_calendar_tile(ctx, bbox, config):
    ensure_fullscreen(ctx, bbox)
    tzinfo = get_timezone(config.get("tz"))
    view = str(config.get("view") or "week").lower()
    now = datetime.now(tzinfo) if tzinfo else datetime.now()
    if view == "day":
        start_dt = datetime.combine(now.date(), time.min, tzinfo)
        end_dt = start_dt + timedelta(days=1)
    elif view == "month":
        first = now.date().replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        start_dt = datetime.combine(first, time.min, tzinfo)
        end_dt = datetime.combine(next_month, time.min, tzinfo)
    else:
        start_dt = datetime.combine(now.date(), time.min, tzinfo)
        end_dt = start_dt + timedelta(days=7)

    if ctx.get("preview_stub"):
        start_base = start_dt + timedelta(hours=8)
        events = [
            {
                "title": "Design review",
                "start": start_base,
                "end": start_base + timedelta(hours=1),
                "calendar": "Work",
                "color": "blue",
                "all_day": False,
            },
            {
                "title": "Focus time",
                "start": start_base + timedelta(hours=3),
                "end": start_base + timedelta(hours=5),
                "calendar": "Work",
                "color": "orange",
                "all_day": False,
            },
            {
                "title": "Gym",
                "start": start_base + timedelta(days=1, hours=1),
                "end": start_base + timedelta(days=1, hours=2),
                "calendar": "Personal",
                "color": "red",
                "all_day": False,
            },
            {
                "title": "All day event",
                "start": start_dt.date(),
                "end": start_dt.date(),
                "calendar": "Personal",
                "color": "yellow",
                "all_day": True,
            },
        ]
    else:
        calendars = config.get("calendars") or []
        if not calendars:
            raise ValueError("No calendars configured")
        events = fetch_events(calendars, tzinfo, start_dt, end_dt)
    events_by_day = group_events_by_day(events, tzinfo)

    if view == "month":
        draw_month_view(ctx, bbox, events_by_day, tzinfo, config)
    elif view == "day":
        draw_day_view(ctx, bbox, events_by_day, tzinfo, config)
    else:
        draw_week_view(ctx, bbox, events_by_day, tzinfo, config)
