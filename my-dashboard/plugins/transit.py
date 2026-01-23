import time
from datetime import datetime
from urllib.parse import quote

from utils import fetch_json, text_size, truncate_text

_LAST_DEPARTURES = {}

DEFAULT_TRANSIT_CONFIG = {
    "stops": ["Genslerstr", "Werneuchener Str"],
    "title_color": "red",
    "line_bg": "red",
    "line_text_color": "white",
    "line_badge_y_offset": 0,
    "max_rows_per_group": 4,
    "pad": 12,
}

TRANSIT_SCHEMA = {
    "stops": {"type": "list", "label": "Stops", "itemType": "string"},
    "title_color": {"type": "enum", "label": "Title Color", "options": ["red", "blue", "black"]},
    "line_bg": {"type": "enum", "label": "Line Badge", "options": ["red", "blue", "black"]},
    "line_text_color": {"type": "enum", "label": "Line Text", "options": ["white", "black"]},
    "line_badge_y_offset": {"type": "number", "label": "Line Badge Y Offset", "min": -10, "max": 10},
    "max_rows_per_group": {"type": "number", "label": "Max Rows Per Direction", "min": 1, "max": 12},
    "pad": {"type": "number", "label": "Padding", "min": 0, "max": 30},
}


def parse_departure_time(when):
    if not when:
        return "--:--", None
    try:
        dt = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%H:%M"), dt.timestamp()
    except ValueError:
        return "--:--", None


def normalize_rows(rows):
    normalized = []
    for row in rows or []:
        if len(row) == 5:
            normalized.append(row)
        elif len(row) == 4:
            when, line, group_direction, display_direction = row
            normalized.append((when, None, line, group_direction, display_direction))
        elif len(row) == 1:
            normalized.append((row[0], None, "", "", ""))
    return normalized


def get_tram_departures(stop_query, line_filter=None):
    stops_url = (
        "https://v6.bvg.transport.rest/stops"
        f"?query={quote(stop_query)}&results=1"
    )
    stops = fetch_json(stops_url, cache_ttl=60)
    if not stops:
        cached = _LAST_DEPARTURES.get(stop_query)
        if cached:
            return cached["stop_name"], normalize_rows(cached["rows"])
        return stop_query, [("No stop data", None, "", "", "")]

    stop = stops[0]
    stop_id = stop.get("id")
    stop_name = stop.get("name", stop_query)
    if not stop_id:
        return stop_name, [("No stop ID", None, "", "", "")]
    stop_id = stop_id.split(":")[2] if ":" in stop_id else stop_id

    dep_url = (
        f"https://v6.bvg.transport.rest/stops/{stop_id}/departures"
        "?duration=1440&stopovers=true"
    )
    departures = fetch_json(dep_url, cache_ttl=60)
    if not departures:
        cached = _LAST_DEPARTURES.get(stop_query)
        if cached:
            return cached["stop_name"], normalize_rows(cached["rows"])
        label = line_filter or "Tram"
        return stop_name, [(f"No {label} data", None, "", "", "")]
    if isinstance(departures, dict):
        departures = departures.get("departures", [])
    if not isinstance(departures, list):
        label = line_filter or "Tram"
        return stop_name, [(f"No {label} data", None, "", "", "")]
    rows = []
    def next_stop_name(stopovers, current_stop_id):
        if not stopovers:
            return None
        seen_current = False
        for stopover in stopovers:
            stop_id = stopover.get("stop", {}).get("id")
            if not stop_id:
                continue
            if stop_id == current_stop_id:
                seen_current = True
                continue
            if seen_current:
                return stopover.get("stop", {}).get("name")
        return None

    for dep in departures:
        line = dep.get("line", {}).get("name", "Tram")
        if line_filter and line != line_filter:
            continue
        display_direction = dep.get("direction", "")
        group_direction = display_direction
        stopovers = dep.get("stopovers") or []
        trip_id = dep.get("tripId")
        if not stopovers and trip_id:
            trip_url = f"https://v6.bvg.transport.rest/trips/{trip_id}?stopovers=true"
            trip_data = fetch_json(trip_url, cache_ttl=600)
            if isinstance(trip_data, dict):
                trip = trip_data.get("trip") or {}
                stopovers = trip.get("stopovers") or []
        next_stop = next_stop_name(stopovers, stop_id)
        if next_stop:
            group_direction = next_stop
        when_text, when_sort = parse_departure_time(dep.get("when") or dep.get("plannedWhen"))
        rows.append((when_text, when_sort, line, group_direction, display_direction))
        if len(rows) >= 16:
            break
    if not rows:
        label = line_filter or "Tram"
        rows.append((f"No {label} departures", None, "", "", ""))
    else:
        _LAST_DEPARTURES[stop_query] = {
            "stop_name": stop_name,
            "rows": rows,
            "updated": time.time(),
        }
    return stop_name, rows


def draw_tram_table(draw, x, y, width, title, rows, fonts, inky, title_color, line_bg, line_text_color):
    font_title, font_sub, font_body, font_meta = fonts
    title_text = truncate_text(draw, title, width, font=font_body)
    draw.text((x, y), title_text, title_color, font=font_body)
    y += line_height(draw, font_body) + 4

    table_left = x
    table_right = x + width
    col_time = text_size(draw, "00:00", font_body)[0]
    col_line = 34
    gap = 10
    col_dir = table_right - table_left - col_time - col_line - (gap * 2)

    draw.line((table_left, y, table_right, y), fill=inky.BLACK)
    y += 4

    return y, (table_left, table_right, col_time, col_line, col_dir, gap)


def line_height(draw, font):
    try:
        return sum(font.getmetrics())
    except AttributeError:
        return text_size(draw, "Ag", font)[1]


def abbreviate_berlin_destination(text):
    if not text:
        return text
    normalized = text
    normalized = normalized.replace(" (Berlin)", "").replace(" (Bln)", "")
    normalized = normalized.split(" [", 1)[0]
    normalized = normalized.replace("\u00fc", "ue").replace("\u00f6", "oe").replace("\u00e4", "ae")
    normalized = normalized.replace("\u00df", "ss")
    normalized = normalized.replace("\u00dc", "Ue").replace("\u00d6", "Oe").replace("\u00c4", "Ae")
    normalized = normalized.replace("Stra\u00dfe", "Str.")
    if "," in normalized:
        normalized = normalized.split(",")[-1].strip()
    abbreviations = {
        "Landsberger Allee": "Land. Allee",
        "Landsberger Allee/Petersburger Str.": "Land. Allee/Petersb. Str.",
        "Landsberger Allee/Rhinstr.": "Land. Allee/Rhinstr.",
        "Lueneburger Str.": "Lueneburger Str.",
        "Zingster Str.": "Zingster Str.",
        "Virchowstr.": "Virchowstr.",
        "Betriebshof Marzahn": "Betr. Marzahn",
        "S Hackescher Markt": "S Hackescher Markt",
        "S Marzahn": "S Marzahn",
        "Riesaer Str.": "Riesaer Str.",
        "Siedlung Wartenberg/Str. 5": "Siedl. Wartenberg/Str. 5",
        "Zentralfriedhof": "Zentralfriedhof",
    }
    for full, short in abbreviations.items():
        if full in normalized:
            normalized = normalized.replace(full, short)
    return normalized


def normalize_direction(direction):
    if not direction:
        return ""
    overrides = {
        "Landsberger Allee/Petersburger Str.": "S+U Hauptbahnhof",
    }
    for key, target in overrides.items():
        if key in direction:
            return target
    return direction


def draw_tram_rows(draw, y, columns, rows, fonts, inky, line_bg, line_text_color, max_rows, line_badge_y_offset):
    table_left, table_right, col_time, col_line, col_dir, gap = columns
    _, _, font_body, _ = fonts
    if not rows:
        draw.text((table_left, y), "No departures", inky.BLACK, font=font_body)
        return y + 28
    count = 0
    row_h = max(16, line_height(draw, font_body) + 4)
    text_h = line_height(draw, font_body)
    for when, _, line, group_direction, display_direction in rows:
        text_y = y + max(0, (row_h - text_h) // 2)
        draw.text((table_left, text_y), when, inky.BLACK, font=font_body)
        line_x = table_left + col_time + gap
        line_text = truncate_text(draw, line, col_line - 4, font=font_body)
        line_w, line_h = text_size(draw, line_text, font=font_body)
        box_w = col_line - 1
        box_h = line_h + 3
        box_y = y + max(0, (row_h - box_h) // 2) + 1 + line_badge_y_offset
        if line_text:
            draw.rectangle(
                (line_x, box_y, line_x + box_w, box_y + box_h),
                fill=line_bg,
                outline=line_bg,
            )
            text_x = line_x + max(0, (box_w - line_w) // 2)
            draw.text((text_x, text_y), line_text, line_text_color, font=font_body)
        dir_text = display_direction or ""
        if dir_text:
            dir_text = dir_text.replace(" (Berlin)", "").replace(" (Bln)", "")
        if text_size(draw, dir_text, font=font_body)[0] > col_dir:
            dir_text = abbreviate_berlin_destination(dir_text)
        dir_text = truncate_text(draw, dir_text, col_dir, font=font_body)
        dest_x = table_left + col_time + gap + col_line + gap
        draw.text((dest_x, text_y), dir_text, inky.BLACK, font=font_body)
        y += row_h
        count += 1
        if count >= max_rows:
            break
    return y


def draw_transit_tile(ctx, bbox, config):
    draw = ctx["draw"]
    inky = ctx["inky"]
    fonts = ctx["fonts"]
    font_title = fonts["title"]
    font_sub = fonts["sub"]
    font_body = fonts["body"]
    font_meta = fonts["meta"]

    pad = config.get("pad", 12)
    if pad is None:
        pad = 12
    else:
        pad = int(pad)
    x0, y0, x1, y1 = bbox
    x = x0 + pad
    y = y0 + pad
    width = x1 - x0 - (pad * 2)

    stops = config.get("stops", DEFAULT_TRANSIT_CONFIG["stops"])
    title_color = getattr(inky, str(config.get("title_color", "RED")).upper(), inky.RED)
    line_bg = getattr(inky, str(config.get("line_bg", "RED")).upper(), inky.RED)
    line_text_color = getattr(inky, str(config.get("line_text_color", "WHITE")).upper(), inky.WHITE)
    line_badge_y_offset = config.get("line_badge_y_offset", DEFAULT_TRANSIT_CONFIG["line_badge_y_offset"])
    try:
        line_badge_y_offset = int(line_badge_y_offset)
    except (TypeError, ValueError):
        line_badge_y_offset = DEFAULT_TRANSIT_CONFIG["line_badge_y_offset"]
    max_rows = DEFAULT_TRANSIT_CONFIG["max_rows_per_group"]
    stub_rows = [
        ("12:05", None, "M5", "S+U Hauptbahnhof", "S+U Hauptbahnhof"),
        ("12:12", None, "M5", "S+U Hauptbahnhof", "S+U Hauptbahnhof"),
        ("12:19", None, "M5", "S+U Hauptbahnhof", "S+U Hauptbahnhof"),
        ("12:07", None, "M5", "Zingster Str.", "Zingster Str."),
        ("12:14", None, "M5", "Zingster Str.", "Zingster Str."),
        ("12:21", None, "M5", "Zingster Str.", "Zingster Str."),
    ]

    for stop_query in stops:
        if ctx.get("preview_stub"):
            stop_name, rows = stop_query, stub_rows
        else:
            stop_name, rows = get_tram_departures(stop_query)
        max_rows_per_group = config.get("max_rows_per_group") or max_rows
        try:
            max_rows_per_group = int(max_rows_per_group)
        except (TypeError, ValueError):
            max_rows_per_group = max_rows
        max_rows_per_group = max(1, min(12, max_rows_per_group))

        groups = []
        group_index = {}

        def token_overlap(a, b):
            if not a or not b:
                return 0
            a_tokens = set(a.lower().replace("/", " ").replace(",", " ").split())
            b_tokens = set(b.lower().replace("/", " ").replace(",", " ").split())
            return len(a_tokens & b_tokens)

        raw_keys = []
        for _, _, _, group_direction, _ in rows:
            key = normalize_direction(group_direction) or ""
            if key not in raw_keys:
                raw_keys.append(key)
        allow_merge = len(raw_keys) > 2

        for when, when_sort, line, group_direction, display_direction in rows:
            key = normalize_direction(group_direction) or ""
            if key not in group_index:
                if len(groups) < 2:
                    group_index[key] = len(groups)
                    groups.append([])
                elif allow_merge:
                    # Merge extra directions into the closest existing group.
                    best_idx = 0
                    best_score = -1
                    for idx, group_rows in enumerate(groups):
                        group_name = group_rows[0][3] if group_rows else ""
                        score = token_overlap(key, group_name)
                        if score > best_score:
                            best_score = score
                            best_idx = idx
                        elif score == best_score and score == 0:
                            if len(group_rows) < len(groups[best_idx]):
                                best_idx = idx
                    group_index[key] = best_idx
                else:
                    # Keep only two distinct directions and drop extras into the second group.
                    group_index[key] = 1
            groups[group_index[key]].append((when, when_sort, line, group_direction, display_direction))

        y, columns = draw_tram_table(
            draw,
            x,
            y,
            width,
            stop_name,
            rows,
            (font_title, font_sub, font_body, font_meta),
            inky,
            title_color,
            line_bg,
            line_text_color,
        )
        if not groups:
            groups = [rows]
        west_keywords = {
            "hauptbahnhof",
            "hackescher markt",
            "zentralfriedhof",
            "lueneburger",
        }
        east_keywords = {
            "zingster",
            "virchow",
            "riesaer",
            "marzahn",
            "wartenberg",
            "landsberger",
        }

        def group_direction_score(group_rows):
            for _, _, _, group_direction, _ in group_rows:
                if group_direction:
                    name = abbreviate_berlin_destination(group_direction).lower()
                    for token in west_keywords:
                        if token in name:
                            return 0
                    for token in east_keywords:
                        if token in name:
                            return 1
            return 2

        def departure_sort_key(row):
            when_text, when_sort, _, _, _ = row
            if when_sort is not None:
                return when_sort
            try:
                hours, minutes = when_text.split(":", 1)
                return int(hours) * 60 + int(minutes)
            except (ValueError, AttributeError):
                return float("inf")

        groups = sorted(groups, key=group_direction_score)
        for idx, group_rows in enumerate(groups):
            group_rows.sort(key=departure_sort_key)
            if idx > 0:
                y += 4
            y = draw_tram_rows(
                draw,
                y,
                columns,
                group_rows,
                (font_title, font_sub, font_body, font_meta),
                inky,
                line_bg,
                line_text_color,
                max_rows_per_group,
                line_badge_y_offset,
            )
        y += 10
