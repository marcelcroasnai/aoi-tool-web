"""
AOI Tool - sync_cli
Steps 4 + 5: Scan CliRuest → populate/update tables `cli_global` and `cli_local`.

Folder structure:
    cli_ruest_path/
        {cli}/                          ← one folder per CLI
            {pm_name}.cle               ← global PM definition
            {pm_name}.mac               ← macro file
            {pp_name}/                  ← PP-specific subfolder (local overrides)
                {pm_name}.cle
                {pm_name}.mac

Step 4 — cli_global:
    Every .cle file directly inside a CLI folder (not in a PP subfolder).
    Tracks mtime_cle + mtime of most recently modified .mac file.

Step 5 — cli_local:
    Every .cle file inside a PP subfolder of a CLI folder.
    Same mtime tracking as global.

Sync logic (both steps):
    - Compare mtime_cle and mtime_mac against DB
    - New or changed → re-parse, upsert row
    - PM no longer exists → delete row
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from modules.app_context import get_ctx
from db.schema           import get_conn
from db.sync_log         import start_sync, finish_sync, fail_sync

logger = logging.getLogger(__name__)


# ─── Public entry points ──────────────────────────────────────────────────────

def sync_cli_global() -> None:
    """Step 4: Sync cli_global table from CliRuest top-level .cle files."""
    t_start  = time.time()
    log_id   = start_sync("cli")
    counters = {"total": 0, "changed": 0, "new": 0, "deleted": 0}

    try:
        _run_global(counters)
        finish_sync(
            log_id, "cli",
            total      = counters["total"],
            changed    = counters["changed"],
            new        = counters["new"],
            deleted    = counters["deleted"],
            duration_s = time.time() - t_start,
        )
    except Exception as e:
        fail_sync(log_id, "cli", str(e), time.time() - t_start)
        raise


def sync_cli_local() -> None:
    """Step 5: Sync cli_local table from CliRuest PP-subfolder .cle files."""
    t_start  = time.time()
    log_id   = start_sync("cli")
    counters = {"total": 0, "changed": 0, "new": 0, "deleted": 0}

    try:
        _run_local(counters)
        finish_sync(
            log_id, "cli",
            total      = counters["total"],
            changed    = counters["changed"],
            new        = counters["new"],
            deleted    = counters["deleted"],
            duration_s = time.time() - t_start,
        )
    except Exception as e:
        fail_sync(log_id, "cli", str(e), time.time() - t_start)
        raise


# ─── Step 4: cli_global ───────────────────────────────────────────────────────

def _run_global(counters: dict) -> None:
    ctx      = get_ctx()
    conn     = get_conn()
    cli_root = ctx.cli_ruest_path

    if not os.path.isdir(cli_root):
        raise RuntimeError(f"sync_cli_global: CliRuest path not found: {cli_root}")

    cli_list = _get_cli_list(cli_root)
    logger.info(f"[sync_cli_global] {len(cli_list)} CLI folders found")

    # Load existing DB state: (pm_name, cli) → (mtime_cle, mtime_mac)
    db_state: dict[tuple, tuple] = {}
    for row in conn.execute(
        "SELECT pm_name, cli, mtime_cle, mtime_mac FROM cli_global"
    ).fetchall():
        db_state[(row["pm_name"], row["cli"])] = (row["mtime_cle"], row["mtime_mac"])

    synced_at   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    seen: set[tuple] = set()

    for cli in cli_list:
        cli_path = os.path.join(cli_root, cli)

        for filename in os.listdir(cli_path):
            if not filename.lower().endswith(".cle"):
                continue

            # Skip .cle files inside PP subfolders (those are local)
            if os.path.isdir(os.path.join(cli_path, filename)):
                continue

            pm_name  = os.path.splitext(filename)[0].lower()
            cle_path = os.path.join(cli_path, filename)
            key      = (pm_name, cli)
            seen.add(key)
            counters["total"] += 1

            current_mtime_cle = os.path.getmtime(cle_path)
            active_macros, mtime_mac, last_mac_name = _parse_cle(cle_path, cli_path)

            db_mtime_cle, db_mtime_mac = db_state.get(key, (None, None))
            is_new = key not in db_state

            if (not is_new
                    and abs_diff(current_mtime_cle, db_mtime_cle) < 1.0
                    and abs_diff(mtime_mac, db_mtime_mac) < 1.0):
                continue   # nothing changed

            with conn:
                conn.execute(
                    """
                    INSERT INTO cli_global (
                        pm_name, cli, active_macros,
                        mtime_cle, mtime_mac, last_modified_mac_name,
                        synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(pm_name, cli) DO UPDATE SET
                        active_macros          = excluded.active_macros,
                        mtime_cle              = excluded.mtime_cle,
                        mtime_mac              = excluded.mtime_mac,
                        last_modified_mac_name = excluded.last_modified_mac_name,
                        synced_at              = excluded.synced_at
                    """,
                    (pm_name, cli.lower(), active_macros,
                     current_mtime_cle, mtime_mac, last_mac_name,
                     synced_at),
                )

            if is_new:
                counters["new"] += 1
                logger.debug(f"[sync_cli_global] NEW     {cli}/{pm_name}")
            else:
                counters["changed"] += 1
                logger.debug(f"[sync_cli_global] UPDATED {cli}/{pm_name}")

    # Delete PM no longer present in CliRuest
    deleted_keys = set(db_state.keys()) - seen
    if deleted_keys:
        with conn:
            for pm_name, cli in deleted_keys:
                conn.execute(
                    "DELETE FROM cli_global WHERE pm_name = ? AND cli = ?",
                    (pm_name, cli),
                )
                logger.debug(f"[sync_cli_global] deleted {cli}/{pm_name}")
        counters["deleted"] = len(deleted_keys)

    logger.info(
        f"[sync_cli_global] done — "
        f"total={counters['total']} new={counters['new']} "
        f"changed={counters['changed']} deleted={counters['deleted']}"
    )


# ─── Step 5: cli_local ────────────────────────────────────────────────────────

def _run_local(counters: dict) -> None:
    ctx      = get_ctx()
    conn     = get_conn()
    cli_root = ctx.cli_ruest_path

    if not os.path.isdir(cli_root):
        raise RuntimeError(f"sync_cli_local: CliRuest path not found: {cli_root}")

    cli_list = _get_cli_list(cli_root)
    logger.info(f"[sync_cli_local] {len(cli_list)} CLI folders found")

    # Load existing DB state: (pm_name, pp_name) → (mtime_cle, mtime_mac)
    db_state: dict[tuple, tuple] = {}
    for row in conn.execute(
        "SELECT pm_name, pp_name, mtime_cle, mtime_mac FROM cli_local"
    ).fetchall():
        db_state[(row["pm_name"], row["pp_name"])] = (row["mtime_cle"], row["mtime_mac"])

    synced_at   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    seen: set[tuple] = set()

    for cli in cli_list:
        cli_path = os.path.join(cli_root, cli)

        # Each subfolder that starts with "80" is a PP-specific override folder
        for pp_folder in os.listdir(cli_path):
            pp_subfolder = os.path.join(cli_path, pp_folder)
            if not os.path.isdir(pp_subfolder):
                continue
            if not pp_folder.startswith("80"):
                continue

            # Canonical pp_name (resolve locked folder names)
            pp_name = pp_folder.replace("__", "_", 1).replace("_gesperrt", "")

            for filename in os.listdir(pp_subfolder):
                if not filename.lower().endswith(".cle"):
                    continue

                pm_name  = os.path.splitext(filename)[0].lower()
                cle_path = os.path.join(pp_subfolder, filename)
                key      = (pm_name, pp_name)
                seen.add(key)
                counters["total"] += 1

                current_mtime_cle = os.path.getmtime(cle_path)
                active_macros, mtime_mac, last_mac_name = _parse_cle(
                    cle_path, pp_subfolder
                )

                db_mtime_cle, db_mtime_mac = db_state.get(key, (None, None))
                is_new = key not in db_state

                if (not is_new
                        and abs_diff(current_mtime_cle, db_mtime_cle) < 1.0
                        and abs_diff(mtime_mac, db_mtime_mac) < 1.0):
                    continue

                with conn:
                    conn.execute(
                        """
                        INSERT INTO cli_local (
                            pm_name, pp_name, cli, active_macros,
                            mtime_cle, mtime_mac, last_modified_mac_name,
                            synced_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(pm_name, pp_name) DO UPDATE SET
                            cli                    = excluded.cli,
                            active_macros          = excluded.active_macros,
                            mtime_cle              = excluded.mtime_cle,
                            mtime_mac              = excluded.mtime_mac,
                            last_modified_mac_name = excluded.last_modified_mac_name,
                            synced_at              = excluded.synced_at
                        """,
                        (pm_name, pp_name, cli.lower(), active_macros,
                         current_mtime_cle, mtime_mac, last_mac_name,
                         synced_at),
                    )

                if is_new:
                    counters["new"] += 1
                    logger.debug(f"[sync_cli_local] NEW     {cli}/{pp_name}/{pm_name}")
                else:
                    counters["changed"] += 1
                    logger.debug(f"[sync_cli_local] UPDATED {cli}/{pp_name}/{pm_name}")

    # Delete rows no longer present in CliRuest
    deleted_keys = set(db_state.keys()) - seen
    if deleted_keys:
        with conn:
            for pm_name, pp_name in deleted_keys:
                conn.execute(
                    "DELETE FROM cli_local WHERE pm_name = ? AND pp_name = ?",
                    (pm_name, pp_name),
                )
                logger.debug(f"[sync_cli_local] deleted {pp_name}/{pm_name}")
        counters["deleted"] = len(deleted_keys)

    logger.info(
        f"[sync_cli_local] done — "
        f"total={counters['total']} new={counters['new']} "
        f"changed={counters['changed']} deleted={counters['deleted']}"
    )


# ─── .cle parser ─────────────────────────────────────────────────────────────

def _parse_cle(
    cle_path: str,
    mac_folder: str,
) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """
    Parse a .cle file and return:
        active_macros       — comma-separated sorted list of active macro names
        mtime_mac           — mtime of the most recently modified .mac file
        last_modified_mac_name — name of that .mac file (without extension)

    .cle format (from your Access code):
        Lines with a letter in col 0 describe a PM entry.
        The 4th token (index 3) is the state — non-zero means active.
        The next line contains the macro name as the first token (prefixed with @).

        e.g.:
            GENR  0  0  1
            @14pol_samtec_meni_17_0  ...
        → macro "14pol_samtec_meni_17_0" is active

    Macro short name (stored in active_macros):
        last 3 underscore-separated parts of the full macro name
        e.g. "14pol_samtec_meni_17_0" → "meni_17_0"
    """
    active_macros: list[str] = []
    mac_dates:     list[tuple[float, str]] = []   # (mtime, short_name)

    try:
        with open(cle_path, "r", encoding="cp1252", errors="replace") as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line and line[0].isalpha():
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        state = int(parts[3])
                    except ValueError:
                        i += 1
                        continue

                    if state != 0 and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        next_parts = next_line.split()
                        if next_parts and next_parts[0].startswith("@"):
                            full_macro = next_parts[0][1:].lower()
                            short_name = "_".join(full_macro.split("_")[-3:])

                            if short_name not in active_macros:
                                active_macros.append(short_name)

                            # Check .mac mtime
                            mac_path = os.path.join(mac_folder, full_macro + ".mac")
                            if os.path.isfile(mac_path):
                                mtime = os.path.getmtime(mac_path)
                                mac_dates.append((mtime, short_name))
            i += 1

    except Exception as e:
        logger.warning(f"[sync_cli] cannot read .cle {cle_path}: {e}")

    active_macros_str = ", ".join(sorted(active_macros)) or None

    if mac_dates:
        mac_dates.sort(reverse=True)
        mtime_mac, last_mac_name = mac_dates[0]
    else:
        mtime_mac = last_mac_name = None

    return active_macros_str, mtime_mac, last_mac_name


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_cli_list(cli_root: str) -> list[str]:
    """Return all CLI folder names inside cli_root."""
    return [
        f for f in os.listdir(cli_root)
        if os.path.isdir(os.path.join(cli_root, f))
    ]


def abs_diff(a: Optional[float], b: Optional[float]) -> float:
    if a is None and b is None:
        return 0.0
    if a is None or b is None:
        return float("inf")
    return abs(a - b)
