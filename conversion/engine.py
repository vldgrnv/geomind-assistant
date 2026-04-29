import csv
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from conversion.options import is_valid_pair


def _tool(name: str) -> str | None:
    return shutil.which(name)


def require_gdal_tools(vector: bool = True, raster: bool = False):
    missing = []
    if vector:
        for b in ("ogr2ogr", "ogrinfo"):
            if not _tool(b):
                missing.append(b)
    if raster:
        if not _tool("gdal_translate"):
            missing.append("gdal_translate")
    if missing:
        raise RuntimeError(
            "Не установлены утилиты GDAL: " + ", ".join(missing)
            + ". Установите пакет gdal-bin (Linux) или GDAL."
        )


def _run(args: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip() or "ошибка ogr/gdal"
        raise RuntimeError(err[:4000])


def _ogr_first_layer(path: Path) -> str | None:
    r = subprocess.run(
        ["ogrinfo", str(path)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    m = re.search(r"^Layer name:\s*(.+)$", r.stdout, re.MULTILINE)
    return m.group(1).strip() if m else None


def _ogr_convert(format_driver: str, dest: Path, src: Path) -> None:
    """ogr2ogr -f FORMAT DEST SOURCE [LAYER].

    Для одиночного файла (.shp, .geojson и т.д.) имя слоя не передаём — иначе GDAL
    часто возвращает ошибку вида «layer … not found».
    Имя слоя задаём для контейнеров: GeoPackage, каталог .gdb.
    """
    lyr = _ogr_first_layer(src)
    args = ["ogr2ogr", "-f", format_driver, str(dest), str(src)]
    suf = src.suffix.lower()
    use_layer = lyr and (
        suf == ".gpkg" or (src.is_dir() and src.name.lower().endswith(".gdb"))
    )
    if use_layer:
        args.append(lyr)
    _run(args)


def _safe_extract_zip(zpath: Path, dest: Path) -> None:
    with zipfile.ZipFile(zpath, "r") as zf:
        for m in zf.namelist():
            if m.startswith("/") or ".." in m:
                raise RuntimeError("Некорректный ZIP")
        zf.extractall(dest)


def _find_shp(root: Path) -> Path:
    """Ищет шейпфайл без учёта регистра расширения (.SHP и т.д.)."""
    candidates: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.lower().endswith(".shp"):
            candidates.append(p)
    if not candidates:
        files = [x for x in root.rglob("*") if x.is_file()][:40]
        preview = "; ".join(str(x.relative_to(root)) for x in files[:20])
        raise RuntimeError(
            "В архиве не найден файл с расширением .shp (проверьте, что внутри ZIP есть .shp рядом с .dbf/.shx). "
            + (f"Файлы в архиве (начало): {preview}" if preview else "Архив пуст или не распаковался.")
        )
    return sorted(candidates, key=lambda x: len(str(x)))[0]


def _find_gdb(root: Path) -> Path:
    gdbs = [p for p in root.rglob("*") if p.is_dir() and p.suffix.lower() == ".gdb"]
    if not gdbs:
        raise RuntimeError("В архиве не найдена папка .gdb")
    return gdbs[0]


def _find_img(root: Path) -> Path:
    imgs = list(root.rglob("*.img")) + list(root.rglob("*.IMG"))
    if not imgs:
        raise RuntimeError("Не найден файл .img")
    return imgs[0]


def _prepare_kml_kmz(upload: Path, work: Path) -> Path:
    suf = upload.suffix.lower()
    if suf == ".kmz":
        _safe_extract_zip(upload, work)
        kmls = list(work.rglob("*.kml"))
        if not kmls:
            raise RuntimeError("В KMZ не найден .kml")
        return kmls[0]
    if suf == ".kml":
        shutil.copy2(upload, work / upload.name)
        return work / upload.name
    raise RuntimeError("Ожидается .kml или .kmz")


def _prepare_vector_source(input_key: str, upload: Path, work: Path) -> Path:
    """Возвращает путь к источнику для ogr2ogr."""
    if input_key == "shp":
        _safe_extract_zip(upload, work)
        return _find_shp(work)
    if input_key == "gdb":
        _safe_extract_zip(upload, work)
        return _find_gdb(work)
    if input_key == "kml_kmz":
        return _prepare_kml_kmz(upload, work / "kml_in")
    if input_key == "geojson":
        shutil.copy2(upload, work / upload.name)
        return work / upload.name
    if input_key == "gpkg":
        shutil.copy2(upload, work / upload.name)
        return work / upload.name
    if input_key == "dxf":
        shutil.copy2(upload, work / upload.name)
        return work / upload.name
    if input_key == "csv":
        shutil.copy2(upload, work / upload.name)
        return work / upload.name
    if input_key == "xlsx":
        shutil.copy2(upload, work / upload.name)
        return work / upload.name
    raise RuntimeError("Неизвестный тип входа")


def _normalize_col(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace("ё", "е")
        .replace("_", "")
        .replace(" ", "")
    )


def _detect_xy_columns(headers: list[str]) -> tuple[str, str]:
    """Возвращает (колонка долготы/x, колонка широты/y) для [lon, lat]."""

    def score_lat(h: str) -> int:
        n = _normalize_col(h)
        if re.match(r"^lat(itude)?$", n) or n == "широта":
            return 100
        if "lat" in n or "широт" in n:
            return 80
        if n == "y":
            return 50
        if "northing" in n:
            return 40
        return 0

    def score_lon(h: str) -> int:
        n = _normalize_col(h)
        if re.match(r"^lon(g(itude)?)?$", n) or n in ("lng", "долгота"):
            return 100
        if "lon" in n or "lng" in n or "долгот" in n:
            return 80
        if n == "x":
            return 50
        if "easting" in n:
            return 40
        return 0

    best_lat = max(headers, key=score_lat)
    best_lon = max(headers, key=score_lon)
    if score_lat(best_lat) < 40 or score_lon(best_lon) < 40:
        raise RuntimeError(
            "Не удалось найти колонки координат. Укажите lat/lon, x/y или широта/долгота."
        )
    if best_lat == best_lon:
        raise RuntimeError("Колонки широты и долготы совпадают — проверьте таблицу.")
    return best_lon, best_lat


def _csv_to_geojson_via_vrt(csv_path: Path, work: Path) -> Path:
    full_text = Path(csv_path).read_text(encoding="utf-8-sig")
    sample = full_text[:65536]
    dialect = csv.Sniffer().sniff(sample.splitlines()[0] if sample else ",")
    rows = list(csv.reader(io.StringIO(full_text), dialect))
    if not rows:
        raise RuntimeError("Пустой CSV")
    headers = [h.strip() for h in rows[0]]

    lon_col, lat_col = _detect_xy_columns(headers)
    lon_i = headers.index(lon_col)
    lat_i = headers.index(lat_col)

    feats = []
    for row in rows[1:]:
        if len(row) <= max(lon_i, lat_i):
            continue
        try:
            lon = float(row[lon_i].replace(",", "."))
            lat = float(row[lat_i].replace(",", "."))
        except ValueError:
            continue
        props = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )

    if not feats:
        raise RuntimeError("Нет ни одной строки с числовыми координатами.")

    gj = {"type": "FeatureCollection", "features": feats}
    out = work / "points.geojson"
    out.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return out


def _xlsx_to_csv(upload: Path, work: Path) -> Path:
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("Для Excel нужен пакет openpyxl")

    wb = openpyxl.load_workbook(upload, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise RuntimeError("Пустой Excel")
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    csv_path = work / "sheet.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows[1:]:
            w.writerow([("" if c is None else c) for c in r])
    return csv_path


def _zip_shapefile_dir(shp_dir: Path, out_zip: Path) -> None:
    paths = []
    for pat in ("*.shp", "*.dbf", "*.shx", "*.prj", "*.cpg", "*.qpj"):
        paths.extend(shp_dir.glob(pat))
    stem = None
    for p in paths:
        if p.suffix.lower() == ".shp":
            stem = p.stem
            break
    if not stem:
        raise RuntimeError("Не создан shapefile")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=p.name)


def convert_file(
    input_key: str,
    output_key: str,
    upload_path: Path,
    original_name: str,
) -> tuple[Path, str, str, Path]:
    """
    Выполняет конвертацию.
    Возвращает (путь к файлу результата, MIME, имя для скачивания, рабочая папка для удаления после отдачи).
    """
    if not is_valid_pair(input_key, output_key):
        raise RuntimeError("Недопустимая пара форматов")

    work = Path(tempfile.mkdtemp(prefix="gm_conv_"))
    try:
        suf = Path(original_name).suffix.lower()

        # --- Растры ---
        if input_key == "geotiff" and output_key == "cog":
            require_gdal_tools(vector=False, raster=True)
            src = work / Path(original_name).name
            shutil.copy2(upload_path, src)
            out_tif = work / "out_cog.tif"
            _run(
                [
                    "gdal_translate",
                    "-of",
                    "COG",
                    "-co",
                    "COMPRESS=LZW",
                    str(src),
                    str(out_tif),
                ]
            )
            return out_tif, "image/tiff", "converted_cog.tif", work

        if input_key == "image_world" and output_key == "geotiff":
            require_gdal_tools(vector=False, raster=True)
            extract_dir = work / "imgwf"
            extract_dir.mkdir()
            _safe_extract_zip(upload_path, extract_dir)
            imgs = (
                list(extract_dir.rglob("*.jpg"))
                + list(extract_dir.rglob("*.jpeg"))
                + list(extract_dir.rglob("*.png"))
                + list(extract_dir.rglob("*.JPG"))
                + list(extract_dir.rglob("*.PNG"))
            )
            if not imgs:
                raise RuntimeError("В ZIP нужен JPEG или PNG и файл привязки (.jgw/.pgw/.tfw)")
            img_path = imgs[0]
            out_tif = work / "georef.tif"
            _run(["gdal_translate", "-of", "GTiff", str(img_path), str(out_tif)])
            return out_tif, "image/tiff", "converted.tif", work

        if input_key == "erdas_img" and output_key == "geotiff":
            require_gdal_tools(vector=False, raster=True)
            if suf == ".zip":
                extract_dir = work / "erd"
                extract_dir.mkdir()
                _safe_extract_zip(upload_path, extract_dir)
                img_path = _find_img(extract_dir)
            elif suf == ".img":
                img_path = work / Path(original_name).name
                shutil.copy2(upload_path, img_path)
            else:
                raise RuntimeError("Ожидается .img или ZIP с .img")
            out_tif = work / "from_erdas.tif"
            _run(["gdal_translate", "-of", "GTiff", str(img_path), str(out_tif)])
            return out_tif, "image/tiff", "converted.tif", work

        # --- Вектор через OGR ---
        require_gdal_tools(vector=True, raster=False)

        if input_key == "csv" and output_key == "geojson":
            src_csv = work / "in.csv"
            shutil.copy2(upload_path, src_csv)
            gj = _csv_to_geojson_via_vrt(src_csv, work)
            return gj, "application/geo+json", "converted.geojson", work

        if input_key == "xlsx" and output_key == "shp":
            csv_path = _xlsx_to_csv(upload_path, work)
            gj = _csv_to_geojson_via_vrt(csv_path, work)
            out_dir = work / "shp_out"
            out_dir.mkdir(parents=True)
            _ogr_convert("ESRI Shapefile", out_dir, gj)
            zip_path = work / "out.zip"
            _zip_shapefile_dir(out_dir, zip_path)
            return zip_path, "application/zip", "converted_shapefile.zip", work

        src = _prepare_vector_source(input_key, upload_path, work)

        if output_key == "geojson":
            out_path = work / "out.geojson"
            _ogr_convert("GeoJSON", out_path, src)
            return out_path, "application/geo+json", "converted.geojson", work

        if output_key == "shp":
            out_dir = work / "shape_out"
            out_dir.mkdir(parents=True)
            _ogr_convert("ESRI Shapefile", out_dir, src)
            zip_path = work / "shape.zip"
            _zip_shapefile_dir(out_dir, zip_path)
            return zip_path, "application/zip", "converted_shapefile.zip", work

        if output_key == "gpkg":
            out_path = work / "out.gpkg"
            _ogr_convert("GPKG", out_path, src)
            return out_path, "application/vnd.sqlite3", "converted.gpkg", work

        raise RuntimeError("Комбинация не реализована")

    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise


def cleanup_workdir(work_root: Path) -> None:
    try:
        if work_root.name.startswith("gm_conv_") and work_root.is_dir():
            shutil.rmtree(work_root, ignore_errors=True)
    except Exception:
        pass
