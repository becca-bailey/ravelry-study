"""Rate-limited, cache-first Ravelry API client.

Adapted from the Wayback client pattern in language-of-work: module-level
throttle, retries with backoff, and every response body cached to
data/raw/api/ keyed by sha256(path + sorted params) with a JSONL manifest.
Cached responses are the permanent record of what Ravelry said on
collection day; re-runs never re-fetch.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from datetime import datetime, timezone

import httpx

from . import config

_last_request_at = 0.0
_interval_s = config.REQUEST_INTERVAL_S


def _throttle() -> None:
    global _last_request_at
    wait = _interval_s - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _cache_key(path: str, params: dict) -> str:
    canonical = path + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha256(canonical.encode()).hexdigest()


class RavelryClient:
    def __init__(self, use_cache: bool = True, scope: str = "readonly"):
        user, password = config.api_credentials(scope)
        self._client = httpx.Client(
            base_url=config.API_BASE, auth=(user, password), timeout=60
        )
        self.use_cache = use_cache
        config.RAW_API_DIR.mkdir(parents=True, exist_ok=True)
        config.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        self._manifest_path = config.MANIFEST_DIR / "api_fetches.jsonl"

    def get_json(self, path: str, **params) -> dict:
        key = _cache_key(path, params)
        cache_file = config.RAW_API_DIR / f"{key}.json.gz"
        if self.use_cache and cache_file.exists():
            return json.loads(gzip.decompress(cache_file.read_bytes()))
        body, status = self._fetch(path, params)
        cache_file.write_bytes(gzip.compress(body))
        self._log(path, params, key, status)
        return json.loads(body)

    def _fetch(self, path: str, params: dict) -> tuple[bytes, int]:
        global _interval_s
        for attempt in range(config.MAX_RETRIES):
            _throttle()
            try:
                resp = self._client.get(path, params=params)
            except httpx.HTTPError:
                if attempt == config.MAX_RETRIES - 1:
                    raise
                time.sleep(2**attempt)
                continue
            if resp.status_code == 429:
                # back off for the rest of the run, not just this request
                _interval_s *= 2
                time.sleep(5 * (attempt + 1))
                continue
            if resp.status_code >= 500:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp.content, resp.status_code
        raise RuntimeError(f"gave up on {path} after {config.MAX_RETRIES} attempts")

    def _log(self, path: str, params: dict, key: str, status: int) -> None:
        record = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "params": params,
            "cache_key": key,
            "status": status,
        }
        with self._manifest_path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    # --- typed surface -----------------------------------------------------

    def search_patterns(self, **filters) -> dict:
        return self.get_json("/patterns/search.json", **filters)

    def get_pattern(self, pattern_id: int) -> dict:
        return self.get_json(f"/patterns/{pattern_id}.json")

    def get_designer(self, designer_id: int) -> dict:
        return self.get_json(f"/designers/{designer_id}.json")

    def get_person(self, username: str) -> dict:
        return self.get_json(f"/people/{username}.json")

    def get_raw(self, path: str, **params) -> dict:
        """Escape hatch for recon of undocumented endpoints."""
        return self.get_json(path, **params)
