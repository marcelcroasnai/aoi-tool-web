"""
AOI Tool - PP Inspection

Single responsibility: build a complete pp_dict.

All private functions return values — no in-place mutation.
Cache stores only parsed results keyed by real file path.
"""

import os
import re
import logging
from collections import defaultdict
from typing import Optional

from modules.app_context import get_ctx
from modules.file_cache import get, put, file_exists_cached
from modules.errors import make_error, add_bg_error

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────────────────────

def read_pp_for_search(folder: str, pp_name: str, pp_path: str) -> dict:
    """
    Read CLI and pm_list for a single PP — used by PM search.
    Does not generate errors, does not need bg context.

    Returns:
        {
            "cli":     str | None,
            "pm_list": [ { "pm": str, "ihl_nr": str }, ... ]
        }

    Uses the same file cache as inspection — warm after any inspection run.
    """
    file_base = pp_name

    cad_path  = os.path.join(pp_path, file_base + ".cad")
    desc_path = os.path.join(pp_path, file_base + ".desc")

    # ── CLI from .desc ──────────────────────────────────────────────────────
    cli = None
    cached_desc = get(desc_path)
    if cached_desc is not None and isinstance(cached_desc, str):
        cli = cached_desc
    elif os.path.exists(desc_path):
        try:
            with open(desc_path, "r", encoding="cp1252", errors="replace") as f:
                for line in f:
                    line = line.strip().lower()
                    if not line or line.startswith("*"):
                        continue
                    if line.startswith("bauteiledirectory"):
                        cli = line.split("\\")[-1].strip()
                        break
        except Exception as e:
            logger.debug(f"search: cannot read .desc {desc_path}: {e}")
        put(desc_path, cli)

    # ── pm_list from .cad ───────────────────────────────────────────────────
    pm_list: list[str] = []
    cache_key  = cad_path
    cached_cad = get(cache_key)

    if cached_cad is not None:
        try:
            pm_dict = cached_cad[1]
            if isinstance(pm_dict, dict):
                pm_list = list(pm_dict.keys())
        except (IndexError, TypeError):
            pass

    if not pm_list and os.path.exists(cad_path):
        # Cache miss — parse via existing _read_cad which populates the cache
        _read_cad(pp_name, "", cad_path)
        cached_cad = get(cache_key)
        if cached_cad is not None:
            try:
                pm_dict = cached_cad[1]
                if isinstance(pm_dict, dict):
                    pm_list = list(pm_dict.keys())
            except (IndexError, TypeError):
                pass

    return {"cli": cli, "pm_list": pm_list}


def build_pp_dict_ap(bg_dict: dict) -> dict:
    """Build complete pp_dict for AP / text mode."""
    ctx     = get_ctx()
    pp_list = get_pp_list()
    pp_dict = {}

    for bg_name, bg in bg_dict.items():
        if not bg.get("active"):
            continue

        bg_nr, bg_idx = bg_name.split(".")
        bg_pp_folders = _find_pp_folders(bg_nr, bg_idx, pp_list, bg_name, bg_dict)

        if not bg_pp_folders:
            add_bg_error(bg_dict, bg_name, "Error_12", f"No test plan found in CadRuest for {bg_name}")
            continue

        for pp_name, locked, folder in bg_pp_folders:
            pp_path = os.path.join(ctx.cad_ruest_path, folder)

            if not os.path.isdir(pp_path):
                logger.warning(f"PP folder not found: {pp_path}")
                err = make_error(bg_name, "Error_12", f"PP folder not found on disk: {folder}", pp_name=pp_name)
                pp_dict[pp_name] = _empty_pp(pp_name, bg_name, locked, errors=[err])
                continue

            logger.debug(f"Filling PP: {pp_name} | folder: {folder}")
            pp = _fill_pp(pp_name, bg_name, locked, pp_path, folder)
            pp_dict[pp_name] = pp

            # Register pp_name in bg_dict pp_list
            if pp_name not in bg_dict[bg_name]["pp_list"]:
                bg_dict[bg_name]["pp_list"].append(pp_name)

    _check_cli_consistency(pp_dict, bg_dict)
    _check_missing_side_ap(pp_dict, bg_dict, ctx)

    logger.info(f"build_pp_dict_ap: {len(pp_dict)} PP built")
    return pp_dict


def build_pp_dict_vb(bg_names: list[str], bg_dict: dict) -> dict:
    """Build complete pp_dict for VB mode."""
    ctx     = get_ctx()
    pp_dict = {}

    for bg_name in bg_names:
        bg_nr, bg_idx = bg_name.split(".")
        bg_path = os.path.join(ctx.vorbereitung_path, bg_name)
        if not os.path.isdir(bg_path):
            continue

        for folder in os.listdir(bg_path):
            fp = os.path.join(bg_path, folder)
            if not os.path.isdir(fp):
                continue
            if len(folder) <= 10:
                continue
            if not folder.startswith(bg_nr):
                continue
            if "BOT" not in folder and "TOP" not in folder:
                continue
            if f"{bg_nr}_{bg_idx}" not in folder:
                continue

            pp = _fill_pp(folder, bg_name, locked=False, pp_path=fp, folder=folder)
            pp_dict[folder] = pp
            if bg_name in bg_dict and folder not in bg_dict[bg_name]["pp_list"]:
                bg_dict[bg_name]["pp_list"].append(folder)

    _check_cli_consistency(pp_dict, bg_dict)
    _check_missing_side_vb(pp_dict, bg_dict, ctx)

    logger.info(f"build_pp_dict_vb: {len(pp_dict)} PP built")
    return pp_dict


def build_pp_dict_single(pp_name: str) -> dict:
    """Build pp_dict for a single standalone PP."""
    ctx     = get_ctx()
    bg_name = _pp_to_bg(pp_name)
    pp_path = os.path.join(ctx.cad_ruest_path, pp_name)

    if not os.path.isdir(pp_path):
        err = make_error(bg_name, "Error_12", f"PP folder not found: {pp_path}", pp_name=pp_name)
        return {pp_name: _empty_pp(pp_name, bg_name, locked=False, errors=[err])}

    return {pp_name: _fill_pp(pp_name, bg_name, locked=False,
                               pp_path=pp_path, folder=pp_name)}


# ─── PP folder detection ──────────────────────────────────────────────────────

# ─── PP list — in-memory scan of CadRuest ────────────────────────────────────
# Scanned once at first use, refreshed on explicit request.
_pp_list_cache: list[str] = []
_pp_list_lock  = __import__("threading").Lock()


def get_pp_list() -> list[str]:
    """
    Return the in-memory PP list.
    Scans CadRuest on first call or after refresh_pp_list().
    """
    global _pp_list_cache
    with _pp_list_lock:
        if _pp_list_cache:
            return list(_pp_list_cache)

    return refresh_pp_list()


def refresh_pp_list() -> list[str]:
    """
    Scan CadRuest folder and rebuild the in-memory PP list.
    Called at first use and on explicit refresh request.
    Returns the new list.
    """
    global _pp_list_cache
    ctx = get_ctx()

    try:
        folders = [
            f for f in os.listdir(ctx.cad_ruest_path)
            if os.path.isdir(os.path.join(ctx.cad_ruest_path, f))
        ]
        with _pp_list_lock:
            _pp_list_cache = sorted(folders)
        logger.info(
            f"PP list refreshed: {len(_pp_list_cache)} folders "
            f"in {ctx.cad_ruest_path}"
        )
        return list(_pp_list_cache)
    except Exception as e:
        logger.error(f"Error scanning CadRuest: {e}")
        return []


def _parse_pp_folder(folder: str, bg_nr: str) -> Optional[tuple[str, bool, Optional[str]]]:
    """
    Parse one CadRuest folder belonging to `bg_nr`.

    Returns (idx, locked, redirect_target) or None if the folder is not a PP
    of this BG.
        idx             : index token — the digits immediately after
                          "{bg_nr}_" (or "{bg_nr}__" for locked folders)
        locked          : True if the folder uses the "__" lock prefix
        redirect_target : target index if the folder is a redirect marker
                          "<idx>=_<target>", else None

    Matching the index as a parsed token (not a substring) is what stops
    BG .1 from colliding with _10 / _11 plans.
    """
    if not folder.startswith(bg_nr) or "THT" in folder:
        return None

    rest = folder[len(bg_nr):]
    locked = rest.startswith("__")
    sep = "__" if locked else "_"
    if not rest.startswith(sep):
        return None

    rest = rest[len(sep):]                       # e.g. "10TOP_DMC" / "10=_09"
    m = re.match(r"(\d+)", rest)
    if not m:
        return None
    idx = m.group(1)

    after = rest[len(idx):]                       # e.g. "TOP_DMC" / "=_09"
    redirect_target = None
    mt = re.match(r"=_?(\d+)", after)             # "<idx>=_<target>" marker
    if mt:
        redirect_target = mt.group(1)

    return idx, locked, redirect_target


def _find_pp_folders(
    bg_nr: str,
    bg_idx: str,
    pp_list: list[str],
    bg_name: str,
    bg_dict: dict,
) -> list[tuple[str, bool, str]]:
    """
    Returns list of (pp_name, locked, folder_name) for the given BG.
    folder_name : actual directory name in CadRuest
    pp_name     : canonical key (__ resolved)

    Index matching is exact (token-based), not substring. If a redirect
    marker "<bg_idx>=_<target>" exists for this BG, the BG is inspected with
    the <target> index plans; the redirect wins over any stray literal
    <bg_idx> plan and the result is independent of folder iteration order.
    """
    parsed: list[tuple[str, str, bool, Optional[str]]] = []   # (folder, idx, locked, rtgt)
    for folder in pp_list:
        info = _parse_pp_folder(folder, bg_nr)
        if info is not None:
            parsed.append((folder, *info))

    # 1. Resolve which index this BG should actually use (follow redirect marker)
    redirect_target: Optional[str] = None
    for folder, idx, locked, rtgt in sorted(parsed):     # sorted → deterministic
        if idx == bg_idx and rtgt is not None:
            redirect_target = rtgt
            break
    pp_idx = redirect_target if redirect_target is not None else bg_idx

    # 2. Collect every real plan folder whose index == pp_idx (skip redirect markers)
    seen: dict[str, tuple[bool, str]] = {}
    for folder, idx, locked, rtgt in parsed:
        if idx != pp_idx or rtgt is not None:
            continue
        if locked:
            pp_name = _resolve_locked_name(folder)
            seen[pp_name] = (True, folder)
        else:
            if "BOT" not in folder and "TOP" not in folder:
                add_bg_error(bg_dict, bg_name, "Error_64", f"Testplan {folder} has no BOT or TOP in name.")
            seen.setdefault(folder, (False, folder))

    return [(pp_name, locked, folder)
            for pp_name, (locked, folder) in seen.items()]


def _resolve_locked_name(folder: str) -> str:
    return folder.replace("__", "_", 1).replace("_gesperrt", "")


# ─── Core assembler ───────────────────────────────────────────────────────────

def _fill_pp(
    pp_name: str,
    bg_name: str,
    locked:  bool,
    pp_path: str,
    folder:  str,
) -> dict:
    """
    Read all Viscom SI files for one PP.
    Returns a complete pp entry dict.
    LP images are resolved at BG level (bg_dict), not here.

    folder   = actual directory name on disk (may contain __ and _gesperrt)
    pp_name  = canonical name used as key and as file basename inside the folder
    file_base = pp_name always (files inside locked folder use canonical name)
    """
    file_base = pp_name

    cad_bot, cad_top, pm_dict, cad_errors = _read_cad(
        pp_name, bg_name, os.path.join(pp_path, file_base + ".cad")
    )

    cli,    desc_errors   = _read_desc(
        pp_name, bg_name, os.path.join(pp_path, file_base + ".desc")
    )
    nutzen, def_errors    = _read_def(
        pp_name, bg_name, os.path.join(pp_path, file_base + ".def")
    )
    exist_errors          = _check_file_exists(pp_name, bg_name, pp_path, file_base)
    hinweis               = _read_hinweis(pp_path)
    haran_errors          = _check_haran_bild(pp_name, bg_name)
    '''
    print("_fill_pp before return:\n", {
        "bg_name":      bg_name,
        "locked":       locked,
        "cad_bot":      cad_bot,
        "cad_top":      cad_top,
        "cli":          cli,
        "nutzen_in_lp": nutzen,
        "pm_dict":      pm_dict,
        "hinweis":      hinweis,
        "pp_errors":    cad_errors + desc_errors + def_errors
                        + exist_errors + haran_errors,
    })
	'''
    return {
        "bg_name":      bg_name,
        "locked":       locked,
        "cad_bot":      cad_bot,
        "cad_top":      cad_top,
        "cli":          cli,
        "nutzen_in_lp": nutzen,
        "pm_dict":      pm_dict,
        "hinweis":      hinweis,
        "pp_errors":    cad_errors + desc_errors + def_errors
                        + exist_errors + haran_errors,
    }


# ─── File readers ─────────────────────────────────────────────────────────────

def _read_cad(
    pp_name: str,
    bg_name: str,
    cad_path: str,
) -> tuple[dict, dict, dict, list]:
    """
    Returns (cad_bot, cad_top, pm_dict, errors).

    cad_bot / cad_top:
        { ihl_nr: [ref, ...] }

    pm_dict:
        {
            pruefmuster_name: [
                { ihl_nr: [ref, ...] },
                ...
            ]
        }
    """

    errors: list = []

    if not os.path.exists(cad_path):
        errors.append(make_error(bg_name, "Error_1", f"File not found: {cad_path}", pp_name=pp_name))
        return {}, {}, {}, errors

    side = "bot" if "bot" in pp_name.lower() else "top"

    cache_key = cad_path
    cached = get(cache_key)

    comps = None
    pm_dict = None

    # ---------- LOAD FROM CACHE ----------
    if cached is not None:
        try:
            c0, c1 = cached[0], cached[1]

            if isinstance(c0, dict) and isinstance(c1, dict):
                comps = c0
                pm_dict = c1

        except (IndexError, TypeError):
            pass

    # ---------- PARSE FILE ----------
    if comps is None:

        # { ihl_nr: [ref, ...] }
        comps = {}

        # {
        #     pm: [
        #         { ihl_nr: [refs...] },
        #         ...
        #     ]
        # }
        pm_dict = {}

        try:
            with open(
                cad_path,
                "r",
                encoding="cp1252",
                errors="replace",
            ) as f:

                for line in f:
                    line = line.strip()

                    if not line or line.startswith("*"):
                        continue

                    parts = line.split()

                    if len(parts) < 8:
                        continue

                    try:
                        ref, pm, x, y, rot, ihl_nr, _, _ = parts
                    except ValueError:
                        continue

                    ref = ref.lower().strip()
                    pm = pm.strip()
                    ihl_nr = ihl_nr.strip()

                    key = ihl_nr if ihl_nr else "unknown"

                    # ---------- COMPONENTS ----------
                    if ref not in ("", "lp", "pcb"):

                        if ref not in comps.get(key, []):
                            comps.setdefault(key, []).append(ref)

                    # ---------- PM DICT ----------
                    if pm and ihl_nr and ref:
                        ref = ref.upper()
                        pm_entry = pm_dict.setdefault(pm, {})
                        ref_list = pm_entry.setdefault(ihl_nr, [])

                        if ref not in ref_list:
                            ref_list.append(ref)

        except Exception as e:
            logger.error(f"Error reading .cad {cad_path}: {e}")

        # ---------- CACHE ----------
        put(cache_key, [comps, pm_dict])

    # ---------- DUPLICATE DETECTION ----------
    seen = set()

    for refs in comps.values():

        for ref in refs:

            if ref in seen:
                errors.append(make_error(bg_name, "Error_9", f"Duplicate ref '{ref}' in {os.path.basename(cad_path)}", pp_name=pp_name, open_file=cad_path))

            seen.add(ref)

    cad_bot = comps if side == "bot" else {}
    cad_top = comps if side == "top" else {}

    return cad_bot, cad_top, pm_dict, errors


def _read_desc(
    pp_name: str,
    bg_name: str,
    desc_path: str,
) -> tuple[Optional[str], list]:
    """Returns (cli, errors)."""
    errors: list[dict] = []

    if not os.path.exists(desc_path):
        errors.append(make_error(bg_name, "Error_3", f"File not found: {desc_path}", pp_name=pp_name))
        return None, errors

    cached = get(desc_path)
    if cached is not None and isinstance(cached, str):
        return cached, errors

    cli = None
    try:
        with open(desc_path, "r", encoding="cp1252", errors="replace") as f:
            for line in f:
                line = line.strip().lower()
                if not line or line.startswith("*"):
                    continue
                if line.startswith("bauteiledirectory"):
                    cli = line.split("\\")[-1].strip()
                    break
    except Exception as e:
        logger.error(f"Error reading .desc {desc_path}: {e}")

    put(desc_path, cli)
    return cli, errors


def _read_def(
    pp_name: str,
    bg_name: str,
    def_path: str,
) -> tuple[Optional[int], list]:
    """Returns (nutzen_in_lp, errors)."""
    errors: list[dict] = []

    if not os.path.exists(def_path):
        errors.append(make_error(bg_name, "Error_2", f"File not found: {def_path}", pp_name=pp_name))
        return None, errors

    cached = get(def_path)
    if cached is not None and isinstance(cached, int):
        return cached, errors

    nutzen = None
    try:
        with open(def_path, "r", encoding="cp1252", errors="replace") as f:
            for line in f:
                
                line = line.strip().lower()
                if line.startswith("lp"):
                    parts = line.split()
                    #print("parts:", parts)
                    if len(parts) >= 2:
                        try:
                            nutzen = int(parts[1])
                        except ValueError:
                            pass
    except Exception as e:
        logger.error(f"Error reading .def {def_path}: {e}")

    put(def_path, nutzen)
    return nutzen, errors


def _read_hinweis(pp_path: str) -> Optional[str]:
    """Returns hinweis content string or None."""
    path = os.path.join(pp_path, "hinweis.txt")

    cached = get(path)
    if cached is not None and isinstance(cached, str):
        return cached

    if not os.path.exists(path):
        return None

    content = None
    try:
        with open(path, "r", encoding="iso-8859-1", errors="replace") as f:
            lines = [
                l.strip() for l in f
                if l.strip() and not l.strip().startswith("*")
            ]
        content = "\n".join(lines) or None
    except Exception as e:
        logger.error(f"Error reading hinweis {path}: {e}")

    if content:
        put(path, content)
    return content


def _check_file_exists(
    pp_name:   str,
    bg_name:   str,
    pp_path:   str,
    file_base: str,
) -> list[dict]:
    """Returns errors for missing .ref / .size """
    errors: list[dict] = []
    for ext, code in (
        (".ref",  "Error_4"),
        (".size", "Error_5")
    ):
        path = os.path.join(pp_path, file_base + ext)
        if not file_exists_cached(path):
            errors.append(make_error(bg_name, code,
                f"File not found: {path}", pp_name=pp_name))
    return errors


def _check_haran_bild(pp_name: str, bg_name: str) -> list[dict]:
    """Returns errors for missing Haran Bild files."""
    errors: list[dict] = []
    ctx = get_ctx()
    error_msg = ""
    for ext in (".hr.bmp", ".us.bmp", ".uscal"):
        path = os.path.join(ctx.picture_path, pp_name + ext)
        if not file_exists_cached(path):
            error_msg += ", " + f"{pp_name}{ext}"
            
    if error_msg:
        error_msg = error_msg[2:]
        errors.append(make_error(bg_name, "Error_77", f"Missing in PICTURE folder: {error_msg}", pp_name=pp_name))
    return errors


# ─── Cross-PP checks ─────────────────────────────────────────────────────────

def _check_cli_consistency(pp_dict: dict, bg_dict: dict) -> None:
    """Add error to both PP of a BG if BOT and TOP have different CLI."""
    bg_clis: dict[str, dict[str, str]] = defaultdict(dict)
    for pp_name, pp in pp_dict.items():
        if pp.get("cli"):
            side = "BOT" if "bot" in pp_name.lower() else "TOP"
            bg_clis[pp["bg_name"]][side] = pp["cli"]

    for bg_name, sides in bg_clis.items():
        if len(sides) == 2 and sides.get("BOT") != sides.get("TOP"):
            for pp_name, pp in pp_dict.items():
                if pp["bg_name"] == bg_name:
                    err = make_error(bg_name, "Error_73", "BOT and TOP have different CLI.", pp_name=pp_name)
                    if err not in pp["pp_errors"]:
                        pp["pp_errors"].append(err)


def _check_missing_side_ap(pp_dict: dict, bg_dict: dict, ctx) -> None:
    """AP: if a side is missing in CadRuest, look in Vorbereitung."""
    bg_sides = _get_bg_sides(pp_dict)

    for bg_name, bg in bg_dict.items():
        if not bg.get("active"):
            continue
        has_bot = bool(bg.get("intranet_bot"))
        has_top = bool(bg.get("intranet_top"))
        sides   = bg_sides.get(bg_name, set())

        for side, has_side in (("bot", has_bot), ("top", has_top)):
            if not (has_side and side not in sides):
                continue
            vb_path = os.path.join(ctx.vorbereitung_path, bg_name)
            if not os.path.isdir(vb_path):
                continue
            for folder in os.listdir(vb_path):
                fp = os.path.join(vb_path, folder)
                if not os.path.isdir(fp) or side.upper() not in folder.upper():
                    continue
                pp = _fill_pp(folder, bg_name, locked=False, pp_path=fp, folder=folder)
                pp["pp_errors"].append(make_error(bg_name, "Error_81", f"PP {folder} found in Vorbereitung folder.", pp_name=folder))
                pp_dict[folder] = pp
                if folder not in bg_dict[bg_name]["pp_list"]:
                    bg_dict[bg_name]["pp_list"].append(folder)


def _check_missing_side_vb(pp_dict: dict, bg_dict: dict, ctx) -> None:
    """VB: if a side is missing in Vorbereitung, look in CadRuest."""
    bg_sides = _get_bg_sides(pp_dict)

    for bg_name, bg in bg_dict.items():
        if not bg.get("active"):
            continue
        bg_nr, bg_idx = bg_name.split(".")
        has_bot = bool(bg.get("intranet_bot"))
        has_top = bool(bg.get("intranet_top"))
        sides   = bg_sides.get(bg_name, set())

        for side, has_side in (("bot", has_bot), ("top", has_top)):
            if not (has_side and side not in sides):
                continue
            try:
                for folder in os.listdir(ctx.cad_ruest_path):
                    if (folder.startswith(f"{bg_nr}_{bg_idx}")
                            and side.upper() in folder.upper()
                            and "__" not in folder):
                        fp = os.path.join(ctx.cad_ruest_path, folder)
                        pp = _fill_pp(folder, bg_name, locked=False,
                                       pp_path=fp, folder=folder)
                        pp["pp_errors"].append(make_error(bg_name, "Error_82", f"PP {folder} found in CadRuest folder.", pp_name=folder))
                        pp_dict[folder] = pp
                        if bg_name in bg_dict and folder not in bg_dict[bg_name]["pp_list"]:
                            bg_dict[bg_name]["pp_list"].append(folder)
            except Exception as e:
                logger.error(f"Error scanning CadRuest for {bg_name}: {e}")


# ─── Utilities ────────────────────────────────────────────────────────────────

def _empty_pp(pp_name: str, bg_name: str, locked: bool,
              errors: list = None) -> dict:
    return {
        "bg_name":      bg_name,
        "locked":       locked,
        "cad_bot":      {},
        "cad_top":      {},
        "cli":          None,
        "nutzen_in_lp": None,
        "pm_dict":      {},
        "hinweis":      None,
        "pp_errors":    errors or [],
    }


def _get_bg_sides(pp_dict: dict) -> dict[str, set]:
    sides: dict[str, set] = defaultdict(set)
    for pp_name, pp in pp_dict.items():
        side = "bot" if "bot" in pp_name.lower() else "top"
        sides[pp["bg_name"]].add(side)
    return sides


def _pp_to_bg(pp_name: str) -> str:
    try:
        parts = pp_name.split("_")
        return f"{parts[0]}.{parts[1][:2]}"
    except Exception:
        return ""
