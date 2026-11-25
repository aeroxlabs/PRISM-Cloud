import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timezone

from fastapi import Header, HTTPException
from sqlalchemy import select

from database import APIKey, reset_monthly_counters_if_due, utcnow


FREE_LIMIT = 500
PRO_LIMIT = 25000
RATE_LIMITS = {"free": 1, "pro": 5}


@dataclass(frozen=True)
class AuthContext:
    key_id: int
    user_id: str
    tier: str
    requests_used: int
    monthly_limit: int
    overage_requests: int
    is_overage: bool


def _pepper() -> bytes:
    value = os.getenv("API_KEY_PEPPER")
    if not value:
        raise RuntimeError("API_KEY_PEPPER must be configured.")
    return value.encode("utf-8")


def hash_api_key(raw_key: str) -> str:
    return hmac.new(_pepper(), raw_key.encode("utf-8"), hashlib.sha256).hexdigest()


def require_admin(x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret")):
    expected = os.getenv("ADMIN_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="Admin endpoint is not configured.")
    if not x_admin_secret or not secrets.compare_digest(x_admin_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    return True


def create_api_key(session_factory, user_id: str, email: str, tier: str):
    if tier not in {"free", "pro"}:
        raise HTTPException(status_code=422, detail="Tier must be 'free' or 'pro'.")

    raw_key = "prism_" + secrets.token_urlsafe(32)
    key_hash = hash_api_key(raw_key)

    with session_factory() as session:
        record = APIKey(
            key_hash=key_hash,
            user_id=user_id,
            email=email,
            tier=tier,
            requests_used_this_month=0,
            overage_count=0,
            billing_cycle_start=utcnow(),
            created_at=utcnow(),
            is_active=1,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        result = {
            "user_id": record.user_id,
            "email": record.email,
            "tier": record.tier,
        }

    return raw_key, result


def authenticate_and_reserve(x_api_key: str, session_factory) -> AuthContext:
    try:
        key_hash = hash_api_key(x_api_key)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="API authentication is not configured.")

    with session_factory() as session:
        key = session.scalar(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == 1)
        )

        if key is None:
            raise HTTPException(status_code=401, detail="Invalid API key.")

        reset_monthly_counters_if_due(session, key)
        session.flush()

        tier = key.tier
        limit = FREE_LIMIT if tier == "free" else PRO_LIMIT

        # Rate-limit before reserving monthly usage so throttled calls do not
        # consume a customer's monthly quota.
        enforce_rate_limit(key.id, tier)

        if tier == "free" and key.requests_used_this_month >= FREE_LIMIT:
            session.commit()
            raise HTTPException(
                status_code=429,
                detail="Free monthly limit reached (500 requests). Upgrade to Pro for 25,000 included monthly requests.",
            )

        previous_count = key.requests_used_this_month
        key.requests_used_this_month += 1

        is_overage = tier == "pro" and previous_count >= PRO_LIMIT
        if is_overage:
            key.overage_count += 1

        session.commit()

        return AuthContext(
            key_id=key.id,
            user_id=key.user_id,
            tier=tier,
            requests_used=key.requests_used_this_month,
            monthly_limit=limit,
            overage_requests=key.overage_count,
            is_overage=is_overage,
        )


# Process-local sliding-window limiter. For multiple workers/instances, replace
# this with Redis so all workers share the same counters.
_rate_lock = threading.Lock()
_request_times = defaultdict(deque)


def enforce_rate_limit(key_id: int, tier: str):
    limit = RATE_LIMITS[tier]
    now = time.monotonic()
    window_start = now - 1.0

    with _rate_lock:
        timestamps = _request_times[key_id]
        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()

        if len(timestamps) >= limit:
            retry_after = max(1, int(timestamps[0] + 1.0 - now + 0.999))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: maximum {limit} requests per second.",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
