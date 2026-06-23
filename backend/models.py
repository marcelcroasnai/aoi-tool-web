"""
AOI Tool - API Response Models

Internal pipeline uses plain dicts (bg_dict, pp_dict, ap_dict).
These Pydantic models are used only for the API response layer.

bg_dict  { bg_name:  { active, kunde, dmc, medi, lp_nr,
                        intranet_bot, intranet_top, bg_errors } }

pp_dict  { pp_name:  { bg_name, locked, cad_bot, cad_top,
                        cli, nutzen_in_lp, pm_dict,
                        hinweis, pp_errors } }

ap_dict  { fbs:  { bg_name, aoi_color, smd_line, auftragsmenge, bg_color } }
"""

from pydantic import BaseModel
from typing import Optional


# ─── Error ────────────────────────────────────────────────────────────────────

class InspectionError(BaseModel):
    timestamp:     str
    bg_name:       str
    pp_name:       Optional[str]       = None
    error_code:    str
    error_type:    str                          # "Critical" | "Suggestion" | "Info"
    short_desc:    str                          # from Excel col D
    long_desc:     str                          # written in code at error site
    open_file:     Optional[str]       = None   # abs path if file-related
    affected_rows: Optional[list[int]] = None   # line numbers in the file


# ─── PP summary (one sub-row in the table) ───────────────────────────────────

class PpSummary(BaseModel):
    name:         str            # "8009917_04BOT_ROT"
    side:         str            # "BOT" | "TOP"
    bg_name:      str            # back-reference
    locked:       bool = False
    cli:          Optional[str] = None
    nutzen_in_lp: Optional[int] = None
    cad_bot_count: int = 0
    cad_top_count: int = 0
    pm_count:     int = 0
    pm_dict:      dict = {}      # { ihl_nr: [ref, ...] }
    hinweis:      Optional[str] = None
    errors:       list[InspectionError] = []
    row_color:    str = "green"


# ─── BG summary (one header row + PP sub-rows) ───────────────────────────────

class BaugrupeSummary(BaseModel):
    name:               str
    active:             bool = True
    kunde:              Optional[str] = None
    project_name:       Optional[str] = None
    dmc:                bool = False
    medi:               bool = False
    lp_nr:              Optional[str] = None
    lp_image_bot:       Optional[str] = None
    lp_image_top:       Optional[str] = None
    intranet_bot_count: int = 0
    intranet_top_count: int = 0
    cad_bot_count:      int = 0
    cad_top_count:      int = 0						   			   
    pp_list:            list[str] = []
    # AP-specific (None for VB / text mode)
    aoi_color:          Optional[str] = None
    bg_color:           Optional[str] = None
    smd_line:           Optional[str] = None
    auftragsmenge:      Optional[str] = None
    # Errors at BG level
    bg_errors:          list[InspectionError] = []
    # PP sub-rows
    pp_list_detail:     list[PpSummary] = []
    # Overall row color
    row_color:          str = "green"


# ─── Inspection response ──────────────────────────────────────────────────────

class InspectionResponse(BaseModel):
    inspection_type:   str       # "ap" | "vb" | "text"
    timestamp:         str
    duration_seconds:  float
    count:             int
    results:           list[BaugrupeSummary]
