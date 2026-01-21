# evaluator/utils.py
import time
import httpx
import logging
import asyncio
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("case.optimizer")

class AsyncTTLCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self.store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        row = self.store.get(key)
        if not row: 
            return None
        if time.time() - row["ts"] > self.ttl:
            del self.store[key]
            return None
        return row["val"]

    def set(self, key: str, val: Any):
        self.store[key] = {"ts": time.time(), "val": val}

    def clear(self):
        self.store.clear()

    def stats(self):
        now = time.time()
        return [
            {
                "key": k,
                "age_seconds": round(now - row["ts"], 2),
                "has_val": row["val"] is not None
            }
            for k, row in self.store.items()
        ]

# Global shared cache instance
CACHE = AsyncTTLCache()

async def fetch_json(url: str, params: Optional[dict] = None) -> Dict:
    """
    Shared async HTTP fetcher with caching.
    """
    cache_key = f"{url}:{str(params)}"
    cached = CACHE.get(cache_key)
    if cached:
        return cached

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            CACHE.set(cache_key, data)
            return data
        except httpx.HTTPError as e:
            logger.error(f"HTTP Error fetching {url}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return {}