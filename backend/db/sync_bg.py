"""
AOI Tool - sync_bg
Step 1: Scan bginfo folder → populate/update table `bg`.

Source:   bg_info_path / {bg_8nr} / {bg_idx} / pl.txt
Trigger:  PP sync start, or manual full sync

Logic:
  - Scan all BG folders in bginfo
  - For each BG compare mtime_pl against DB
  - New or changed → parse pl.txt, upsert row
  - BG no longer in bginfo → delete from DB
  - pp_list is left empty here — filled by sync_pp (Step 2)
"""

import os
import time
import logging
from datetime import datetime, timezone

from modules.app_context import get_ctx
from modules.intranet    import _parse_pl_file, _load_kunde_map
from db.schema           import get_conn
from db.sync_log         import start_sync, finish_sync, fail_sync

logger = logging.getLogger(__name__)


# ─── Public entry point ───────────────────────────────────────────────────────

def sync_bg() -> None:
    """Sync bg table from bginfo pl.txt files."""
    t_start  = time.time()
    log_id   = start_sync("pp")   # bg sync is part of the "pp" sync type
    counters = {"total": 0, "changed": 0, "new": 0, "deleted": 0}

    try:
        _run(counters)
        finish_sync(
            log_id, "pp",
            total   = counters["total"],
            changed = counters["changed"],
            new     = counters["new"],
            deleted = counters["deleted"],
            duration_s = time.time() - t_start,
        )
    except Exception as e:
        fail_sync(log_id, "pp", str(e), time.time() - t_start)
        raise


# ─── Core logic ───────────────────────────────────────────────────────────────

def _run(counters: dict) -> None:
    ctx       = get_ctx()
    conn      = get_conn()
    kunde_map = _load_kunde_map(ctx)
    bginfo    = ctx.bg_info_path

    if not os.path.isdir(bginfo):
        raise RuntimeError(f"sync_bg: bginfo path not found: {bginfo}")

    # ── 1. Scan bginfo → build set of all valid bg_names ──────────────────────
    bginfo_bg_set: set[str] = set()

    for bg_8nr in os.listdir(bginfo):
        bg_8nr_path = os.path.join(bginfo, bg_8nr)
        if not os.path.isdir(bg_8nr_path) or not bg_8nr.isdigit():
            continue
        for bg_idx in os.listdir(bg_8nr_path):
            bg_idx_path = os.path.join(bg_8nr_path, bg_idx)
            if not os.path.isdir(bg_idx_path):
                continue
            pl_file = os.path.join(bg_idx_path, "pl.txt")
            if os.path.isfile(pl_file):
                bg_name = f"{bg_8nr}.{bg_idx}"
                bginfo_bg_set.add(bg_name)

    logger.info(f"[sync_bg] {len(bginfo_bg_set)} BG found in bginfo")
    counters["total"] = len(bginfo_bg_set)

    # ── 2. Load existing DB rows (bg_name → mtime_pl) ─────────────────────────
    db_bg: dict[str, float | None] = {}
    for row in conn.execute("SELECT bg_name, mtime_pl FROM bg").fetchall():
        db_bg[row["bg_name"]] = row["mtime_pl"]

    # ── 3. Determine deleted BG (in DB, not in bginfo) ────────────────────────
    deleted = set(db_bg.keys()) - bginfo_bg_set
    if deleted:
        logger.info(f"[sync_bg] deleting {len(deleted)} inactive BG: {sorted(deleted)}")
        with conn:
            for bg_name in deleted:
                conn.execute("DELETE FROM bg WHERE bg_name = ?", (bg_name,))
                logger.debug(f"[sync_bg] deleted BG: {bg_name}")
        counters["deleted"] = len(deleted)

    # ── 4. Process each BG in bginfo ──────────────────────────────────────────
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for bg_name in sorted(bginfo_bg_set):
        bg_8nr, bg_idx = bg_name.split(".")
        pl_file = os.path.join(bginfo, bg_8nr, bg_idx, "pl.txt")

        current_mtime = os.path.getmtime(pl_file)
        db_mtime      = db_bg.get(bg_name)
        is_new        = bg_name not in db_bg

        # Skip if mtime unchanged
        if not is_new and db_mtime is not None and abs(current_mtime - db_mtime) < 1.0:
            continue

        # Parse pl.txt
        active, kunde, project_name, dmc, medi, lp_nr, bot, top, errors = \
            _parse_pl_file(bg_name, pl_file, kunde_map)

        if not active:
            logger.debug(f"[sync_bg] {bg_name}: inactive (Z_ marker)")
            # Upsert with active=0 so sync_errors can generate Error_9
            with conn:
                conn.execute(
                    """
                    INSERT INTO bg (bg_name, active, mtime_pl, synced_at)
                    VALUES (?, 0, ?, ?)
                    ON CONFLICT(bg_name) DO UPDATE SET
                        active    = 0,
                        mtime_pl  = excluded.mtime_pl,
                        synced_at = excluded.synced_at
                    """,
                    (bg_name, current_mtime, synced_at),
                )
            if is_new:
                counters["new"] += 1
            else:
                counters["changed"] += 1
            counters["total"] -= 1
            continue

        # Flatten comp_bot / comp_top from {ihl_nr: [refs]} to sorted comma-sep string
        comp_bot = _flatten_comps(bot)
        comp_top = _flatten_comps(top)

        with conn:
            conn.execute(
                """
                INSERT INTO bg (
                    bg_name, active, kunde, lp_nr, medi, dmc,
                    comp_bot, comp_top, project_name,
                    mtime_pl, synced_at
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bg_name) DO UPDATE SET
                    active       = 1,
                    kunde        = excluded.kunde,
                    lp_nr        = excluded.lp_nr,
                    medi         = excluded.medi,
                    dmc          = excluded.dmc,
                    comp_bot     = excluded.comp_bot,
                    comp_top     = excluded.comp_top,
                    project_name = excluded.project_name,
                    mtime_pl     = excluded.mtime_pl,
                    synced_at    = excluded.synced_at
                """,
                (
                    bg_name, kunde, lp_nr,
                    int(medi), int(dmc),
                    comp_bot, comp_top,
                    project_name,
                    current_mtime, synced_at,
                ),
            )

        if is_new:
            counters["new"]     += 1
            logger.debug(f"[sync_bg] NEW     {bg_name}  kunde={kunde}")
        else:
            counters["changed"] += 1
            logger.debug(f"[sync_bg] UPDATED {bg_name}  kunde={kunde}")

    logger.info(
        f"[sync_bg] done — "
        f"total={counters['total']} "
        f"new={counters['new']} "
        f"changed={counters['changed']} "
        f"deleted={counters['deleted']}"
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _flatten_comps(comp_dict: dict) -> str:
    """
    Flatten {ihl_nr: [ref, ...]} → sorted comma-separated string of unique refs.
    e.g. {"123": ["R1", "C2"], "456": ["R1", "D3"]} → "C2, D3, R1"
    """
    refs: set[str] = set()
    for ref_list in comp_dict.values():
        refs.update(ref_list)
    return ", ".join(sorted(refs))
