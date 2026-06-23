"""
AOI Tool - Sync Log helpers
All sync modules use these helpers to record their progress in sync_log.
"""

import logging
from datetime import datetime, timezone

from db.schema import get_conn

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def start_sync(sync_type: str) -> int:
    """
    Insert a 'running' row into sync_log.
    Returns the new row id — pass it to finish_sync() or fail_sync().
    """
    conn = get_conn()
    started_at = _now()
    cur = conn.execute(
        """
        INSERT INTO sync_log (sync_type, status, started_at)
        VALUES (?, 'running', ?)
        """,
        (sync_type, started_at),
    )
    conn.commit()
    log_id = cur.lastrowid
    logger.info(f"[sync_log] {sync_type.upper()} sync started  (id={log_id})")
    return log_id


def finish_sync(
    log_id:    int,
    sync_type: str,
    total:     int = 0,
    changed:   int = 0,
    new:       int = 0,
    deleted:   int = 0,
    duration_s: float = 0.0,
) -> None:
    """Mark a sync run as done and record its counters."""
    conn = get_conn()
    finished_at = _now()
    conn.execute(
        """
        UPDATE sync_log
        SET status      = 'done',
            total       = ?,
            changed     = ?,
            new         = ?,
            deleted     = ?,
            duration_s  = ?,
            finished_at = ?
        WHERE id = ?
        """,
        (total, changed, new, deleted, round(duration_s, 2), finished_at, log_id),
    )
    conn.commit()
    logger.info(
        f"[sync_log] {sync_type.upper()} sync done  (id={log_id}) "
        f"total={total} changed={changed} new={new} deleted={deleted} "
        f"duration={duration_s:.1f}s"
    )


def fail_sync(log_id: int, sync_type: str, error_msg: str, duration_s: float = 0.0) -> None:
    """Mark a sync run as failed and record the error message."""
    conn = get_conn()
    finished_at = _now()
    conn.execute(
        """
        UPDATE sync_log
        SET status      = 'error',
            error_msg   = ?,
            duration_s  = ?,
            finished_at = ?
        WHERE id = ?
        """,
        (error_msg[:1000], round(duration_s, 2), finished_at, log_id),
    )
    conn.commit()
    logger.error(
        f"[sync_log] {sync_type.upper()} sync FAILED (id={log_id}): {error_msg}"
    )


def get_last_sync(sync_type: str) -> dict | None:
    """
    Return the most recent completed sync_log row for the given type,
    or None if no sync has ever run.
    """
    conn = get_conn()
    row = conn.execute(
        """
        SELECT * FROM sync_log
        WHERE  sync_type = ?
          AND  status    != 'running'
        ORDER BY id DESC
        LIMIT 1
        """,
        (sync_type,),
    ).fetchone()
    return dict(row) if row else None


def get_running_syncs() -> list[dict]:
    """Return all currently running sync rows (status = 'running')."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sync_log WHERE status = 'running' ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_sync_status() -> dict:
    """
    Return a summary of the last sync for each type.
    Used by the frontend status bar via /api/sync/status.
    """
    result = {}
    for sync_type in ("pp", "cli", "ap", "pm_type"):
        result[sync_type] = get_last_sync(sync_type)
    result["running"] = get_running_syncs()
    return result
