"""
AOI Tool - Error management

_ERROR_REGISTRY is built automatically at startup by reading ERRORS_XLS_FILE.
																		  

Error dict structure:
{
    "timestamp":      "2026-05-21 14:30:00",
    "bg_name":        "8009917.04",
    "pp_name":        "8009917_04BOT_ROT",  # None = BG-level error
    "error_code":     "Error_1",
    "error_type":     "Critical",           # from Excel col E
    "short_desc":     "CAD missing",        # from Excel col D
    "long_desc":      "File not found: P:/CadRuest/...",  # written in code
    "open_file":      "P:/CadRuest/...",    # None if not file-related
    "affected_rows":  [12, 15],             # None if not applicable
}
"""

		 
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Error type → row color ───────────────────────────────────────────────────
_TYPE_COLORS: dict[str, str] = {
    "Critical":   "red",				   
    "Suggestion": "orange",										
    "Info":       "yellow",
}

# ─── Error registry — built at startup from Excel ─────────────────────────────
# { error_code: { short_desc, long_desc, error_type, open_file } }
_ERROR_REGISTRY: dict[str, dict] = {}


def load_error_registry():	  
    """
    Load error definitions from ERRORS_XLS_FILE into _ERROR_REGISTRY.
    Called once at startup from main.py.

    Excel columns:
        B = ErrorNr        (e.g. "Error_1")
        C = LongDescription
        D = ShortDescription
        E = Type           ("Critical" | "Suggestion" | "Info")
        F = OpenFile       ("yes" | "no")
    """
    global _ERROR_REGISTRY
				   
    try:
        from config import ERRORS_XLS_FILE
        import openpyxl
        import os


        if not os.path.exists(ERRORS_XLS_FILE):
            logger.warning(f"ERRORS_XLS_FILE not found: {ERRORS_XLS_FILE} — using fallback registry")
            _build_fallback_registry()
            return

        wb  = openpyxl.load_workbook(ERRORS_XLS_FILE, read_only=True, data_only=True)
        ws  = wb.active
        reg = {}

        for row in ws.iter_rows(min_row=2, values_only=True):

            # B=col1, C=col2, D=col3, E=col4, F=col5  (0-indexed after min_col)
            try:
                raw_nr     = str(row[1]).strip() if row[1] else None   # col B
                long_desc  = str(row[2]).strip() if row[2] else ""      # col C
                short_desc = str(row[3]).strip() if row[3] else ""      # col D
                error_type = str(row[4]).strip() if row[4] else "Info"  # col E
                open_file  = str(row[5]).strip().lower() if row[5] else "no"  # col F

                if not raw_nr or raw_nr in ("None", ""):
                    continue

                # Normalise to "Error_N" whether col B contains "1" or "Error_1"
                if raw_nr.startswith("Error_"):
                    error_nr = raw_nr
                else:
                    try:
                        error_nr = f"Error_{int(float(raw_nr))}"
                    except ValueError:
                        error_nr = raw_nr

                if error_type not in _TYPE_COLORS:
                    logger.warning(f"Unknown error_type '{error_type}' for {error_nr} — defaulting to Info")
                    error_type = "Info"

                reg[error_nr] = {
                    "short_desc": short_desc,
                    "long_desc":  long_desc,
                    "error_type": error_type,
                    "open_file":  open_file == "yes",
                }
            except Exception as e:
                logger.warning(f"Skipping row in errors.xlsx: {e}")
                continue

        wb.close()
        _ERROR_REGISTRY = reg
        logger.info(f"Error registry loaded: {len(reg)} entries from {ERRORS_XLS_FILE}")

    except Exception as e:
        logger.error(f"Error loading error registry: {e} — using fallback registry")
        _build_fallback_registry()


def _build_fallback_registry():
    """Minimal fallback registry used when Excel file is missing."""
    global _ERROR_REGISTRY
    _ERROR_REGISTRY = {
        "Error_1":  {"short_desc": "CAD missing",       "long_desc": ".cad file not found.",           "error_type": "Critical",   "open_file": True},
        "Error_2":  {"short_desc": "DESC missing",      "long_desc": ".desc file not found.",          "error_type": "Critical",   "open_file": True},
        "Error_3":  {"short_desc": "REF missing",       "long_desc": ".ref file not found.",           "error_type": "Info",       "open_file": False},
        "Error_4":  {"short_desc": "SIZE missing",      "long_desc": ".size file not found.",          "error_type": "Info",       "open_file": False},
        "Error_5":  {"short_desc": "DEF missing",       "long_desc": ".def file not found.",           "error_type": "Critical",   "open_file": True},
        "Error_6":  {"short_desc": "MOD missing",       "long_desc": ".mod file not found.",           "error_type": "Info",       "open_file": False},
        "Error_9":  {"short_desc": "Duplicate ref",     "long_desc": "Duplicate component in .cad.",   "error_type": "Suggestion", "open_file": True},
        "Error_12": {"short_desc": "No test plan",      "long_desc": "No test plan found in CadRuest.","error_type": "Critical",   "open_file": False},
        "Error_64": {"short_desc": "No BOT/TOP",        "long_desc": "Testplan has no BOT or TOP.",    "error_type": "Suggestion", "open_file": False},
        "Error_68": {"short_desc": "PP locked",         "long_desc": "Testplan is locked.",            "error_type": "Suggestion", "open_file": False},
        "Error_72": {"short_desc": "BG inactive",       "long_desc": "BG is inactive or deleted.",     "error_type": "Critical",   "open_file": False},
        "Error_73": {"short_desc": "CLI mismatch",      "long_desc": "BOT and TOP have different CLI.","error_type": "Critical",   "open_file": False},
        "Error_76": {"short_desc": "Wrong CLI",         "long_desc": "Wrong CLI for Wago/Drago.",      "error_type": "Critical",   "open_file": True},
        "Error_77": {"short_desc": "Haran missing",     "long_desc": "Haran Bild file missing.",       "error_type": "Suggestion", "open_file": False},
        "Error_81": {"short_desc": "PP in Vorbereitung","long_desc": "PP found in Vorbereitung.",      "error_type": "Info",       "open_file": False},
        "Error_82": {"short_desc": "PP in CadRuest",    "long_desc": "PP found in CadRuest.",          "error_type": "Info",       "open_file": False},
    }
    logger.info(f"Fallback error registry loaded: {len(_ERROR_REGISTRY)} entries")


# ─── Public API ───────────────────────────────────────────────────────────────

def make_error(
    bg_name:       str,
    error_code:    str,
    long_desc:     str,
    pp_name:       Optional[str]       = None,
    open_file:     Optional[str]       = None,
    affected_rows: Optional[list[int]] = None,
) -> dict:
    """
    Create an error dict.

    Args:
        bg_name:       BG name (always required)
        error_code:    e.g. "Error_1"
        long_desc:     Runtime error message written in code
        pp_name:       PP name if PP-level error, None for BG-level
        open_file:     Absolute path to affected file, None if not file-related
        affected_rows: List of affected line numbers in the file
    """

    entry      = _ERROR_REGISTRY.get(error_code.split("_")[-1], {})
    error_type = entry.get("error_type", "Info")
    short_desc = entry.get("short_desc", error_code)

    return {
        "timestamp":     time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "bg_name":       bg_name,
        "pp_name":       pp_name,
        "error_code":    error_code,
        "error_type":    error_type,
        "short_desc":    short_desc,
        "long_desc":     long_desc,
        "open_file":     open_file,
        "affected_rows": affected_rows,
    }


def add_bg_error(
    bg_dict:       dict,
    bg_name:       str,
    error_code:    str,
    long_desc:     str,
    open_file:     Optional[str]       = None,
    affected_rows: Optional[list[int]] = None,
):
    """Add a BG-level error directly into bg_dict."""
    if bg_name not in bg_dict:
        logger.warning(f"add_bg_error: '{bg_name}' not in bg_dict")
        return
    err = make_error(bg_name, error_code, long_desc,
                     open_file=open_file, affected_rows=affected_rows)
    bg_dict[bg_name].setdefault("bg_errors", [])
    if err not in bg_dict[bg_name]["bg_errors"]:
        bg_dict[bg_name]["bg_errors"].append(err)


# ─── Row color helpers ────────────────────────────────────────────────────────

def row_color_from_errors(errors: list[dict]) -> str:
    """Compute worst-case row color from a list of error dicts."""
    for severity in ("Critical", "Suggestion", "Info"):
        if any(e.get("error_type") == severity for e in errors):
            return _TYPE_COLORS[severity]
										 
										 
    return "green"


def bg_row_color(bg_dict: dict, bg_name: str, pp_dict: dict) -> str:
	   
							   
    """Overall row color for a BG — worst across bg_errors + all PP errors."""
	   
    if not bg_dict.get(bg_name, {}).get("active", True):
        return "red"

    all_errors = list(bg_dict[bg_name].get("bg_errors", []))
    for pp in pp_dict.values():
        if pp.get("bg_name") == bg_name:
            all_errors.extend(pp.get("pp_errors", []))

    return row_color_from_errors(all_errors)


def get_error_color(error_type: str) -> str:
    """Return row color for a given error_type string."""
    return _TYPE_COLORS.get(error_type, "yellow")
