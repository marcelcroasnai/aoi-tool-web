"""
AOI Tool - Search PM

Searches Prüfmerkmale across all PP folders in CadRuest.

Data source:
    - CLI  : read from <pp_name>.desc via file cache (mtime+size invalidation)
    - PM   : read from <pp_name>.cad  via file cache (shared with inspection)

No pre-built index file needed. Cache is warm after any inspection run;
cold start reads all .cad/.desc files once and caches them automatically.
"""

import os
import logging
from typing import Literal
from pydantic import BaseModel

from modules.app_context import get_ctx
from modules.pp_inspect import get_pp_list, _resolve_locked_name, read_pp_for_search

logger = logging.getLogger(__name__)

SearchType = Literal["exact", "contains", "starts_with", "ends_with"]


# ─── Response models ──────────────────────────────────────────────────────────

class PmSearchResult(BaseModel):
    pp:     str   # canonical pp name  e.g. "8004085_10TOP_ROT_DMC"
    folder: str   # actual folder name (may differ for locked PPs)
    bg:     str   # e.g. "8004085.10"
    side:   str   # "BOT" | "TOP"
    cli:    str
    pm:     str   # Prüfmerkmal name


class PmSearchResponse(BaseModel):
    query:       str
    search_type: SearchType
    cli_filter:  str
    count:       int
    results:     list[PmSearchResult]


# ─── Public API ───────────────────────────────────────────────────────────────

def search_pm(
    query:      str,
    search_type: SearchType = "contains",
    cli_filter: str = "all",
) -> PmSearchResponse:
    """
    Search PM names across all PP in CadRuest.
    Returns matching (pp, cli, pm, ihl_nr) records sorted by BG → PP → PM.
    """
    query      = query.strip().lower()
    cli_filter = cli_filter.strip().lower()
    wildcard   = query == "*"

    if not query:
        return PmSearchResponse(query=query, search_type=search_type,
                                cli_filter=cli_filter, count=0, results=[])

    ctx     = get_ctx()
    pp_list = get_pp_list()
    results = []

    for folder in pp_list:
        # Skip THT and non-BG folders
        if not folder.startswith("80") or "THT" in folder:
            continue

        # Resolve canonical pp_name (locked folders use __ prefix)
        pp_name = _resolve_locked_name(folder)
        pp_path = os.path.join(ctx.cad_ruest_path, folder)

        data = read_pp_for_search(folder, pp_name, pp_path)

        cli = data["cli"] or ""

        # Apply CLI filter early to skip irrelevant PPs fast
        if cli_filter != "all" and cli_filter not in cli.lower():
            continue

        side = "BOT" if "bot" in pp_name.lower() else "TOP"
        bg   = _pp_to_bg(pp_name)

        for pm in data["pm_list"]:
            if not wildcard and not _matches(pm.lower(), query, search_type):
                continue

            results.append(PmSearchResult(
                pp=pp_name, folder=folder, bg=bg, side=side,
                cli=cli, pm=pm,
            ))

    results.sort(key=lambda r: (r.bg, r.pp, r.pm))

    logger.info(
        f"search_pm: '{query}' ({search_type}, cli={cli_filter}) "
        f"→ {len(results)} results across {len(pp_list)} PP"
    )
    return PmSearchResponse(
        query=query,
        search_type=search_type,
        cli_filter=cli_filter,
        count=len(results),
        results=results,
    )


def get_cli_list() -> list[str]:
    """
    Return unique CLI values from cli_global table in DB.
    Fast — no file I/O needed.
    """
    from db.schema import get_conn
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT cli FROM cli_global WHERE cli IS NOT NULL ORDER BY cli"
    ).fetchall()
    return [row[0] for row in rows]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _matches(pm: str, query: str, search_type: SearchType) -> bool:
    if search_type == "exact":
        return pm == query
    elif search_type == "contains":
        return query in pm
    elif search_type == "starts_with":
        return pm.startswith(query)
    elif search_type == "ends_with":
        return pm.endswith(query)
    return False


def _pp_to_bg(pp_name: str) -> str:
    """e.g. '8004085_10TOP_ROT' → '8004085.10'"""
    try:
        parts = pp_name.split("_")
        return f"{parts[0]}.{parts[1][:2]}"
    except Exception:
        return pp_name
