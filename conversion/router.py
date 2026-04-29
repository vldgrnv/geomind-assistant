import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from auth.jwt import get_current_user_id
from conversion.engine import cleanup_workdir, convert_file
from conversion.options import INPUT_META, OUTPUT_HINTS, OUTPUT_LABELS, OUTPUTS_BY_INPUT

router = APIRouter(prefix="/api", tags=["convert"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024


@router.get("/convert/options")
def convert_options():
    """Публичный справочник пар форматов для UI (не секрет). Конвертация — только с JWT."""
    return {
        "inputs": INPUT_META,
        "outputs_by_input": OUTPUTS_BY_INPUT,
        "output_labels": OUTPUT_LABELS,
        "output_hints": OUTPUT_HINTS,
    }


@router.post("/convert")
async def convert_upload(
    input_format: str = Form(...),
    output_format: str = Form(...),
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    _ = user_id
    if not file.filename:
        raise HTTPException(400, "Не указано имя файла")

    suf = Path(file.filename).suffix.lower()
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Файл слишком большой")

    tmp_in = Path(tempfile.mkstemp(prefix="gm_up_", suffix=suf)[1])
    try:
        tmp_in.write_bytes(raw)
        try:
            out_path, mime, dl_name, work_root = convert_file(
                input_format.strip(),
                output_format.strip(),
                tmp_in,
                file.filename,
            )
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            raise HTTPException(500, "Ошибка конвертации: " + str(e)[:500]) from e

        return FileResponse(
            path=out_path,
            media_type=mime,
            filename=dl_name,
            background=BackgroundTask(cleanup_workdir, work_root),
        )
    finally:
        tmp_in.unlink(missing_ok=True)
