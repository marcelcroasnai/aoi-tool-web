"""
AOI Tool - App Context
Gestionează modul Live / Test și returnează path-urile corecte pentru fiecare.
Toate modulele care accesează fișiere folosesc get_ctx() în loc de config direct.
"""

from dataclasses import dataclass
from typing import Literal
import logging

logger = logging.getLogger(__name__)

Mode = Literal["live", "test"]

@dataclass
class AppContext:
    mode: Mode
    # Paths — populate din config în funcție de mod
    ap_html_file: str | None      # None = fetch din intranet (live)
    cli_ruest_path: str				   
    cad_ruest_path: str
    vorbereitung_path: str
    bg_info_path: str
    picture_path: str
    #pp_list_file: str
    kunde_csv: str
    empty_lp_path: str
    ideas_file: str



def _build_context(mode: Mode) -> AppContext:
    import config as cfg

    if mode == "live":
        return AppContext(
            mode="live",
            ap_html_file=None,
			cli_ruest_path=cfg.CLI_RUEST_PATH,								  
            cad_ruest_path=cfg.CAD_RUEST_PATH,
            vorbereitung_path=cfg.VORBEREITUNG_PATH,
            bg_info_path=cfg.BG_INFO_PATH,
            picture_path=cfg.PICTURE_PATH,
            #pp_list_file=cfg.PP_LIST_FILE,
            kunde_csv = cfg.KUNDE_CSV_FILE,
            empty_lp_path = cfg.EMPTY_LP_PATH,
            ideas_file = cfg.IDEAS_FILE,
            
        )
    else:
        return AppContext(
            mode="test",
            ap_html_file=cfg.TEST_AP_HTML_FILE,
			cli_ruest_path=cfg.TEST_CLI_RUEST_PATH,									   
            cad_ruest_path=cfg.TEST_CAD_RUEST_PATH,
            vorbereitung_path=cfg.TEST_VORBEREITUNG_PATH,
            bg_info_path=cfg.TEST_BG_INFO_PATH,
            picture_path=cfg.TEST_PICTURE_PATH,
            #pp_list_file=cfg.TEST_PP_LIST_FILE,
            kunde_csv = cfg.TEST_KUNDE_CSV_FILE,
            empty_lp_path = cfg.TEST_EMPTY_LP_PATH,
            ideas_file = cfg.TEST_IDEAS_FILE,

        )


# ─── Singleton context ────────────────────────────────────────────────────────
_current_mode: Mode = "live"
_ctx: AppContext = _build_context("live")


def get_ctx() -> AppContext:
    return _ctx


def set_mode(mode: Mode):
    global _current_mode, _ctx
    _current_mode = mode
    _ctx = _build_context(mode)
    logger.info(f"App mode schimbat la: {mode.upper()}")


def get_mode() -> Mode:
    return _current_mode
