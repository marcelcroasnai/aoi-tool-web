"""
AOI Tool - sync_pp
Steps 2 + 3: Scan CadRuest → populate/update tables `pp`, `pp_pm`,
             then update `bg.pp_list` for every BG.

Source:   cad_ruest_path / {folder} / {pp_name}.{ext}
Trigger:  PP sync (after sync_bg)

Logic per PP:
  - Collect mtime of all 10 file extensions
  - Compare each mtime against DB
  - If nothing changed → skip
  - If new or any file changed → re-parse, upsert pp row,
    delete + reinsert pp_pm rows
  - Deleted folders → delete from pp (cascades to pp_pm)
  - After all PP processed → update bg.pp_list per BG
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from modules.app_context import get_ctx
from modules.pp_inspect  import (
    get_pp_list,
    _resolve_locked_name,
    _is_locked_folder,
    _read_cad,
    _read_desc,
    _read_def,
    _read_hinweis,
)
from db.schema   import get_conn
from db.sync_log import start_sync, finish_sync, fail_sync

logger = logging.getLogger(__name__)

# File extensions tracked per PP (order matches DB columns)
_EXTENSIONS = ["bbs", "cad", "def", "desc", "mod", "par", "pre", "ref", "size"]


# ─── Public entry point ───────────────────────────────────────────────────────

def sync_pp() -> None:
    """Sync pp + pp_pm tables from CadRuest, then update bg.pp_list."""
    t_start  = time.time()
    log_id   = start_sync("pp")
    counters = {"total": 0, "changed": 0, "new": 0, "deleted": 0}

    try:
        _run(counters)
        finish_sync(
            log_id, "pp",
            total      = counters["total"],
            changed    = counters["changed"],
            new        = counters["new"],
            deleted    = counters["deleted"],
            duration_s = time.time() - t_start,
        )
    except Exception as e:
        fail_sync(log_id, "pp", str(e), time.time() - t_start)
        raise


# ─── Core logic ───────────────────────────────────────────────────────────────

def _run(counters: dict) -> None:
    ctx      = get_ctx()
    conn     = get_conn()
    cad_root = ctx.cad_ruest_path

    if not os.path.isdir(cad_root):
        raise RuntimeError(f"sync_pp: CadRuest path not found: {cad_root}")

    # ── 1. Get full PP folder list from CadRuest ───────────────────────────────
    cad_folders: set[str] = set(get_pp_list())
    logger.info(f"[sync_pp] {len(cad_folders)} PP folders found in CadRuest")
    counters["total"] = len(cad_folders)

    # ── 2. Load existing DB state (pp_name → mtime dict) ──────────────────────
    db_pp: dict[str, dict] = {}
    for row in conn.execute(
        "SELECT pp_name, mtime_bbs, mtime_cad, mtime_def, mtime_desc, "
        "       mtime_mod, mtime_par, mtime_pre, mtime_ref, mtime_size, "
        "       mtime_hinweis FROM pp"
    ).fetchall():
        db_pp[row["pp_name"]] = dict(row)

    # ── 3. Detect deleted PP ───────────────────────────────────────────────────
    # Map canonical pp_name → folder for everything in CadRuest
    folder_map: dict[str, str] = {}   # canonical pp_name → folder
    for folder in cad_folders:
        pp_name = _resolve_locked_name(folder)
        folder_map[pp_name] = folder

    deleted = set(db_pp.keys()) - set(folder_map.keys())
    if deleted:
        logger.info(f"[sync_pp] deleting {len(deleted)} inactive PP")
        with conn:
            for pp_name in deleted:
                conn.execute("DELETE FROM pp WHERE pp_name = ?", (pp_name,))
                logger.debug(f"[sync_pp] deleted PP: {pp_name}")
        counters["deleted"] = len(deleted)

    # ── 4. Process each PP ────────────────────────────────────────────────────
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for pp_name, folder in sorted(folder_map.items()):
        pp_path = os.path.join(cad_root, folder)

        if not os.path.isdir(pp_path):
            logger.warning(f"[sync_pp] folder missing on disk: {pp_path}")
            continue

        locked = _is_locked_folder(folder)

        # Collect current mtimes for all tracked files
        current_mtimes = _collect_mtimes(pp_path, pp_name)

        # Compare against DB
        is_new = pp_name not in db_pp
        if not is_new and not _any_mtime_changed(current_mtimes, db_pp[pp_name]):
            continue   # nothing changed — skip

        # ── Parse files ───────────────────────────────────────────────────────
        file_base = pp_name

        _, _, pm_dict, _ = _read_cad(
            pp_name, "", os.path.join(pp_path, file_base + ".cad")
        )
        cli, _     = _read_desc(
            pp_name, "", os.path.join(pp_path, file_base + ".desc")
        )
        nutzen, _  = _read_def(
            pp_name, "", os.path.join(pp_path, file_base + ".def")
        )
        hinweis    = _read_hinweis(pp_path)
        oldest_mod = _parse_mod(os.path.join(pp_path, file_base + ".mod"))

        # Build comp string (all refs from cad, single side)
        comp = _build_comp_str(pm_dict)

        # ── Upsert pp row ─────────────────────────────────────────────────────
        with conn:
            conn.execute(
                """
                INSERT INTO pp (
                    pp_name, folder, locked, cli, nutzen_in_lp, hinweis,
                    oldest_mod, comp,
                    mtime_bbs, mtime_cad, mtime_def, mtime_desc,
                    mtime_mod, mtime_par, mtime_pre, mtime_ref,
                    mtime_size, mtime_hinweis,
                    synced_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?
                )
                ON CONFLICT(pp_name) DO UPDATE SET
                    folder       = excluded.folder,
                    locked       = excluded.locked,
                    cli          = excluded.cli,
                    nutzen_in_lp = excluded.nutzen_in_lp,
                    hinweis      = excluded.hinweis,
                    oldest_mod   = excluded.oldest_mod,
                    comp         = excluded.comp,
                    mtime_bbs    = excluded.mtime_bbs,
                    mtime_cad    = excluded.mtime_cad,
                    mtime_def    = excluded.mtime_def,
                    mtime_desc   = excluded.mtime_desc,
                    mtime_mod    = excluded.mtime_mod,
                    mtime_par    = excluded.mtime_par,
                    mtime_pre    = excluded.mtime_pre,
                    mtime_ref    = excluded.mtime_ref,
                    mtime_size   = excluded.mtime_size,
                    mtime_hinweis= excluded.mtime_hinweis,
                    synced_at    = excluded.synced_at
                """,
                (
                    pp_name, folder, int(locked), cli, nutzen, hinweis,
                    oldest_mod, comp,
                    current_mtimes.get("bbs"),
                    current_mtimes.get("cad"),
                    current_mtimes.get("def"),
                    current_mtimes.get("desc"),
                    current_mtimes.get("mod"),
                    current_mtimes.get("par"),
                    current_mtimes.get("pre"),
                    current_mtimes.get("ref"),
                    current_mtimes.get("size"),
                    current_mtimes.get("hinweis"),
                    synced_at,
                ),
            )

            # ── Delete + reinsert pp_pm only when .cad changed ────────────────
            cad_changed = (
                is_new
                or db_pp.get(pp_name, {}).get("mtime_cad") != current_mtimes.get("cad")
            )
            if cad_changed and pm_dict:
                conn.execute("DELETE FROM pp_pm WHERE pp_name = ?", (pp_name,))
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO pp_pm (pp_name, pm_name, ihl_nr, pm_type, refs_count)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    _flatten_pm_dict(pp_name, pm_dict),
                )
                logger.debug(
                    f"[sync_pp] pp_pm updated for {pp_name}: "
                    f"{len(pm_dict)} PM entries"
                )

        if is_new:
            counters["new"]     += 1
            logger.debug(f"[sync_pp] NEW     {pp_name}")
        else:
            counters["changed"] += 1
            logger.debug(f"[sync_pp] UPDATED {pp_name}")

    # ── 5. Update bg.pp_list for every BG ─────────────────────────────────────
    _update_bg_pp_list(conn, synced_at)

    logger.info(
        f"[sync_pp] done — "
        f"total={counters['total']} "
        f"new={counters['new']} "
        f"changed={counters['changed']} "
        f"deleted={counters['deleted']}"
    )


# ─── bg.pp_list updater ───────────────────────────────────────────────────────

def _update_bg_pp_list(conn, synced_at: str) -> None:
    """
    For every BG in the bg table, find all PP that belong to it using the
    same _find_pp_folders logic as the old pipeline, then write pp_list.
    Reads PP list from DB (pp table) instead of CadRuest.
    """
    logger.info("[sync_pp] updating bg.pp_list …")

    from modules.pp_inspect import _find_pp_folders
    from modules.errors import add_bg_error

    bg_rows = conn.execute("SELECT bg_name FROM bg").fetchall()

    # Use the real CadRuest folder names (incl. _gesperrt suffix / __ quirks) so
    # _find_pp_folders matches by index and returns canonical pp_names.
    pp_list_with_locked = [
        (row["folder"] or row["pp_name"])
        for row in conn.execute("SELECT pp_name, folder FROM pp").fetchall()
    ]

    # Dummy bg_dict for _find_pp_folders (only needs to accept add_bg_error calls)
    class _DummyBgDict(dict):
        def __missing__(self, key):
            self[key] = {"pp_list": [], "errors": []}
            return self[key]

    updated = 0
    with conn:
        for row in bg_rows:
            bg_name = row["bg_name"]
            try:
                bg_nr, bg_idx = bg_name.split(".")
            except ValueError:
                continue

            dummy_bg_dict = _DummyBgDict()
            dummy_bg_dict[bg_name] = {"pp_list": [], "errors": []}

            pp_folders = _find_pp_folders(
                bg_nr, bg_idx, pp_list_with_locked, bg_name, dummy_bg_dict
            )

            # Resolve canonical pp_names from folder results
            pp_names = sorted(pp_name for pp_name, locked, folder in pp_folders)

            conn.execute(
                "UPDATE bg SET pp_list = ?, synced_at = ? WHERE bg_name = ?",
                (", ".join(pp_names) if pp_names else None, synced_at, bg_name),
            )
            updated += 1

    logger.info(f"[sync_pp] bg.pp_list updated for {updated} BG")


# ─── File helpers ─────────────────────────────────────────────────────────────

def _collect_mtimes(pp_path: str, pp_name: str) -> dict[str, Optional[float]]:
    """Return {ext: mtime_or_None} for all tracked file extensions."""
    mtimes: dict[str, Optional[float]] = {}
    for ext in _EXTENSIONS:
        path = os.path.join(pp_path, f"{pp_name}.{ext}")
        mtimes[ext] = os.path.getmtime(path) if os.path.isfile(path) else None
    # hinweis.txt
    hinweis_path = os.path.join(pp_path, "hinweis.txt")
    mtimes["hinweis"] = (
        os.path.getmtime(hinweis_path) if os.path.isfile(hinweis_path) else None
    )
    return mtimes


def _any_mtime_changed(current: dict, db_row: dict) -> bool:
    """Return True if any tracked mtime differs from the DB row."""
    for ext in _EXTENSIONS:
        col = f"mtime_{ext}"
        if abs_diff(current.get(ext), db_row.get(col)) > 1.0:
            return True
    if abs_diff(current.get("hinweis"), db_row.get("mtime_hinweis")) > 1.0:
        return True
    return False


def abs_diff(a: Optional[float], b: Optional[float]) -> float:
    """Safe absolute difference — treats None == None as 0."""
    if a is None and b is None:
        return 0.0
    if a is None or b is None:
        return float("inf")
    return abs(a - b)


# ─── .mod parser ─────────────────────────────────────────────────────────────

def _parse_mod(mod_path: str) -> Optional[str]:
    """
    Parse pp_name.mod and return the oldest exception date as ISO string
    (YYYY-MM-DD), or None if the file doesn't exist or has no entries.

    Line format:
        W  DD.MM.YY_<something>  <rest of line>
    Only lines starting with "W" are exception entries.
    Date is parts[1], split on "_", parsed as %d.%m.%y.
    """
    if not os.path.isfile(mod_path):
        return None

    oldest: Optional[datetime] = None

    try:
        with open(mod_path, "r", encoding="cp1252", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("*"):
                    continue
                parts = line.split()
                if not parts or parts[0] != "W":
                    continue
                if len(parts) < 2:
                    continue
                try:
                    date_str = parts[1].split("_")[0]
                    dt = datetime.strptime(date_str, "%d.%m.%y")
                    if oldest is None or dt < oldest:
                        oldest = dt
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        logger.warning(f"[sync_pp] cannot read .mod {mod_path}: {e}")

    return oldest.strftime("%Y-%m-%d") if oldest else None


# ─── Data helpers ─────────────────────────────────────────────────────────────

def _build_comp_str(pm_dict: dict) -> Optional[str]:
    """
    Flatten pm_dict into a sorted comma-separated string of unique refs.
    pm_dict = { pm_name: { ihl_nr: [ref, ...] } }
    """
    if not pm_dict:
        return None
    refs: set[str] = set()
    for ihl_map in pm_dict.values():
        for ref_list in ihl_map.values():
            refs.update(ref_list)
    return ", ".join(sorted(refs)) or None


def _flatten_pm_dict(pp_name: str, pm_dict: dict) -> list[tuple]:
    """
    Flatten pm_dict into rows for pp_pm.
    pm_dict = { pm_name: { ihl_nr: [refs] } }
    One row per (pp_name, pm_name, ihl_nr) with refs_count.
    """
    rows = []
    for pm_name, ihl_map in pm_dict.items():
        pm_lower = pm_name.lower()
        for ihl_nr, refs in ihl_map.items():
            rows.append((pp_name, pm_lower, ihl_nr or "", None, len(refs)))
    return rows




