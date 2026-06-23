"""
AOI Tool - refresh_ap
Targeted AP refresh with per-PP mtime check.

For each BG in the current AP:
  - Find its PP list from DB
  - For each PP: compare all 10 file mtimes on disk vs DB
  - If any differ: re-parse changed files, update DB
  - Then re-run error generation for the full AP
  - Stream progress via SSE generator
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Generator, Optional

from modules.app_context import get_ctx
from modules.pp_inspect  import (
    get_pp_list, _resolve_locked_name,
    _read_cad, _read_desc, _read_def, _read_hinweis,
)
from db.schema   import get_conn
from db.sync_pp  import (
    _collect_mtimes, _any_mtime_changed,
    _flatten_pm_dict, _build_comp_str, _parse_mod,
)

logger = logging.getLogger(__name__)


def refresh_ap_with_progress() -> Generator[str, None, None]:
    """
    SSE generator. Yields lines in the format:
        data: <message>\n\n
    Final event:
        data: __DONE__\n\n
    """
    def event(msg: str) -> str:
        return f"data: {msg}\n\n"

    conn      = get_conn()
    ctx       = get_ctx()
    cad_root  = ctx.cad_ruest_path
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # ── 1. Get current AP BG list from memory ─────────────────────────────────
    from main import _ap_memory
    ap_dict = _ap_memory.get("ap_dict") or {}

    if not ap_dict:
        yield event("No AP in memory — fetching from Intranet...")
        from modules.intranet import fetch_auftragsplan, parse_auftragsplan
        html    = fetch_auftragsplan()
        ap_dict = parse_auftragsplan(html)

    if not ap_dict:
        yield event("ERROR: AP is empty")
        yield event("__DONE__")
        return

    # ── 2. Collect all PP for BGs in AP ───────────────────────────────────────
    bg_names = list(dict.fromkeys(
        entry["bg_name"] for entry in ap_dict.values()
    ))

    # Get pp_list per BG from DB
    ap_pp_names: list[str] = []
    for bg_name in bg_names:
        row = conn.execute(
            "SELECT pp_list FROM bg WHERE bg_name = ?", (bg_name,)
        ).fetchone()
        if row and row["pp_list"]:
            ap_pp_names.extend(
                p.strip() for p in row["pp_list"].split(",") if p.strip()
            )

    total = len(ap_pp_names)
    if total == 0:
        yield event("No PP found for current AP BGs")
        yield event("__DONE__")
        return

    yield event(f"Checking {total} PP for {len(bg_names)} BG...")

    # ── 3. Load DB mtime state for these PP ───────────────────────────────────
    placeholders = ",".join("?" * len(ap_pp_names))
    db_pp: dict[str, dict] = {
        row["pp_name"]: dict(row)
        for row in conn.execute(
            f"SELECT pp_name, mtime_bbs, mtime_cad, mtime_def, mtime_desc, "
            f"mtime_mod, mtime_par, mtime_pre, mtime_ref, mtime_size, mtime_hinweis "
            f"FROM pp WHERE pp_name IN ({placeholders})",
            ap_pp_names,
        ).fetchall()
    }

    # ── 4. Build folder map (pp_name → folder) ────────────────────────────────
    all_folders = get_pp_list()
    folder_map: dict[str, str] = {}
    for folder in all_folders:
        pp_name = _resolve_locked_name(folder) if "__" in folder else folder
        folder_map[pp_name] = folder

    # ── 5. Check + update each PP ─────────────────────────────────────────────
    updated_count = 0

    for idx, pp_name in enumerate(ap_pp_names, 1):
        folder  = folder_map.get(pp_name, pp_name)
        pp_path = os.path.join(cad_root, folder)

        if not os.path.isdir(pp_path):
            logger.warning(f"[refresh_ap] folder not found: {pp_path}")
            continue

        yield event(f"Checking {pp_name}... ({idx}/{total})")

        current_mtimes = _collect_mtimes(pp_path, pp_name)
        db_row         = db_pp.get(pp_name, {})
        is_new         = pp_name not in db_pp

        if not is_new and not _any_mtime_changed(current_mtimes, db_row):
            continue   # nothing changed

        yield event(f"Updating {pp_name}... ({idx}/{total})")

        # Re-parse all files
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
        comp       = _build_comp_str(pm_dict)
        locked     = "__" in folder

        with conn:
            conn.execute(
                """
                INSERT INTO pp (
                    pp_name, locked, cli, nutzen_in_lp, hinweis,
                    oldest_mod, comp,
                    mtime_bbs, mtime_cad, mtime_def, mtime_desc,
                    mtime_mod, mtime_par, mtime_pre, mtime_ref,
                    mtime_size, mtime_hinweis, synced_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(pp_name) DO UPDATE SET
                    locked        = excluded.locked,
                    cli           = excluded.cli,
                    nutzen_in_lp  = excluded.nutzen_in_lp,
                    hinweis       = excluded.hinweis,
                    oldest_mod    = excluded.oldest_mod,
                    comp          = excluded.comp,
                    mtime_bbs     = excluded.mtime_bbs,
                    mtime_cad     = excluded.mtime_cad,
                    mtime_def     = excluded.mtime_def,
                    mtime_desc    = excluded.mtime_desc,
                    mtime_mod     = excluded.mtime_mod,
                    mtime_par     = excluded.mtime_par,
                    mtime_pre     = excluded.mtime_pre,
                    mtime_ref     = excluded.mtime_ref,
                    mtime_size    = excluded.mtime_size,
                    mtime_hinweis = excluded.mtime_hinweis,
                    synced_at     = excluded.synced_at
                """,
                (
                    pp_name, int(locked), cli, nutzen, hinweis,
                    oldest_mod, comp,
                    current_mtimes.get("bbs"), current_mtimes.get("cad"),
                    current_mtimes.get("def"), current_mtimes.get("desc"),
                    current_mtimes.get("mod"), current_mtimes.get("par"),
                    current_mtimes.get("pre"), current_mtimes.get("ref"),
                    current_mtimes.get("size"), current_mtimes.get("hinweis"),
                    synced_at,
                ),
            )

            # Update pp_pm if .cad changed
            cad_changed = (
                is_new or
                abs(
                    (current_mtimes.get("cad") or 0) -
                    (db_row.get("mtime_cad") or 0)
                ) > 1.0
            )
            if cad_changed and pm_dict:
                conn.execute("DELETE FROM pp_pm WHERE pp_name = ?", (pp_name,))
                conn.executemany(
                    "INSERT OR REPLACE INTO pp_pm (pp_name, pm_name, ihl_nr, pm_type, refs_count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    _flatten_pm_dict(pp_name, pm_dict),
                )

        updated_count += 1
        logger.info(f"[refresh_ap] updated PP: {pp_name}")

    if updated_count > 0:
        # Re-run pm_type pass for updated PP only
        yield event(f"Updated {updated_count} PP — recalculating PM types...")
        _update_pm_type_for(conn, ap_pp_names)

    # ── 6. Re-run error generation ────────────────────────────────────────────
    yield event("Generating inspection results...")
    from db.sync_errors import sync_errors
    sync_errors()

    yield event(f"__DONE__")


def _update_pm_type_for(conn, pp_names: list[str]) -> None:
    """Re-run pm_type evaluation only for the given PP names."""
    placeholders = ",".join("?" * len(pp_names))

    with conn:
        # Reset pm_type for these PP
        conn.execute(
            f"UPDATE pp_pm SET pm_type = NULL WHERE pp_name IN ({placeholders})",
            pp_names,
        )
        # Mark local
        conn.execute(
            f"""
            UPDATE pp_pm SET pm_type = 'local'
            WHERE pp_name IN ({placeholders})
              AND EXISTS (
                SELECT 1 FROM cli_local cl
                WHERE cl.pm_name = pp_pm.pm_name
                  AND cl.pp_name = pp_pm.pp_name
              )
            """,
            pp_names,
        )
        # Mark global
        conn.execute(
            f"""
            UPDATE pp_pm SET pm_type = 'global'
            WHERE pm_type IS NULL
              AND pp_name IN ({placeholders})
              AND EXISTS (
                SELECT 1 FROM cli_global cg
                JOIN pp ON pp.pp_name = pp_pm.pp_name
                WHERE cg.pm_name = pp_pm.pm_name
                  AND cg.cli     = pp.cli
              )
            """,
            pp_names,
        )
