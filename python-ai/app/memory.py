import json
import math
import re
import threading
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas import (
    MemorySearchRequest,
    MemorySearchResult,
    MemoryStoreRequest,
    MemoryStoreResponse,
)

# Memories are saved in python-ai/data/memory.json
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "memory.json"
DIM = 512
STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "of", "to", "for", "and", "or", "with", "them",
    "it", "is", "are", "be", "how", "should", "i", "me", "my", "we", "you", "this",
    "that", "then", "from", "by", "as",
}
_lock = threading.Lock()


def embed(text: str) -> dict[int, float]:
    """Turn text into a small numeric fingerprint so similar texts can be compared."""
    vec: dict[int, float] = {}
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token in STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]  # crude plural handling: emails -> email
        index = zlib.crc32(token.encode()) % DIM
        vec[index] = vec.get(index, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {i: round(v / norm, 4) for i, v in vec.items()}


def _load() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save(items: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(items), encoding="utf-8")


def store_memory(req: MemoryStoreRequest) -> MemoryStoreResponse:
    item = {
        "id": str(uuid.uuid4()),
        "user_id": req.user_id,
        "type": req.type,
        "text": req.text,
        "metadata": req.metadata,
        "embedding": [[i, v] for i, v in embed(req.text).items()],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    return MemoryStoreResponse(id=item["id"], total_memories=len(items))


def search_memories(
    query: str,
    user_id: Optional[str] = None,
    types: Optional[list[str]] = None,
    top_k: int = 3,
    min_score: float = 0.2,
) -> list[MemorySearchResult]:
    q = embed(query)
    with _lock:
        items = _load()

    scored = []
    for item in items:
        if item["user_id"] != user_id:
            continue
        if types and item["type"] not in types:
            continue
        score = sum(q.get(i, 0.0) * v for i, v in item["embedding"])
        if score >= min_score:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        MemorySearchResult(
            id=item["id"],
            type=item["type"],
            text=item["text"],
            score=round(score, 3),
            metadata=item["metadata"],
            created_at=item["created_at"],
        )
        for score, item in scored[:top_k]
    ]


def search_from_request(req: MemorySearchRequest) -> list[MemorySearchResult]:
    return search_memories(
        req.query,
        user_id=req.user_id,
        types=[req.type] if req.type else None,
        top_k=req.top_k,
    )