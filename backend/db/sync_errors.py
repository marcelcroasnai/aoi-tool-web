"""
AOI Tool - sync_errors
Step 6: AP refresh from Intranet + error generation + build response from DB.

Triggered manually (AP refresh button) — never auto-scheduled.

Flow:
    1. Fetch AP from Intranet
    2. Truncate error table
    3. For each BG in AP: run all checks, collect errors
    4. Write errors to DB in one transaction
    5. Build BaugrupeSummary list from DB data
    6. Store result in main._ap_memory via set_ap_memory()
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from modules.app_context import get_ctx

from modules.intranet import fetch_auftragsplan, parse_auftragsplan
from db.schema        import get_conn
from db.sync_log      import start_sync, finish_sync, fail_sync

logger = logging.getLogger(__name__)


# ─── Public entry point ───────────────────────────────────────────────────────

def sync_errors() -> dict:
    """
    Fetch AP + generate errors + build response from DB.
    Stores result in main._ap_memory.
    Returns the ap_dict for logging.
    """
    t_start = time.time()
    log_id  = start_sync("ap")

    try:
        ap_dict, results, error_count = _run()
        duration = time.time() - t_start

        # Store in main memory for /api/ap endpoint
        from main import set_ap_memory
        set_ap_memory(ap_dict, results, duration)

        finish_sync(
            log_id, "ap",
            total      = len(ap_dict),
            changed    = error_count,
            duration_s = duration,
        )
        logger.info(
            f"[sync_errors] done — "
            f"{len(ap_dict)} BG, {error_count} errors, "
            f"{len(results)} BaugrupeSummary built, "
            f"duration={duration:.1f}s"
        )
        return ap_dict

    except Exception as e:
        fail_sync(log_id, "ap", str(e), time.time() - t_start)
        raise


# ─── Core logic ───────────────────────────────────────────────────────────────

def _run() -> tuple[dict, list, int]:
    conn = get_conn()

    # ── 1. Fetch AP ───────────────────────────────────────────────────────────
    logger.info("[sync_errors] fetching AP from Intranet …")
    try:
        html    = fetch_auftragsplan()
        ap_dict = parse_auftragsplan(html)
    except Exception as e:
        logger.error(f"[sync_errors] AP fetch failed: {e}")
        # Write a single global Error_18 so it's visible in the UI
        conn = get_conn()
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute("DELETE FROM error")
            conn.execute(
                "INSERT INTO error (bg_name, pp_name, error_code, error_type, error_text, created_at) "
                "VALUES (?, ?, 'Error_18', 'Suggestion', ?, ?)",
                ("—", None, f"AP URL request failed: {e}", created_at),
            )
        raise

    if not ap_dict:
        logger.warning("[sync_errors] AP is empty")
        return ap_dict, [], 0

    # ── 2. Truncate error table ───────────────────────────────────────────────
    with conn:
        conn.execute("DELETE FROM error")

    # ── 2b. Refresh pm_type so Error_16 reflects current cli_global/cli_local ──
    # pp_pm.pm_type is written NULL whenever pp_pm is rebuilt and is only
    # recomputed by the pm_type pass. A CLI-only change (e.g. a newly added
    # .cle) does not touch any PP, so neither run_sync("cli") nor the
    # refresh_ap scoped recalc (which only runs when a PP changed) updates it —
    # the stored pm_type stays a stale NULL and produces false
    # "PM not found in CLI" (Error_16) reports. Running the full pass here keeps
    # error generation consistent with the current CLI tables regardless of
    # which caller (manager "ap" / refresh_ap SSE) invoked sync_errors.
    from db.sync_pm_type import sync_pm_type
    sync_pm_type()

    # ── 3. Load DB data ───────────────────────────────────────────────────────
    bg_rows: dict[str, dict] = {
        row["bg_name"]: dict(row)
        for row in conn.execute("SELECT * FROM bg").fetchall()
    }
    pp_rows: dict[str, dict] = {
        row["pp_name"]: dict(row)
        for row in conn.execute("SELECT * FROM pp").fetchall()
    }
    pp_pm_rows: dict[str, list[dict]] = {}
    for row in conn.execute("SELECT * FROM pp_pm").fetchall():
        pp_pm_rows.setdefault(row["pp_name"], []).append(dict(row))

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    errors: list[tuple] = []

    ctx = get_ctx()

    # ── 4. Check each BG ──────────────────────────────────────────────────────
    for fbs, ap_entry in ap_dict.items():
        bg_name = ap_entry["bg_name"]
        bg      = bg_rows.get(bg_name)

        if bg is None:
            # BG not in DB — bginfo not synced or genuinely missing
            errors.append(_make_error_row(bg_name, None, "Error_9",
                f"BG {bg_name} not found in DB — bginfo sync may be needed.", created_at))
            continue

        # Error_9: BG inactive (Z_ marker in pl.txt)
        if not bg.get("active", True):
            errors.append(_make_error_row(bg_name, None, "Error_9",
                f"BG {bg_name} is inactive (Z_ marker in pl.txt).", created_at))

        pp_list_str = bg.get("pp_list") or ""
        pp_names    = [p.strip() for p in pp_list_str.split(",") if p.strip()]

        # Error_14: No test plan found
        if not pp_names:
            errors.append(_make_error_row(bg_name, None, "Error_14",
                f"No test plans found for {bg_name}.", created_at))
            # Create placeholder PP rows based on BG comp sides
            expected_sides = []
            if bg.get("comp_bot"): expected_sides.append("BOT")
            if bg.get("comp_top"): expected_sides.append("TOP")
            if not expected_sides: expected_sides = ["BOT", "TOP"]
            bg_nr, bg_idx = (bg_name.split(".") + ["00"])[:2]
            for side in expected_sides:
                placeholder_name = f"{bg_nr}_{bg_idx}{side}"
                pp_names.append(placeholder_name)
                pp_rows[placeholder_name] = {"_placeholder": True, "locked": False,
                                              "cli": None, "nutzen_in_lp": None,
                                              "comp": None, "hinweis": None}

        # Error_11: No BOT or TOP in PP names (check per PP)
        for pp_name in pp_names:
            if "bot" not in pp_name.lower() and "top" not in pp_name.lower():
                errors.append(_make_error_row(bg_name, pp_name, "Error_11",
                    f"PP {pp_name} has no BOT or TOP in name.", created_at))

        # Error_42: Different CLI on BOT vs TOP
        cli_by_side: dict[str, str] = {}
        for pp_name in pp_names:
            pp = pp_rows.get(pp_name)
            if pp and pp.get("cli"):
                side = "BOT" if "bot" in pp_name.lower() else "TOP"
                cli_by_side[side] = pp["cli"]
        if len(cli_by_side) == 2 and cli_by_side.get("BOT") != cli_by_side.get("TOP"):
            for pp_name in pp_names:
                errors.append(_make_error_row(bg_name, pp_name, "Error_42",
                    f"BOT CLI={cli_by_side.get('BOT')} ≠ TOP CLI={cli_by_side.get('TOP')}.",
                    created_at))

        # PP-level checks
        for pp_name in pp_names:
            pp = pp_rows.get(pp_name)
            if pp is None:
                errors.append(_make_error_row(bg_name, pp_name, "Error_14",
                    f"PP {pp_name} missing from pp table.", created_at))
                continue

            if pp.get("_placeholder"):
                continue

            # Error_17: PP locked
            if pp.get("locked"):
                errors.append(_make_error_row(bg_name, pp_name, "Error_17",
                    f"PP {pp_name} is locked.", created_at))

            # Errors 1–5: always-required files
            for ext, code in [
                ("cad",  "Error_1"),
                ("def",  "Error_2"),
                ("desc", "Error_3"),
                ("ref",  "Error_4"),
                ("size", "Error_5"),
            ]:
                if pp.get(f"mtime_{ext}") is None:
                    errors.append(_make_error_row(bg_name, pp_name, code,
                        f"{pp_name}.{ext} missing.", created_at))

            # Errors 6–7: .par / .pre are DMC-only artifacts. Check their
            # presence only when this PP is DMC-relevant, i.e. the PP name
            # carries the "_DMC" marker, or the dmc flag is set on the pp row
            # or on the parent bg row. Otherwise a non-DMC plan would always
            # trip Error_6/_7 for files it is not expected to have.
            dmc_relevant = (
                "_DMC" in pp_name.upper()
                or bool(pp.get("dmc"))
                or bool(bg.get("dmc"))
            )
            if dmc_relevant:
                for ext, code in [
                    ("par", "Error_6"),
                    ("pre", "Error_7"),
                ]:
                    if pp.get(f"mtime_{ext}") is None:
                        errors.append(_make_error_row(bg_name, pp_name, code,
                            f"{pp_name}.{ext} missing.", created_at))

            # Error_8: Haran files missing (.uscal, .us.bmp, .hr.bmp)
            pic_path = ctx.picture_path
            for suffix in [".uscal", ".us.bmp", ".hr.bmp"]:
                haran_file = os.path.join(pic_path, pp_name + suffix)
                if not os.path.isfile(haran_file):
                    errors.append(_make_error_row(bg_name, pp_name, "Error_8",
                        f"Haran file missing: {pp_name}{suffix}", created_at))
                    break  # one error per PP is enough

            # Error_10: PP already in VB folder
            bg_nr_part = bg_name.split(".")[0]
            vb_pp_path = os.path.join(ctx.vorbereitung_path, bg_name, pp_name)
            if os.path.isdir(vb_pp_path):
                errors.append(_make_error_row(bg_name, pp_name, "Error_10",
                    f"PP {pp_name} already prepared in VB folder.", created_at))

            # Error_12 / Error_13: DMC mismatch
            bg_dmc  = bool(bg.get("dmc"))
            pp_has_dmc = (
                "_DMC" in pp_name.upper()
                and pp.get("mtime_pre") is not None
                and pp.get("mtime_par") is not None
            )
            if bg_dmc and not pp_has_dmc:
                errors.append(_make_error_row(bg_name, pp_name, "Error_12",
                    f"DMC required by BG but not present in PP {pp_name} "
                    f"(missing _DMC in name or .pre/.par files).", created_at))
            elif not bg_dmc and pp_has_dmc:
                errors.append(_make_error_row(bg_name, pp_name, "Error_13",
                    f"PP {pp_name} has DMC (_DMC in name + .pre/.par) "
                    f"but BG does not require DMC.", created_at))

            # Error_16: PM not in assigned CLI
            for pm in pp_pm_rows.get(pp_name, []):
                if pm.get("pm_type") is None:
                    errors.append(_make_error_row(bg_name, pp_name, "Error_16",
                        f"PM '{pm['pm_name']}' not found in CLI '{pp.get('cli')}'.",
                        created_at))

    # ── 5. Write errors ───────────────────────────────────────────────────────
    if errors:
        with conn:
            conn.executemany(
                """INSERT INTO error
                   (bg_name, pp_name, error_code, error_type,
                    error_text, open_file, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                errors,
            )

    # ── 6. Build error lookup ─────────────────────────────────────────────────
    # { bg_name: [error_dicts] }, { pp_name: [error_dicts] }
    bg_errors_map: dict[str, list] = {}
    pp_errors_map: dict[str, list] = {}
    for row in conn.execute("SELECT * FROM error").fetchall():
        e = _db_error_to_dict(dict(row))
        if row["pp_name"] is None:
            bg_errors_map.setdefault(row["bg_name"], []).append(e)
        else:
            pp_errors_map.setdefault(row["pp_name"], []).append(e)

    # ── 7. Build BaugrupeSummary list ─────────────────────────────────────────
    from models import BaugrupeSummary, PpSummary, InspectionError
    from modules.errors import get_error_color, row_color_from_errors
    from modules.intranet import _resolve_lp_images

    results = []
    for fbs, ap_entry in ap_dict.items():
        bg_name = ap_entry["bg_name"]
        bg      = bg_rows.get(bg_name)

        pp_names    = []
        pp_details  = []
        bg_err_list = bg_errors_map.get(bg_name, [])

        if bg:
            pp_list_str = bg.get("pp_list") or ""
            pp_names    = [p.strip() for p in pp_list_str.split(",") if p.strip()]

            # If no PP in DB, create placeholders based on BG comp sides
            if not pp_names:
                expected_sides = []
                if bg.get("comp_bot"): expected_sides.append("BOT")
                if bg.get("comp_top"): expected_sides.append("TOP")
                if not expected_sides: expected_sides = ["BOT", "TOP"]
                bg_nr, bg_idx = (bg_name.split(".") + ["00"])[:2]
                for side in expected_sides:
                    placeholder_name = f"{bg_nr}_{bg_idx}{side}"
                    pp_names.append(placeholder_name)
                    if placeholder_name not in pp_rows:
                        pp_rows[placeholder_name] = {
                            "_placeholder": True, "locked": False,
                            "cli": None, "nutzen_in_lp": None,
                            "comp": None, "hinweis": None,
                        }

            for pp_name in pp_names:
                pp = pp_rows.get(pp_name)
                if pp is None:
                    continue

                is_placeholder = bool(pp.get("_placeholder"))
                pp_err_list  = pp_errors_map.get(pp_name, [])
                pp_err_objs  = [InspectionError(**e) for e in pp_err_list]
                side         = "BOT" if "bot" in pp_name.lower() else "TOP"
                pm_entries   = [] if is_placeholder else pp_pm_rows.get(pp_name, [])
                pm_dict      = _build_pm_dict(pm_entries)
                pm_count     = len(pm_dict)

                pp_details.append(PpSummary(
                    name          = pp_name,
                    display_name  = None if is_placeholder else (pp.get("folder") or pp_name),
                    placeholder   = is_placeholder,
                    side          = side,
                    bg_name       = bg_name,
                    locked        = bool(pp.get("locked")),
                    cli           = pp.get("cli"),
                    nutzen_in_lp  = pp.get("nutzen_in_lp"),
                    cad_bot_count = _comp_count(pp.get("comp")) if side == "BOT" else 0,
                    cad_top_count = _comp_count(pp.get("comp")) if side == "TOP" else 0,
                    pm_count      = pm_count,
                    pm_dict       = pm_dict,
                    hinweis       = pp.get("hinweis"),
                    errors        = pp_err_objs,
                    row_color     = row_color_from_errors(pp_err_list),
                ))

        bg_err_objs = [InspectionError(**e) for e in bg_err_list]

        lp_nr = bg.get("lp_nr") if bg else None
        lp_image_bot, lp_image_top = _resolve_lp_images(lp_nr, ctx)

        intranet_bot_count = _comp_count(bg.get("comp_bot")) if bg else 0
        intranet_top_count = _comp_count(bg.get("comp_top")) if bg else 0
        cad_bot_count = sum(pp.cad_bot_count for pp in pp_details)
        cad_top_count = sum(pp.cad_top_count for pp in pp_details)

        results.append(BaugrupeSummary(
            name               = bg_name,
            active             = True,
            kunde              = bg.get("kunde") if bg else None,
            project_name       = bg.get("project_name") if bg else None,
            dmc                = bool(bg.get("dmc")) if bg else False,
            medi               = bool(bg.get("medi")) if bg else False,
            lp_nr              = lp_nr,
            lp_image_bot       = lp_image_bot,
            lp_image_top       = lp_image_top,
            intranet_bot_count = intranet_bot_count,
            intranet_top_count = intranet_top_count,
            cad_bot_count      = cad_bot_count,
            cad_top_count      = cad_top_count,
            pp_list       = pp_names,
            aoi_color     = ap_entry.get("aoi_color"),
            bg_color      = ap_entry.get("bg_color"),
            smd_line      = ap_entry.get("smd_line"),
            auftragsmenge = ap_entry.get("auftragsmenge"),
            bg_errors     = bg_err_objs,
            pp_list_detail= pp_details,
            row_color     = row_color_from_errors(bg_err_list) if bg_err_list else
                            (max((p.row_color for p in pp_details),
                                 key=lambda c: ["green","yellow","orange","red"].index(c),
                                 default="green") if pp_details else "green"),
        ))

    logger.info(f"[sync_errors] {len(errors)} errors written to DB")
    return ap_dict, results, len(errors)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_error_row(
    bg_name: str, pp_name: Optional[str],
    error_code: str, error_text: str,
    created_at: str, open_file: Optional[str] = None,
) -> tuple:
    from modules.errors import _ERROR_REGISTRY
    entry      = _ERROR_REGISTRY.get(error_code, {})
    error_type = entry.get("error_type", "Info")
    return (bg_name, pp_name, error_code, error_type, error_text, open_file, created_at)


def _build_pm_dict(pm_entries: list[dict]) -> dict:
    """
    Build pm_dict from pp_pm DB rows for frontend display.
    Structure: { pm_name: { ihl_nr: "(N refs)" } }
    Multiple ihl_nr rows per pm_name are all included.
    """
    result: dict[str, dict] = {}
    for pm in pm_entries:
        pm_name    = pm.get("pm_name", "")
        ihl_nr     = pm.get("ihl_nr") or "—"
        refs_count = pm.get("refs_count") or 0
        result.setdefault(pm_name, {})[ihl_nr] = f"({refs_count} refs)"
    return result


def _comp_count(comp_str: Optional[str]) -> int:
    """Count components from a comma-separated string stored in DB."""
    if not comp_str:
        return 0
    return len([c for c in comp_str.split(",") if c.strip()])


def _db_error_to_dict(row: dict) -> dict:
    """Convert a DB error row to the dict shape expected by InspectionError."""
    from modules.errors import _ERROR_REGISTRY
    entry = _ERROR_REGISTRY.get(row["error_code"], {})
    return {
        "timestamp":     row["created_at"],
        "bg_name":       row["bg_name"],
        "pp_name":       row["pp_name"],
        "error_code":    row["error_code"],
        "error_type":    row["error_type"],
        "short_desc":    entry.get("short_desc", row["error_code"]),
        "long_desc":     row["error_text"],
        "open_file":     row["open_file"],
        "affected_rows": None,
    }
