# ai-generated: 90% - Claude Code drafted, reviewed by me
"""Client for the kb-index dependency (MONITORING-SPEC.md M-01, M-02)."""
import os

import httpx

from .domain import ApiError

KB_INDEX_URL = os.environ.get("KB_INDEX_URL", "http://kb-index:8080").rstrip("/")
# At least 2 s (M-02); generous beyond that so a slow upstream answer is still observed, not timed out by us.
_client = httpx.AsyncClient(timeout=10.0)


async def search(q: str) -> list:
    """Exactly one GET to kb-index, no cache, no retry; any failure becomes 502 upstream_unavailable."""
    try:
        response = await _client.get(f"{KB_INDEX_URL}/search", params={"q": q})
    except httpx.HTTPError:
        raise ApiError(502, "upstream_unavailable", "kb-index did not answer") from None
    if response.status_code != 200:
        raise ApiError(502, "upstream_unavailable", f"kb-index answered {response.status_code}")
    return response.json()["hits"]
