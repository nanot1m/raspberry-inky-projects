from urllib.parse import quote

from utils import fetch_json, parse_when, text_size, truncate_text

DEFAULT_TRANSIT_CONFIG = {
    "stops": ["Genslerstr", "Werneuchener Str"],
    "title_color": "red",
    "line_bg": "red",
    "line_text_color": "white",
    "max_rows_per_group": 4,
    "pad": 12,
}

TRANSIT_SCHEMA = {
    "stops": {"type": "list", "label": "Stops", "itemType": "string"},
    "title_color": {"type": "enum", "label": "Title Color", "options": ["red", "blue", "black"]},
    "line_bg": {"type": "enum", "label": "Line Badge", "options": ["red", "blue", "black"]},
    "line_text_color": {"type": "enum", "label": "Line Text", "options": ["white", "black"]},
    "max_rows_per_group": {"type": "number", "label": "Max Rows Per Direction", "min": 1, "max": 12},
    "pad": {"type": "number", "label": "Padding", "min": 0, "max": 30},
}


def get_tram_departures(stop_query, line_filter=None):
    stops_url = (
        "https://v6.bvg.transport.rest/stops"
        f"?query={quote(stop_query)}&results=1"
    )
    stops = fetch_json(stops_url, cache_ttl=60)
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
        "?duration=1440"
    )
    departures = fetch_json(dep_url, cache_ttl=60)
    if not departures:
        label = line_filter or "Tram"
        return stop_name, [(f"No {label} data", "", "")]
    if isinstance(departures, dict):
        departures = departures.get("departures", [])
    if not isinstance(departures, list):
        label = line_filter or "Tram"
        return stop_name, [(f"No {label} data", "", "")]
    rows = []
    for dep in departures:
        line = dep.get("line", {}).get("name", "Tram")
        if line_filter and line != line_filter:
            continue
        direction = dep.get("direction", "")
        when = parse_when(dep.get("when") or dep.get("plannedWhen"))
        rows.append((when, line, direction))
        if len(rows) >= 16:
            break
    if not rows:
        label = line_filter or "Tram"
        rows.append((f"No {label} departures", "", ""))
    return stop_name, rows


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

    return y, (table_left, table_right, col_time, col_line, col_dir)


def abbreviate_berlin_destination(text):
    if not text:
        return text
    abbreviations = {
        "Landsberger Allee": "Land. Allee",
    }
    for full, short in abbreviations.items():
        if full in text:
            text = text.replace(full, short)
    return text


def draw_tram_rows(draw, y, columns, rows, fonts, inky, line_bg, line_text_color, max_rows):
    table_left, table_right, col_time, col_line, col_dir = columns
    _, _, font_body, _ = fonts
    if not rows:
        draw.text((table_left, y), "No departures", inky.BLACK, font=font_body)
        return y + 28
    count = 0
    for when, line, direction in rows:
        draw.text((table_left, y), when, inky.BLACK, font=font_body)
        line_x = table_left + col_time
        line_text = truncate_text(draw, line, col_line - 8, font=font_body)
        line_w, line_h = text_size(draw, line_text, font=font_body)
        box_w = min(col_line - 4, line_w + 10)
        box_h = line_h + 4
        box_y = y + 2
        if line_text:
            draw.rectangle(
                (line_x, box_y, line_x + box_w, box_y + box_h),
                fill=line_bg,
                outline=line_bg,
            )
            draw.text((line_x + 5, y), line_text, line_text_color, font=font_body)
        dir_text = abbreviate_berlin_destination(direction)
        dir_text = truncate_text(draw, dir_text, col_dir, font=font_body)
        draw.text((table_left + col_time + col_line, y), dir_text, inky.BLACK, font=font_body)
        y += 20
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
    max_rows = DEFAULT_TRANSIT_CONFIG["max_rows_per_group"]

    for stop_query in stops:
        stop_name, rows = get_tram_departures(stop_query)
        max_rows_per_group = config.get("max_rows_per_group") or max_rows
        try:
            max_rows_per_group = int(max_rows_per_group)
        except (TypeError, ValueError):
            max_rows_per_group = max_rows
        max_rows_per_group = max(1, min(12, max_rows_per_group))

        groups = []
        group_index = {}
        for when, line, direction in rows:
            key = direction or ""
            if key not in group_index:
                if len(groups) >= 2:
                    continue
                group_index[key] = len(groups)
                groups.append([])
            groups[group_index[key]].append((when, line, direction))

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
        for idx, group_rows in enumerate(groups):
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
            )
        y += 10
