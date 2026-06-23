"""
AOI Tool - Inspection pipeline

Orchestrates all steps and builds the API response.

Internal data flow:
    ap_dict   { fbs: { bg_name, aoi_color, smd_line, auftragsmenge } }
    bg_dict   { bg_name: { active, kunde, dmc, ... intranet_bot/top } }
    pp_dict   { pp_name: { bg_name, cad_bot/top, cli, pm_dict, ... } }

All three are plain dicts — no Pydantic until the final build_response() call.
"""

import logging
import re
import time

from models import BaugrupeSummary, PpSummary, InspectionError

from modules.intranet import (
    fetch_auftragsplan, parse_auftragsplan, build_bg_dict
)
from modules.pp_inspect import (
    build_pp_dict_ap, build_pp_dict_vb, build_pp_dict_single
)
from modules.errors import bg_row_color, row_color_from_errors
from modules.app_context import get_ctx

logger = logging.getLogger(__name__)


# ─── Public pipeline runners ──────────────────────────────────────────────────

def run_inspection_ap() -> tuple[list[BaugrupeSummary], dict, dict, dict]:
    """
    Full AP inspection pipeline.
    Returns (results, bg_dict, pp_dict, ap_dict) for caching.
    """
    logger.info("Starting AP inspection...")
    t0 = time.time()

    html     = fetch_auftragsplan()
    ap_dict  = parse_auftragsplan(html)
    bg_names = [ap_dict[fbs]["bg_name"] for fbs in ap_dict.keys()]
    bg_dict  = build_bg_dict(bg_names)
    pp_dict  = build_pp_dict_ap(bg_dict)

    results = build_response(bg_names, bg_dict, pp_dict, ap_dict)
    logger.info(f"AP inspection done: {len(results)} BG in {time.time()-t0:.1f}s")
    return results, bg_dict, pp_dict, ap_dict


def run_inspection_vb() -> tuple[list[BaugrupeSummary], dict, dict]:
    """
    Full VB inspection pipeline.
    Returns (results, bg_dict, pp_dict).
    """
    logger.info("Starting VB inspection...")
    t0 = time.time()

    ctx      = get_ctx()
    bg_names = _list_vb_bg_names(ctx)
    bg_dict  = build_bg_dict(bg_names)
    pp_dict  = build_pp_dict_vb(bg_names, bg_dict)

    results = build_response(bg_names, bg_dict, pp_dict, ap_dict={})
    logger.info(f"VB inspection done: {len(results)} BG in {time.time()-t0:.1f}s")
    return results, bg_dict, pp_dict


def run_inspection_text(text: str) -> list[BaugrupeSummary]:
    """
    Inspection for manually entered BG / PP names.
    """
    logger.info("Starting text inspection...")
    t0 = time.time()

    bg_names, standalone_pp = _parse_text_input(text)
    bg_dict = build_bg_dict(bg_names) if bg_names else {}

    # BG-based PP detection + inspection
    pp_dict = build_pp_dict_ap(bg_dict) if bg_dict else {}

    # Standalone PP entered directly
    for pp_name in standalone_pp:
        if pp_name not in pp_dict:
            pp_dict.update(build_pp_dict_single(pp_name))

    # Merge bg_names with any BG inferred from standalone PP
    all_bg = list(bg_names)
    for pp in pp_dict.values():
        if pp["bg_name"] not in all_bg:
            all_bg.append(pp["bg_name"])
            if pp["bg_name"] not in bg_dict:
                bg_dict[pp["bg_name"]] = _empty_bg()

    results = build_response(all_bg, bg_dict, pp_dict, ap_dict={})
    logger.info(f"Text inspection done: {len(results)} BG in {time.time()-t0:.1f}s")
    return results


# ─── Response builder ─────────────────────────────────────────────────────────

def build_response(
    bg_names: list[str],
    bg_dict:  dict,
    pp_dict:  dict,
    ap_dict:  dict,
) -> list[BaugrupeSummary]:
    """
    Convert internal dicts to API response models (Pydantic).
    Preserves the order of bg_names.
    """
    results = []
    nr=0
    for bg_name in bg_names:
        nr+=1
        #print(nr, "bg_name:", bg_name)

        bg  = bg_dict.get(bg_name, _empty_bg())
        ap = next(
        (ap for ap in ap_dict.values() if ap.get("bg_name") == bg_name), {})

        #print("bg:", bg)
        #print("ap:", ap)

        # Collect PP summaries for this BG (sorted BOT before TOP)
        bg_pp = {
            pp_name: pp
            for pp_name, pp in pp_dict.items()
            if pp["bg_name"] == bg_name
        }
        pp_list = _build_pp_summaries(bg_pp, bg_name)

        # BG-level errors → InspectionError models
        bg_errors = [_to_error_model(e) for e in bg.get("bg_errors", [])]

        # Overall row color
        color = bg_row_color(bg_dict, bg_name, pp_dict) if bg_name in bg_dict else "green"

        results.append(BaugrupeSummary(
            name               = bg_name,
            active             = bg.get("active", False),
            kunde              = bg.get("kunde") or None,
            project_name       = bg.get("project_name"),
            dmc                = bg.get("dmc", False),
            medi               = bg.get("medi", False),
            lp_nr              = bg.get("lp_nr"),
            lp_image_bot       = bg.get("lp_image_bot"),
            lp_image_top       = bg.get("lp_image_top"),
            intranet_bot_count = sum(len(v) for v in bg.get("intranet_bot", {}).values()),
            intranet_top_count = sum(len(v) for v in bg.get("intranet_top", {}).values()),
            cad_bot_count      = sum(
                sum(len(v) for v in pp.get("cad_bot", {}).values())
                for pp in bg_pp.values()
            ),
            cad_top_count      = sum(
                sum(len(v) for v in pp.get("cad_top", {}).values())
                for pp in bg_pp.values()
            ),									 
            pp_list            = bg.get("pp_list", []),
            aoi_color          = ap.get("aoi_color"),
            bg_color           = ap.get("bg_color"),
            smd_line           = ap.get("smd_line"),
            auftragsmenge      = ap.get("auftragsmenge"),
            bg_errors          = bg_errors,
            pp_list_detail     = pp_list,
            row_color          = color,
        ))

    return results


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_pp_summaries(bg_pp: dict, bg_name: str) -> list[PpSummary]:
    """Build PpSummary list, BOT before TOP."""
    def sort_key(item):
        pp_name = item[0]
        return (0 if "bot" in pp_name.lower() else 1, pp_name)

    summaries = []
    for pp_name, pp in sorted(bg_pp.items(), key=sort_key):
        side   = "BOT" if "bot" in pp_name.lower() else "TOP"
        errors = [_to_error_model(e) for e in pp.get("pp_errors", [])]
        color  = row_color_from_errors(pp.get("pp_errors", []))

        summaries.append(PpSummary(
            name          = pp_name,
            side          = side,
            bg_name       = bg_name,
            locked        = pp.get("locked", False),
            cli           = pp.get("cli"),
            nutzen_in_lp  = pp.get("nutzen_in_lp"),
            cad_bot_count = sum(len(v) for v in pp.get("cad_bot", {}).values()),
            cad_top_count = sum(len(v) for v in pp.get("cad_top", {}).values()),
            pm_count      = len(pp.get("pm_dict", {})),
            pm_dict       = pp.get("pm_dict", {}),
            hinweis       = pp.get("hinweis"),
            errors        = errors,
            row_color     = color,
        ))

    return summaries


def _to_error_model(e: dict) -> InspectionError:
    return InspectionError(
        timestamp     = e.get("timestamp", ""),
        bg_name       = e.get("bg_name", ""),
        pp_name       = e.get("pp_name"),
        error_code    = e.get("error_code", ""),
        error_type    = e.get("error_type", "Info"),
        short_desc    = e.get("short_desc", ""),
        long_desc     = e.get("long_desc", ""),
        open_file     = e.get("open_file"),
        affected_rows = e.get("affected_rows"),
    )


def _list_vb_bg_names(ctx) -> list[str]:
    """List BG folders in Vorbereitung."""
    import os
    result = []
    try:
        for name in sorted(os.listdir(ctx.vorbereitung_path)):
            path = os.path.join(ctx.vorbereitung_path, name)
            if os.path.isdir(path) and len(name) == 10 and name[7] == ".":
                result.append(name)
    except Exception as e:
        logger.error(f"Error listing Vorbereitung: {e}")
    return result


def _parse_text_input(text: str) -> tuple[list[str], list[str]]:
    """
    Parse manually entered text into (bg_names, standalone_pp_names).
    BG format:  8009917.04
    PP format:  8009917_04BOT_ROT
    """
    bg_pat = re.compile(r'^\d{7}\.\d{2}$')
    pp_pat = re.compile(r'^\d{7}_\d{2}')
    bg_names = []
    pp_names = []
    seen_bg  = set()

    for line in text.splitlines():
        elem = line.strip()
        if not elem or not elem.startswith("80"):
            continue

        if bg_pat.match(elem):
            if elem not in seen_bg:
                seen_bg.add(elem)
                bg_names.append(elem)

        elif pp_pat.match(elem):
            # Also register inferred BG
            parts   = elem.split("_")
            bg_name = f"{parts[0]}.{parts[1][:2]}"
            if bg_name not in seen_bg:
                seen_bg.add(bg_name)
                bg_names.append(bg_name)
            pp_names.append(elem)

    return bg_names, pp_names


def _empty_bg() -> dict:
    return {
        "active": False, "kunde": "", "dmc": False,
        "medi": False, "lp_nr": None,
        "intranet_bot": {}, "intranet_top": {},
        "bg_errors": [],
    }
