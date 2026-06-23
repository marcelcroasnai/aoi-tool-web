"""
AOI Tool - sync_pm_type
Option B pass: update pm_type in pp_pm after both pp + cli syncs are done.

Logic per pp_pm row:
    1. If (pm_name, pp_name) exists in cli_local  → pm_type = 'local'
    2. Elif (pm_name, cli)   exists in cli_global → pm_type = 'global'
       where cli comes from the parent pp row
    3. Else → pm_type stays NULL (critical error — PM not found in any CLI)

NULL pm_type after this pass = PM missing from both cli_global and cli_local.
sync_errors will generate a Critical error for these rows.

Runs entirely as SQL UPDATE statements — no Python-level row iteration.
"""

import time
import logging

from db.schema   import get_conn
from db.sync_log import start_sync, finish_sync, fail_sync

logger = logging.getLogger(__name__)


# ─── Public entry point ───────────────────────────────────────────────────────

def sync_pm_type() -> None:
    """Update pm_type for all NULL rows in pp_pm."""
    t_start = time.time()
    log_id  = start_sync("pm_type")

    try:
        total, local_count, global_count, missing_count = _run()
        finish_sync(
            log_id, "pm_type",
            total      = total,
            changed    = local_count + global_count,
            duration_s = time.time() - t_start,
        )
        logger.info(
            f"[sync_pm_type] done — "
            f"total={total} "
            f"global={global_count} "
            f"local={local_count} "
            f"missing={missing_count}"
        )
        if missing_count > 0:
            logger.warning(
                f"[sync_pm_type] {missing_count} PM not found in any CLI — "
                f"will generate Critical errors at AP inspection"
            )
    except Exception as e:
        fail_sync(log_id, "pm_type", str(e), time.time() - t_start)
        raise


# ─── Core logic ───────────────────────────────────────────────────────────────

def _run() -> tuple[int, int, int, int]:
    conn = get_conn()

    # Reset all pm_type to NULL — full re-evaluation on every pass
    # This ensures changes in cli_global/cli_local are always reflected
    with conn:
        conn.execute("UPDATE pp_pm SET pm_type = NULL")

    total = conn.execute("SELECT COUNT(*) FROM pp_pm").fetchone()[0]

    if total == 0:
        logger.info("[sync_pm_type] pp_pm is empty — nothing to update")
        return 0, 0, 0, 0

    logger.info(f"[sync_pm_type] evaluating {total} pp_pm rows …")

    with conn:
        # Pass 1 — mark 'local': PM exists in cli_local for this exact PP
        conn.execute(
            """
            UPDATE pp_pm
            SET pm_type = 'local'
            WHERE EXISTS (
                SELECT 1 FROM cli_local cl
                WHERE cl.pm_name = pp_pm.pm_name
                  AND cl.pp_name = pp_pm.pp_name
            )
            """
        )

        # Pass 2 — mark 'global': PM exists in cli_global for this PP's CLI
        # Only rows not already marked 'local'
        conn.execute(
            """
            UPDATE pp_pm
            SET pm_type = 'global'
            WHERE pm_type IS NULL
              AND EXISTS (
                  SELECT 1 FROM cli_global cg
                  JOIN pp ON pp.pp_name = pp_pm.pp_name
                  WHERE cg.pm_name = pp_pm.pm_name
                    AND cg.cli     = pp.cli
              )
            """
        )
        # Rows still NULL after both passes = PM missing from any CLI

    local_count  = conn.execute(
        "SELECT COUNT(*) FROM pp_pm WHERE pm_type = 'local'"
    ).fetchone()[0]
    global_count = conn.execute(
        "SELECT COUNT(*) FROM pp_pm WHERE pm_type = 'global'"
    ).fetchone()[0]
    missing_count = conn.execute(
        "SELECT COUNT(*) FROM pp_pm WHERE pm_type IS NULL"
    ).fetchone()[0]

    return total, local_count, global_count, missing_count
