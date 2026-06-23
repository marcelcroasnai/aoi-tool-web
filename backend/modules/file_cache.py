"""
AOI Tool - File Cache

Two-level cache for parsed file data.

L1: memory dict  — instant access, lost on restart
L2: disk JSON    — persistent across restarts

Cache key   = real file path
Cache value = parsed result (not raw file content)
Invalidation = mtime + size via os.stat()

Supported parsed types (must be JSON-serializable):
  str, int, None, list, dict — all safe for JSON round-trip.
  Tuples are stored as lists (JSON has no tuple type) — callers must handle this.
"""

import os
import json
import threading
import logging
from typing import Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
_CACHE_DIR   = Path(__file__).parent.parent / "cache"
_CACHE_FILE  = _CACHE_DIR / "file_cache.json"
_WRITE_BATCH = 50   # flush to disk every N new entries

# ─── State ────────────────────────────────────────────────────────────────────
# { path: { "mtime": float, "size": int, "data": Any } }
_l1:   dict = {}
_lock  = threading.Lock()
_dirty = 0


# ─── Public API ───────────────────────────────────────────────────────────────

def get(path: str) -> Optional[Any]:
    """
    Return cached parsed data for a real file path.
    Returns None on cache miss or if the file has changed (mtime/size mismatch).
    """
    try:
        st = os.stat(path)
    except OSError:
        return None

    with _lock:
        entry = _l1.get(path)
        if entry and entry["mtime"] == st.st_mtime and entry["size"] == st.st_size:
            return entry["data"]

    return None


def put(path: str, data: Any) -> None:
    """
    Store parsed data for a real file path.
    Flushes to disk every _WRITE_BATCH new entries.
    """
    global _dirty
    try:
        st = os.stat(path)
    except OSError:
        return

    with _lock:
        _l1[path] = {"mtime": st.st_mtime, "size": st.st_size, "data": data}
        _dirty += 1
        should_flush = _dirty >= _WRITE_BATCH

    if should_flush:
        flush_to_disk()


def invalidate(path: str) -> None:
    """Remove a single entry from L1."""
    with _lock:
        _l1.pop(path, None)


def clear() -> None:
    """Clear all cache — memory and disk."""
    global _dirty
    with _lock:
        _l1.clear()
        _dirty = 0
    if _CACHE_FILE.exists():
        _CACHE_FILE.unlink()
    logger.info("File cache cleared.")


def stats() -> dict:
    with _lock:
        return {
            "entries_l1":    len(_l1),
            "dirty":         _dirty,
            "cache_file":    str(_CACHE_FILE),
            "cache_size_kb": round(_CACHE_FILE.stat().st_size / 1024, 1)
                             if _CACHE_FILE.exists() else 0,
        }


def flush_to_disk() -> None:
    """Write L1 to disk (L2)."""
    global _dirty
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            snapshot = dict(_l1)
            _dirty   = 0

        serializable = {}
        for path, entry in snapshot.items():
            try:
                json.dumps(entry["data"])
                serializable[path] = entry
            except (TypeError, ValueError):
                pass   # skip non-serializable entries

        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False)

        logger.debug(f"Cache flushed to disk: {len(serializable)} entries")
    except Exception as e:
        logger.error(f"Error flushing cache to disk: {e}")


def load_from_disk() -> None:
    """Load L2 into L1 at startup, validating each entry against the real file."""
    global _dirty
    if not _CACHE_FILE.exists():
        logger.info("No cache file found — starting with empty cache.")
        return

    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        loaded = skipped = 0
        with _lock:
            for path, entry in data.items():
                try:
                    st = os.stat(path)
                    if st.st_mtime == entry["mtime"] and st.st_size == entry["size"]:
                        _l1[path] = entry
                        loaded += 1
                    else:
                        skipped += 1   # file changed
                except OSError:
                    skipped += 1       # file deleted
            _dirty = 0

        logger.info(f"Cache loaded from disk: {loaded} valid, {skipped} expired/missing")
    except Exception as e:
        logger.error(f"Error loading cache from disk: {e}")


def file_exists_cached(path: str) -> bool:
    """
    Check file existence with cache.
    Only caches positive results (True) — a missing file may appear later.
    """
    cached = get(path + "::exists")
    if cached is True:
        return True
    exists = os.path.exists(path)
    if exists:
        put(path + "::exists", True)
    return exists


# ─── Startup ──────────────────────────────────────────────────────────────────
load_from_disk()
