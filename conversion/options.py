"""Описание допустимых пар форматов для UI и валидации."""

INPUT_META = [
    {"key": "shp", "label": "Shapefile (.zip)", "hint": "ZIP с .shp, .shx, .dbf"},
    {"key": "geojson", "label": "GeoJSON", "hint": ".geojson или .json"},
    {"key": "kml_kmz", "label": "KML / KMZ", "hint": ".kml или .kmz"},
    {"key": "gpkg", "label": "GeoPackage (.gpkg)", "hint": ""},
    {"key": "gdb", "label": "File Geodatabase", "hint": "ZIP с папкой .gdb"},
    {"key": "dxf", "label": "DXF (AutoCAD)", "hint": ".dxf"},
    {"key": "csv", "label": "CSV с координатами", "hint": "Колонки lat/lon, x/y и т.п."},
    {"key": "xlsx", "label": "Excel (.xlsx)", "hint": "Первая страница, координаты в колонках"},
    {"key": "geotiff", "label": "GeoTIFF", "hint": ".tif / .tiff"},
    {"key": "image_world", "label": "JPEG/PNG + world file", "hint": "ZIP: изображение + .jgw/.pgw/.tfw"},
    {"key": "erdas_img", "label": "ERDAS Imagine (.img)", "hint": ".img или ZIP с .img"},
]

OUTPUT_LABELS = {
    "geojson": "GeoJSON",
    "shp": "Shapefile (.zip)",
    "gpkg": "GeoPackage (.gpkg)",
    "cog": "Cloud Optimized GeoTIFF (COG)",
    "geotiff": "GeoTIFF",
}

# output_key -> описание для справки
OUTPUT_HINTS = {
    "geojson": "Для веб-карт и API",
    "shp": "Для ArcMap / совместимость",
    "gpkg": "Open-source ГИС",
    "cog": "Веб и облако",
    "geotiff": "Унифицированный растр",
}

# Какие выходы доступны для каждого входа
OUTPUTS_BY_INPUT = {
    "shp": ["geojson", "gpkg"],
    "geojson": ["shp"],
    "kml_kmz": ["geojson", "shp"],
    "gpkg": ["shp", "geojson"],
    "gdb": ["gpkg", "shp"],
    "dxf": ["geojson"],
    "csv": ["geojson"],
    "xlsx": ["shp"],
    "geotiff": ["cog"],
    "image_world": ["geotiff"],
    "erdas_img": ["geotiff"],
}


def is_valid_pair(input_key: str, output_key: str) -> bool:
    return output_key in OUTPUTS_BY_INPUT.get(input_key, [])
