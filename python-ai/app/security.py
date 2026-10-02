import secrets
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from app.config import settings

_hits: dict[str, deque] = defaultdict(deque)


def _check_limit(bucket: str, limit: int, window: int = 60) -> None:
    """Allow at most `limit` requests per `window` seconds for this bucket."""
    now = time.monotonic()
    hits = _hits[bucket]
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
        retry_after = int(window - (now - hits[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


async def verify_api_key(request: Request, x_api_key: str = Header(...)):
    client = request.client.host if request.client else "unknown"

    # Count every attempt (even wrong keys) so the key cannot be guessed quickly
    _check_limit(f"all:{client}", settings.rate_limit_per_minute)

    if not secrets.compare_digest(x_api_key.encode(), settings.service_api_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Workflow runs use the language model, so they get a stricter limit
    if request.url.path == "/agent/run":
        _check_limit(f"run:{client}", settings.run_limit_per_minute)