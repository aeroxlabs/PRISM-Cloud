import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
load_dotenv()  # Must run before importing database.py (DATABASE_URL is read at import).

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from auth_and_limits import AuthContext, authenticate_and_reserve, create_api_key, require_admin
from database import get_session_factory, init_db, check_database
from logging_config import configure_logging, get_logger
from ml_pipeline import detect, load_pipeline

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PRISM Cloud API")
    try:
        init_db()
        app.state.session_factory = get_session_factory()
        app.state.pipeline = load_pipeline()
        logger.info("PRISM startup complete; database and model are ready")
    except Exception:
        logger.exception("PRISM startup failed")
        raise
    yield
    app.state.pipeline = None
    logger.info("PRISM Cloud API stopped")


app = FastAPI(
    title="PRISM Cloud API",
    description="AeroxLabs PRISM message threat-detection API",
    version="1.1.0",
    lifespan=lifespan,
)


class DetectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10000)


class CreateKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    tier: str = Field(pattern="^(free|pro)$")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request exception",
            extra={"request_id": request_id, "method": request.method,
                   "path": request.url.path,
                   "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error.", "request_id": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "Request completed",
        extra={"request_id": request_id, "method": request.method,
               "path": request.url.path, "status_code": response.status_code,
               "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
    )
    return response


def get_auth_context(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthContext:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    return authenticate_and_reserve(
        x_api_key=x_api_key, session_factory=request.app.state.session_factory
    )


@app.get("/")
def root():
    return {"name": "PRISM Cloud API", "organization": "AeroxLabs",
            "version": app.version, "docs": "/docs"}


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health")
def health(request: Request):
    model_ready = getattr(request.app.state, "pipeline", None) is not None
    database_ready = check_database()
    healthy = model_ready and database_ready
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "healthy" if healthy else "unhealthy",
                 "checks": {"database": "ok" if database_ready else "error",
                            "model": "loaded" if model_ready else "not_loaded"}},
    )


@app.post("/v1/detect")
def detect_endpoint(
    payload: DetectRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
):
    try:
        result = detect(payload.text, request.app.state.pipeline)
    except Exception:
        logger.exception("Model inference failed",
                         extra={"request_id": getattr(request.state, "request_id", None)})
        raise HTTPException(
            status_code=500,
            detail="PRISM inference failed. Contact support with the request ID.",
        )
    return {
        "is_scam": result["is_scam"],
        "confidence_score": result["confidence_score"],
        "risk_level": result["risk_level"],
        "reason_codes": result["reason_codes"],
        "usage": {"tier": auth.tier, "requests_used": auth.requests_used,
                  "monthly_limit": auth.monthly_limit,
                  "overage_requests": auth.overage_requests,
                  "is_overage": auth.is_overage},
    }


@app.post("/admin/keys")
def admin_create_key(
    payload: CreateKeyRequest,
    request: Request,
    _: Annotated[bool, Depends(require_admin)],
):
    raw_key, record = create_api_key(
        session_factory=request.app.state.session_factory,
        user_id=payload.user_id, email=payload.email, tier=payload.tier,
    )
    logger.info("API key created",
                extra={"user_id": record["user_id"], "tier": record["tier"]})
    return {
        "api_key": raw_key, "user_id": record["user_id"],
        "email": record["email"], "tier": record["tier"],
        "monthly_limit": 500 if record["tier"] == "free" else 25000,
        "warning": "Store this key securely. It will not be shown again.",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail,
                 "request_id": getattr(request.state, "request_id", None)},
        headers=exc.headers or {},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Do not echo submitted message text or other input values in error responses.
    safe_errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
                   for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors,
                 "request_id": getattr(request.state, "request_id", None)},
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application exception",
                     extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.",
                 "request_id": getattr(request.state, "request_id", None)},
    )
