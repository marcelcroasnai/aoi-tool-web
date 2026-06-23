"""
AOI Tool - Sync Manager
Orchestrates all sync steps in the correct order.

Sync types:
    "pp"      — Step 1 (bg) + Step 2+3 (pp + pp_pm)
    "cli"     — Step 4 (cli_global) + Step 5 (cli_local)
    "pm_type" — Step 6: update pm_type in pp_pm after both pp + cli are done
    "ap"      — Step 7: AP refresh from Intranet + error generation
    "full"    — pp + cli + pm_type in correct order

All sync functions run synchronously. Call run_sync() from a
FastAPI BackgroundTask so it doesn't block the event loop.

Usage:
    from db.manager import run_sync
    background_tasks.add_task(run_sync, "full")
"""

import logging
import time

from db.schema   import init_schema
from db.sync_log import get_running_syncs

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Call once at application startup.
    Creates schema if not present, logs DB path.
    """
    from db.schema import get_db_path
    init_schema()
    logger.info(f"DB: ready at {get_db_path()}")


def run_sync(sync_type: str = "full") -> None:
    """
    Run one or more sync steps.

    sync_type:
        "pp"      — bg + pp + pp_pm
        "cli"     — cli_global + cli_local
        "pm_type" — update pm_type pass
        "ap"      — AP refresh + error generation
        "full"    — cli → pp → pm_type  (ap is always manual only)
    """
    logger.info(f"[manager] run_sync called: type='{sync_type}'")

    # Guard: don't start a new sync of the same type while one is running
    running = get_running_syncs()
    running_types = {r["sync_type"] for r in running}

    if sync_type in running_types:
        logger.warning(f"[manager] '{sync_type}' sync already running — skipped")
        return

    t_start = time.time()

    try:
        if sync_type == "full":
            _run_cli_sync()
            _run_pp_sync()
            _run_pm_type_pass()

        elif sync_type == "pp":
            _run_pp_sync()

        elif sync_type == "cli":
            _run_cli_sync()

        elif sync_type == "pm_type":
            _run_pm_type_pass()

        elif sync_type == "ap":
            _run_ap_sync()

        else:
            logger.error(f"[manager] unknown sync_type: '{sync_type}'")
            return

    except Exception as e:
        logger.exception(f"[manager] run_sync('{sync_type}') crashed: {e}")
        return

    elapsed = time.time() - t_start
    logger.info(f"[manager] run_sync('{sync_type}') finished in {elapsed:.1f}s")


# ─── Internal step runners ────────────────────────────────────────────────────

def _run_pp_sync() -> None:
    """Step 1 (bg) + Steps 2+3 (pp + pp_pm)."""
    logger.info("[manager] → starting PP sync (bg + pp + pp_pm)")
    from db.sync_bg import sync_bg
    from db.sync_pp import sync_pp
    sync_bg()
    sync_pp()
    logger.info("[manager] ✓ PP sync complete")


def _run_cli_sync() -> None:
    """Steps 4+5 (cli_global + cli_local)."""
    logger.info("[manager] → starting CLI sync (cli_global + cli_local)")
    from db.sync_cli import sync_cli_global, sync_cli_local
    sync_cli_global()
    sync_cli_local()
    logger.info("[manager] ✓ CLI sync complete")


def _run_pm_type_pass() -> None:
    """Option B pass — update pm_type in pp_pm after pp + cli are both done."""
    logger.info("[manager] → starting pm_type update pass")
    from db.sync_pm_type import sync_pm_type
    sync_pm_type()
    logger.info("[manager] ✓ pm_type pass complete")


def _run_ap_sync() -> None:
    """AP refresh from Intranet + error generation."""
    logger.info("[manager] → starting AP sync")
    from db.sync_errors import sync_errors
    sync_errors()
    logger.info("[manager] ✓ AP sync complete")
