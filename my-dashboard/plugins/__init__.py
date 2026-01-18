from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .transit import DEFAULT_TRANSIT_CONFIG, TRANSIT_SCHEMA, draw_transit_tile
from .weather import DEFAULT_WEATHER_CONFIG, WEATHER_SCHEMA, draw_weather_tile


@dataclass
class TileSpec:
    plugin: str
    col: int
    row: int
    colspan: int = 1
    rowspan: int = 1
    config: Dict[str, object] = field(default_factory=dict)


def layout_tiles(area, cols, rows, gutter, tile_layout):
    x0, y0, x1, y1 = area
    width = x1 - x0
    height = y1 - y0
    total_gutter_x = gutter * (cols - 1)
    total_gutter_y = gutter * (rows - 1)
    col_w = (width - total_gutter_x) // cols
    row_h = (height - total_gutter_y) // rows
    col_x = [x0 + c * (col_w + gutter) for c in range(cols)]
    row_y = [y0 + r * (row_h + gutter) for r in range(rows)]

    tiles = []
    for spec in tile_layout:
        left = col_x[spec.col]
        top = row_y[spec.row]
        right = left + (col_w * spec.colspan) + (gutter * (spec.colspan - 1))
        bottom = top + (row_h * spec.rowspan) + (gutter * (spec.rowspan - 1))
        tiles.append((spec, (left, top, right, bottom)))
    return tiles


PLUGIN_REGISTRY = {
    "transit": draw_transit_tile,
    "weather": draw_weather_tile,
}

PLUGIN_DEFAULTS = {
    "transit": DEFAULT_TRANSIT_CONFIG,
    "weather": DEFAULT_WEATHER_CONFIG,
}

PLUGIN_SCHEMAS = {
    "transit": TRANSIT_SCHEMA,
    "weather": WEATHER_SCHEMA,
}

PLUGIN_NAMES = {
    "transit": "Transit",
    "weather": "Weather",
}
