"""
AOI Tool - Intranet module

Responsibilities:
  1. fetch_auftragsplan()    → raw HTML string
  2. parse_auftragsplan()    → ap_dict  { bg_name: { bg_name, aoi_color, smd_line, auftragsmenge, bg_color } }
  3. build_bg_dict()         → bg_dict  (reads pl.txt per BG, resolves lp images, pp_list)

All file reads go directly to disk.
Cache stores only parsed results, keyed by real file path.
"""

import os
import re
import logging
import requests
from typing import Optional
from bs4 import BeautifulSoup

from config import AP_URL
from modules.app_context import get_ctx
from modules.file_cache import get, put
from modules.errors import make_error

logger = logging.getLogger(__name__)

_BL_COMP = {
    '', 'leerplatine', 'pcb', 'lp', '__', '_', '-',
    'pb24', 'label', 'led-label', 'led-aufkleber', 'pcb1', 'ref.'
}


# ─── 1. Auftragsplan ──────────────────────────────────────────────────────────

def fetch_auftragsplan() -> str:
    ctx = get_ctx()
    if ctx.mode == "test":
        try:
            with open(ctx.ap_html_file, "r", encoding="cp1252", errors="replace") as f:
                html = f.read()
            logger.info(f"TEST MODE: Auftragsplan read from {ctx.ap_html_file}")
            return html
        except Exception as e:
            logger.error(f"TEST MODE: Error reading HTML: {e}")
            return ""
    else:
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(AP_URL)
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching Auftragsplan: {e}")
            return ""


def parse_auftragsplan(html: str) -> dict:
    """
    Parse Auftragsplan HTML.

    Returns:
        ap_dict  { fbs: { bg_name, aoi_color, smd_line, auftragsmenge, bg_color } }

    Order of insertion reflects production plan order.
    Use ap_dict.keys() to get the ordered BG list.
    """
    ap_dict: dict = {}

    if not html:
        return ap_dict

    soup     = BeautifulSoup(html, "html.parser")
    href_pat = re.compile(r"javascript:quickmail\('(\d+)', '(\d+\.\d+)', '(\d+)'\)")
    bg_pat   = re.compile(r'\d{7}\.\d{2}')

    c=0
    for tr in soup.find_all("tr"):
        c+=1
        
        bg_color_dict = {}
        tds      = tr.find_all("td")
        td_texts = [td.text for td in tds]

        if not (5 < len(td_texts) < 20):
            continue

        bg_name = smd_line = aoi_color = auftragsmenge = ""
        nr = 0
        for td in tds:
            nr+=1

            bg_color = td.get("bgcolor")
            if bg_color not in bg_color_dict:
                bg_color_dict[bg_color] = 1
            else:
                bg_color_dict[bg_color] += 1

            a = td.find("a")
            if a:
                m = href_pat.match(str(a.get("href", "")))
                if m:
                    smd_line  = m.group(1)
                    bg_name   = m.group(2)
                    fbs       = m.group(3)
                    aoi_color = td.get("bgcolor", "")

                    sorted_bg_color_dict = sorted(bg_color_dict.items(), key=lambda item: item[1], reverse=True)
                    bg_color = list(sorted_bg_color_dict)[0][0]

                    break

        if not bg_name:
            continue

        for i, txt in enumerate(td_texts):
            if re.match(bg_pat, txt) and txt.strip() == bg_name:
                if i + 3 < len(td_texts):
                    auftragsmenge = td_texts[i + 3]
                break
            
        if fbs not in ap_dict:
            ap_dict[fbs] = {
                "bg_name":       bg_name,
                "aoi_color":     aoi_color,
                "smd_line":      smd_line,
                "auftragsmenge": auftragsmenge,
                "bg_color":      bg_color,
            }

    logger.info(f"parse_auftragsplan: {len(ap_dict)} BG found")
    
    #print("ap_dict BEFORE return:", ap_dict)
    return ap_dict


# ─── 2. bg_dict builder ───────────────────────────────────────────────────────

def build_bg_dict(bg_names: list[str]) -> dict:
    """
    Read pl.txt for each BG and build bg_dict.

    bg_dict structure:
    {
      "8009917.04": {
        "active":        bool,
        "kunde":         str,
        "project_name":  str | None,
        "dmc":           bool,
        "medi":          bool,
        "lp_nr":         str | None,
        "lp_image_bot":  str | None,   # absolute path
        "lp_image_top":  str | None,   # absolute path
        "intranet_bot":  list[str],
        "intranet_top":  list[str],
        "pp_list":       list[str],    # filled later by pp_inspect
        "bg_errors":     list[dict],
      }
    }
    """
    ctx       = get_ctx()
    kunde_map = _load_kunde_map(ctx)
    bg_dict   = {}

    for bg_name in bg_names:
        bg_nr, bg_idx = bg_name.split(".")
        pl_file = os.path.join(ctx.bg_info_path, bg_nr, bg_idx, "pl.txt")

        active, kunde, project_name, dmc, medi, lp_nr, bot, top, errors = \
            _parse_pl_file(bg_name, pl_file, kunde_map)

        lp_image_bot, lp_image_top = _resolve_lp_images(lp_nr, ctx)

        bg_dict[bg_name] = {
            "active":        active,
            "kunde":         kunde,
            "project_name":  project_name,
            "dmc":           dmc,
            "medi":          medi,
            "lp_nr":         lp_nr,
            "lp_image_bot":  lp_image_bot,
            "lp_image_top":  lp_image_top,
            "intranet_bot":  bot,
            "intranet_top":  top,
            "pp_list":       [],
            "bg_errors":     errors,
        }

        logger.debug(
            f"bg_dict: {bg_name} active={active} "
            f"bot={len(bot)} top={len(top)} lp_nr={lp_nr}"
        )

    active_count = sum(1 for v in bg_dict.values() if v["active"])
    logger.info(f"build_bg_dict: {len(bg_dict)} BG total, {active_count} active")
    return bg_dict


# ─── pl.txt parser ────────────────────────────────────────────────────────────

def _parse_pl_file(
    bg_name:   str,
    pl_file:   str,
    kunde_map: dict,
) -> tuple[bool, str, Optional[str], bool, bool, Optional[str], list, list, list]:
    """
    Parse pl.txt for one BG.
    Cache stores parsed result as 8-element list (JSON-safe).

    Returns:
        active, kunde, project_name, dmc, medi, lp_nr,
        intranet_bot, intranet_top, errors
    """
    errors: list[dict] = []

    if not os.path.exists(pl_file):
        errors.append(make_error(bg_name, "Error_72", f"pl.txt not found: {pl_file}"))
        return False, "", None, False, False, None, [], [], errors

    # Cache format: [active, kunde, project_name, dmc, medi, lp_nr, bot, top]
    cached = get(pl_file)
    if cached is not None and isinstance(cached, list) and len(cached) == 8:
        active, kunde, project_name, dmc, medi, lp_nr, bot, top = cached
        # Guard: bot/top must be dicts — reject stale list-format cache
        if isinstance(bot, dict) and isinstance(top, dict):
            return active, kunde, project_name, dmc, medi, lp_nr, bot, top, errors
        # else fall through to re-parse

    try:
        with open(pl_file, "r", encoding="cp1252", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading pl.txt {pl_file}: {e}")
        errors.append(make_error(bg_name, "Error_72", f"Cannot read pl.txt: {pl_file}", open_file=pl_file))
        return False, "", None, False, False, None, [], [], errors

    active        = True
    kunde         = ""
    project_name  = None
    dmc           = False
    medi          = False
    lp_nr         = None
    intranet_bot: dict[str, list] = {}
    intranet_top: dict[str, list] = {}

    for line in lines:
        ls    = line.strip().lower()
        parts = ls.split()

        if "kunde:" in ls:
            raw   = ls.split("kunde:")[1].strip()
            short = raw.split()[0][:2]
            kunde = kunde_map.get(short, short)

        if "projekt:" in ls:
            project_name = ls.split("projekt:")[1].strip()

        if bg_name.lower() in parts and any(p.startswith("z_") for p in parts):
            active = False

        if len(parts) <= 5:
            continue

        if "smd" in parts:
            while parts and parts[-1] != "smd":
                parts.pop()
                if len(parts) < 5:
                    break

        if len(parts) < 5:
            continue

        ref       = parts[0]
        ihl_nr    = parts[1]
        such_wort = parts[2]
        last_elem = parts[-1]

        if lp_nr is None and (parts[-1] == "lp" or parts[-2] == "lp"):
            lp_nr = ihl_nr

        if not dmc and such_wort == "aufkleberasys":
            dmc = True

        if (not medi and not any(intranet_bot.values())
                and not any(intranet_top.values()) and "medi" in last_elem):
            medi = True

        refs = [r.strip() for r in ref.split(",")] if "," in ref else [ref.strip()]
        key = ihl_nr if ihl_nr else "unknown"									  
        for r in refs:
            if r in _BL_COMP:
                continue
            if "smdbot" in parts:
                if r not in intranet_bot.get(key, []):
                    intranet_bot.setdefault(key, []).append(r)
            elif "smdtop" in parts:
                if r not in intranet_top.get(key, []):
                    intranet_top.setdefault(key, []).append(r)

    if not active:
        errors.append(make_error(bg_name, "Error_72", "BG is inactive (Z_ marker found in pl.txt)."))

    put(pl_file, [active, kunde, project_name, dmc, medi,
                  lp_nr, intranet_bot, intranet_top])

    return active, kunde, project_name, dmc, medi, lp_nr, \
           intranet_bot, intranet_top, errors


# ─── LP image resolver ────────────────────────────────────────────────────────

def _resolve_lp_images(
    lp_nr: Optional[str],
    ctx,
) -> tuple[Optional[str], Optional[str]]:
    """
    Find empty LP images for both sides from empty_lp_path.
    Returns (lp_image_bot, lp_image_top) as absolute paths.

    Folder structure:
        empty_lp_path/
            {lp_nr}_Hersteller_Model/
                images/
                    image_1.jpg   ← TOP
                    image_2.jpg   ← BOT

    If multiple folders match lp_nr, newest (by mtime) wins.
    """
    if not lp_nr or not os.path.isdir(ctx.empty_lp_path):
        return None, None

    try:
        candidates = sorted(
            [
                os.path.join(ctx.empty_lp_path, f)
                for f in os.listdir(ctx.empty_lp_path)
                if f.startswith(lp_nr)
                and os.path.isdir(os.path.join(ctx.empty_lp_path, f))
            ],
            key=os.path.getmtime,
            reverse=True,
        )
    except Exception as e:
        logger.error(f"Error scanning empty_lp_path for {lp_nr}: {e}")
        return None, None

    if not candidates:
        logger.debug(f"No LP folder found for lp_nr={lp_nr}")
        return None, None

    lp_image_bot = None
    lp_image_top = None

    for folder_path in candidates:
        top_path = os.path.join(folder_path, "Referenz", "Scan1.jpg")
        bot_path = os.path.join(folder_path, "Referenz", "Scan2.jpg")

        if lp_image_top is None and os.path.exists(top_path):
            lp_image_top = top_path
        if lp_image_bot is None and os.path.exists(bot_path):
            lp_image_bot = bot_path

        if lp_image_bot and lp_image_top:
            break

    logger.debug(f"LP images for {lp_nr}: bot={lp_image_bot} top={lp_image_top}")
    return lp_image_bot, lp_image_top


# ─── Kunde map ────────────────────────────────────────────────────────────────

def _load_kunde_map(ctx) -> dict[str, str]:
    """
    Load kunde short→full name mapping from CSV.
    CSV format: short_name,full_name  (comma or semicolon delimited).
    Cache stores the parsed dict, keyed by real file path.
    """
    csv_path = ctx.kunde_csv

    cached = get(csv_path)
    if cached is not None and isinstance(cached, dict):
        return cached

    mapping: dict[str, str] = {}

    if not os.path.exists(csv_path):
        logger.warning(f"Kunde CSV not found: {csv_path}")
        return mapping

    lines = []
    for encoding in ("utf-8", "cp1252"):
        try:
            with open(csv_path, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()
            break
        except Exception:
            pass

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        delim = ";" if ";" in line else ","
        parts = line.split(delim, 1)
        if len(parts) == 2:
            short = parts[0].strip().lower()
            full  = parts[1].strip()
            if short:
                mapping[short] = full

    logger.info(f"Kunde map loaded: {len(mapping)} entries from {csv_path}")
    put(csv_path, mapping)
    return mapping
