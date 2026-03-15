import os
import sys
import time
import logging
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from starlette.exceptions import HTTPException as StarletteHTTPException

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from database.db import init_db  # noqa: E402
from api_v2.routers import tasks, plans, feedback, analytics, settings, session, mood, focus, songs, fortune, assistant  # noqa: E402

app = FastAPI(title="Deletion Planner API v2", version="2.0.0")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("deletion-planner-fastapi")

# ── CORS ──────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ─────────────────────────────────────────
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "120"))
_rate_buckets = defaultdict(list)


@app.on_event("startup")
def startup():
    init_db()


# ── API Key Auth (optional) ──────────────────────────────
API_KEY = os.getenv("API_KEY", "")


@app.middleware("http")
async def auth_and_timing_middleware(request: Request, call_next):
    start = time.perf_counter()

    # Skip auth for health check and OPTIONS
    if request.url.path == "/health" or request.method == "OPTIONS":
        response = await call_next(request)
    else:
        # API key check (only if API_KEY env var is set)
        if API_KEY:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {API_KEY}":
                return JSONResponse(
                    status_code=401,
                    content={"error_code": "UNAUTHORIZED", "message": "Invalid or missing API key"},
                )

        # Rate limiting by IP
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = _rate_buckets[client_ip]
        # Remove entries older than 60 seconds
        _rate_buckets[client_ip] = [t for t in bucket if now - t < 60]
        if len(_rate_buckets[client_ip]) >= RATE_LIMIT_RPM:
            return JSONResponse(
                status_code=429,
                content={"error_code": "RATE_LIMITED", "message": "Too many requests. Try again later."},
            )
        _rate_buckets[client_ip].append(now)

        response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {
        "error_code": "HTTP_ERROR",
        "message": str(exc.detail),
    }
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": exc.errors()},
        },
    )


@app.get("/health")
def health():
    return {"ok": True, "service": "Deletion Planner API v2"}


app.include_router(tasks.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(session.router, prefix="/api")
app.include_router(mood.router, prefix="/api")
app.include_router(focus.router, prefix="/api")
app.include_router(songs.router, prefix="/api")
app.include_router(fortune.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
