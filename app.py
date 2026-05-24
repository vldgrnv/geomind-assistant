import os
import logging
import time
from collections import defaultdict, deque
from threading import Lock
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

load_dotenv()

from database.db import get_db, init_db, optimize_db
from auth.router import router as auth_router
from api.router import router as api_router
from conversion.router import router as convert_router
from AI_service.search_algorithm import get_algorithm_index


APP_VERSION = "project-logo-1"
logger = logging.getLogger("geomind.app")


def configure_logging():
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class FixedWindowRateLimiter:
    def __init__(self):
        self._buckets = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        boundary = now - window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < boundary:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


configure_logging()

app = FastAPI(title="GeoMind Assistant API")
app.state.ready = False
app.state.startup_error = None
app.state.rate_limiter = FixedWindowRateLimiter()

allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(convert_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    started_at = time.perf_counter()
    try:
        init_db()
        optimize_db()
        get_algorithm_index()
        app.state.ready = True
        app.state.startup_error = None
        logger.info(
            "startup_complete version=%s duration_ms=%.2f",
            APP_VERSION,
            (time.perf_counter() - started_at) * 1000,
        )
    except Exception as exc:
        app.state.ready = False
        app.state.startup_error = str(exc)
        logger.exception("startup_failed")
        raise


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    start = time.perf_counter()

    path_limits = {
        "/auth/login": (12, 60),
        "/auth/register": (6, 600),
        "/api/bug-reports": (8, 600),
        "/api/contact-requests": (5, 600),
    }
    limit = path_limits.get(request.url.path)
    if limit:
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
        key = f"{request.url.path}:{client_ip}"
        if not app.state.rate_limiter.is_allowed(key, *limit):
            logger.warning("rate_limit_exceeded path=%s ip=%s", request.url.path, client_ip)
            return JSONResponse(
                {"detail": "Слишком много запросов. Попробуйте чуть позже."},
                status_code=429,
            )

    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    if not request.url.path.startswith("/static/"):
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )
    return response


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": APP_VERSION}


@app.get("/readyz")
def readyz():
    if not app.state.ready:
        return JSONResponse(
            {"ok": False, "reason": app.state.startup_error or "startup_not_complete"},
            status_code=503,
        )

    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        logger.exception("readiness_check_failed")
        return JSONResponse({"ok": False, "reason": str(exc)}, status_code=503)

    return {"ok": True}


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return RedirectResponse(f"/static/index.html?v={APP_VERSION}")


@app.api_route("/admin", methods=["GET", "HEAD"])
def admin():
    return RedirectResponse(f"/static/admin.html?v={APP_VERSION}")


@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
def favicon():
    return RedirectResponse(f"/static/favicon.svg?v={APP_VERSION}")


@app.api_route("/robots.txt", methods=["GET", "HEAD"])
def robots():
    return FileResponse("static/robots.txt", media_type="text/plain; charset=utf-8")
