"""
AOI Tool - FastAPI Backend
Rulează pe Raspberry Pi sau Windows pentru test.

Pornire:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Accesibil din rețea la: http://<ip>:8000
Documentație API:        http://<ip>:8000/docs
"""

import logging
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import BaugrupeSummary, InspectionResponse
import auth
from modules.pipeline import (
    run_inspection_ap,
    run_inspection_vb,
    run_inspection_text,
)


from pydantic import BaseModel
from typing import Optional
import json, os, time
from pathlib import Path

class IdeaIn(BaseModel):
    user:       str
    short_desc: str
    long_desc:  Optional[str] = ""


# ─── Logging ──────────────────────────────────────────────────────────────────
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

from config import LOG_PATH

def _setup_logging():
    log_dir = Path(LOG_PATH)
    log_dir.mkdir(parents=True, exist_ok=True)

    today     = datetime.now().strftime("%Y.%m.%d")
    all_file  = log_dir / f"{today}_aoi_tool.log"
    err_file  = log_dir / f"{today}_aoi_errors.log"

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console — INFO and above
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    # Daily all-logs file — DEBUG and above
    # TimedRotatingFileHandler with midnight rotation keeps one file per day
    all_handler = logging.handlers.TimedRotatingFileHandler(
        filename    = all_file,
        when        = "midnight",
        interval    = 1,
        backupCount = 30,       # keep 30 days
        encoding    = "utf-8",
        utc         = False,
    )
    all_handler.suffix   = "%Y.%m.%d"
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(fmt)

    # Daily errors-only file — ERROR and above, includes traceback
    err_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    err_handler = logging.handlers.TimedRotatingFileHandler(
        filename    = err_file,
        when        = "midnight",
        interval    = 1,
        backupCount = 30,
        encoding    = "utf-8",
        utc         = False,
    )
    err_handler.suffix   = "%Y.%m.%d"
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(err_fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(all_handler)
    root.addHandler(err_handler)

_setup_logging()
logger = logging.getLogger(__name__)

# ─── Inspection result cache (in-memory) ─────────────────────────────────────
_cache: dict = {
    "ap": {"data": None, "timestamp": None, "running": False},
    "vb": {"data": None, "timestamp": None, "running": False},
}
CACHE_TTL = 120  # seconds

# In-memory store for the last AP result built from DB
# Updated by sync_errors via set_ap_memory() after every AP sync
_ap_memory: dict = {
    "ap_dict":   None,   # raw ap_dict from parse_auftragsplan
    "results":   None,   # list[BaugrupeSummary] built from DB
    "timestamp": None,   # float
    "duration":  None,   # float seconds
}

def set_ap_memory(ap_dict: dict, results: list, duration: float) -> None:
    """Called by sync_errors after a successful AP sync."""
    _ap_memory["ap_dict"]   = ap_dict
    _ap_memory["results"]   = results
    _ap_memory["timestamp"] = time.time()
    _ap_memory["duration"]  = duration

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AOI Tool API",
    description="Backend for Viscom SI AOI inspection",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Status models ────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    status:  str
    message: str


# ─── Info endpoints ───────────────────────────────────────────────────────────


@app.get("/api/ideas", tags=["Ideas"])
def get_ideas(_u: dict = Depends(auth.require("ideas.view"))):
    """Return all ideas from JSON file."""
    path = _ideas_path()
    if not os.path.exists(path):
        return {"ideas": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"ideas": json.load(f)}
    except Exception as e:
        logger.error(f"Error reading ideas: {e}")
        raise HTTPException(500, "Could not read ideas file")

@app.post("/api/ideas", tags=["Ideas"])
def add_idea(idea: IdeaIn, _u: dict = Depends(auth.require("ideas.edit"))):
    """Add a new idea to the JSON file."""
    path = _ideas_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    ideas = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                ideas = json.load(f)
        except Exception:
            ideas = []

    new_idea = {
        "id":         int(time.time() * 1000),
        "user":       idea.user.strip(),
        "short_desc": idea.short_desc.strip(),
        "long_desc":  idea.long_desc.strip(),
        "added_at":   time.strftime("%Y-%m-%d %H:%M", time.localtime()),
        "solved_at":  None,
    }
    ideas.insert(0, new_idea)   # newest first

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ideas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving idea: {e}")
        raise HTTPException(500, "Could not save idea")

    return {"message": "Idea saved", "idea": new_idea}

def _ideas_path() -> str:
    from modules.app_context import get_ctx
    return get_ctx().ideas_file

@app.get("/api/files/ideas", tags=["Files"])
def get_ideas_file(_u: dict = Depends(auth.require("ideas.view"))):
    """Download the improvement ideas Excel file."""
    import os
    from fastapi.responses import FileResponse
    from modules.app_context import get_ctx
    ctx = get_ctx()
    if not os.path.exists(ctx.ideas_file):
        raise HTTPException(404, f"Ideas file not found: {ctx.ideas_file}")
    from fastapi.responses import Response
    with open(ctx.ideas_file, "rb") as f:
        data = f.read()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "inline; filename=\"ideas.xlsx\""},
    )

@app.get("/", tags=["Info"])
def root():
    return {"message": "AOI Tool API v3.0", "docs": "/docs"}


@app.get("/api/status", response_model=StatusResponse, tags=["Info"])
def get_status():
    """Check server and drive accessibility."""
    import os
    from modules.app_context import get_ctx, get_mode
    ctx    = get_ctx()
    issues = []
    if not os.path.isdir(ctx.cad_ruest_path):
        issues.append(f"CadRuest not accessible: {ctx.cad_ruest_path}")
    if not os.path.isdir(ctx.vorbereitung_path):
        issues.append(f"Vorbereitung not accessible: {ctx.vorbereitung_path}")
    mode = get_mode()
    if issues:
        return StatusResponse(status="error", message=" | ".join(issues))
    return StatusResponse(status="ok", message=f"OK ({mode.upper()})")


@app.get("/api/mode", tags=["Info"])
def get_current_mode(_u: dict = Depends(auth.current_user)):
    """Return current mode (live/test) and active paths."""
    from modules.app_context import get_mode, get_ctx
    ctx = get_ctx()
    return {
        "mode": get_mode(),
        "paths": {
            "cad_ruest":    ctx.cad_ruest_path,
            "vorbereitung": ctx.vorbereitung_path,
            "bg_info":      ctx.bg_info_path,
            "picture":      ctx.picture_path,
            "ap_html":      ctx.ap_html_file,
        },
    }


@app.post("/api/mode/{mode}", tags=["Info"])
def set_mode(mode: str, _u: dict = Depends(auth.require("mode.switch"))):
    """Switch mode: live or test. Clears inspection cache and PP list."""
    from modules.app_context import set_mode as _set
    from modules.pp_inspect import refresh_pp_list
    if mode not in ("live", "test"):
        raise HTTPException(400, "Mode must be 'live' or 'test'.")
    _set(mode)
    for key in _cache:
        _cache[key]["data"]      = None
        _cache[key]["timestamp"] = None
    refresh_pp_list()
    return {"mode": mode, "message": f"Mode switched to {mode.upper()}"}


# ─── PP list ──────────────────────────────────────────────────────────────────

@app.post("/api/pp-list/refresh", tags=["Info"])
def refresh_pp_list_endpoint(_u: dict = Depends(auth.require("sync.run"))):
    """
    Rescan CadRuest folder and rebuild the in-memory PP list.
    Call this after new test programs are added to the server.
    """
    from modules.pp_inspect import refresh_pp_list
    try:
        folders = refresh_pp_list()
        return {
            "message": f"PP list refreshed: {len(folders)} folders found",
            "count":   len(folders),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── Inspection endpoints ─────────────────────────────────────────────────────

@app.get("/api/inspect/ap", response_model=InspectionResponse, tags=["Inspection"])
def inspect_ap(force: bool = False, _u: dict = Depends(auth.require("inspection.run"))):
    """
    Run Auftragsplan (AP) inspection.
    Use force=true to bypass the 2-minute cache.
    """
    cache = _cache["ap"]

    if not force and _cache_valid(cache):
        logger.info(f"AP: returning from cache (age {time.time()-cache['timestamp']:.0f}s)")
        return InspectionResponse(
            inspection_type  = "ap",
            timestamp        = _fmt(cache["timestamp"]),
            duration_seconds = 0.0,
            count            = len(cache["data"]),
            results          = cache["data"],
        )

    if cache["running"]:
        raise HTTPException(409, "AP inspection already running, try again shortly.")

    cache["running"] = True
    try:
        t0          = time.time()
        results, *_ = run_inspection_ap()
        duration    = time.time() - t0
        cache["data"]      = results
        cache["timestamp"] = time.time()
        return InspectionResponse(
            inspection_type  = "ap",
            timestamp        = _fmt(cache["timestamp"]),
            duration_seconds = round(duration, 1),
            count            = len(results),
            results          = results,
        )
    except Exception as e:
        logger.exception(f"AP inspection error: {e}")
        raise HTTPException(500, str(e))
    finally:
        cache["running"] = False


@app.get("/api/inspect/vb", response_model=InspectionResponse, tags=["Inspection"])
def inspect_vb(force: bool = False, _u: dict = Depends(auth.require("inspection.run"))):
    """
    Run Vorbereitung (VB) inspection.
    Use force=true to bypass the 2-minute cache.
    """
    cache = _cache["vb"]

    if not force and _cache_valid(cache):
        logger.info(f"VB: returning from cache (age {time.time()-cache['timestamp']:.0f}s)")
        return InspectionResponse(
            inspection_type  = "vb",
            timestamp        = _fmt(cache["timestamp"]),
            duration_seconds = 0.0,
            count            = len(cache["data"]),
            results          = cache["data"],
        )

    if cache["running"]:
        raise HTTPException(409, "VB inspection already running, try again shortly.")

    cache["running"] = True
    try:
        t0          = time.time()
        results, *_ = run_inspection_vb()
        duration    = time.time() - t0
        cache["data"]      = results
        cache["timestamp"] = time.time()
        return InspectionResponse(
            inspection_type  = "vb",
            timestamp        = _fmt(cache["timestamp"]),
            duration_seconds = round(duration, 1),
            count            = len(results),
            results          = results,
        )
    except Exception as e:
        logger.exception(f"VB inspection error: {e}")
        raise HTTPException(500, str(e))
    finally:
        cache["running"] = False


@app.post("/api/inspect/text", response_model=InspectionResponse, tags=["Inspection"])
def inspect_text(body: dict, _u: dict = Depends(auth.require("inspection.run"))):
    """
    Inspect manually entered BG or PP names.
    Body: { "text": "8009917.04\\n8009918_04BOT_ROT\\n..." }
    """
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Field 'text' is empty.")
    try:
        t0       = time.time()
        results  = run_inspection_text(text)
        duration = time.time() - t0
        return InspectionResponse(
            inspection_type  = "text",
            timestamp        = _fmt(time.time()),
            duration_seconds = round(duration, 1),
            count            = len(results),
            results          = results,
        )
    except Exception as e:
        logger.exception(f"Text inspection error: {e}")
        raise HTTPException(500, str(e))


# ─── Image endpoints ──────────────────────────────────────────────────────────

@app.get("/api/image/{pp_name}", tags=["Images"])
def get_image(pp_name: str, type: str = "hr"):
    """Return Haran Bild image for a PP. type: 'hr' or 'us'"""
    import os
    from fastapi.responses import FileResponse
    from modules.app_context import get_ctx

    if type not in ("hr", "us"):
        raise HTTPException(400, "type must be 'hr' or 'us'")

    pp_name_safe = os.path.basename(pp_name)
    ctx          = get_ctx()
    img_path     = os.path.join(ctx.picture_path, f"{pp_name_safe}.{type}.bmp")

    if not os.path.exists(img_path):
        raise HTTPException(404, f"Image not found: {pp_name_safe}.{type}.bmp")

    return FileResponse(img_path, media_type="image/bmp")


@app.get("/api/lp-image/", tags=["Images"])
def get_lp_image(path: str):
    """
    Return empty LP image by absolute path.
    path: absolute path returned by _find_lp_image()
    """
    import os
    from fastapi.responses import FileResponse
    from modules.app_context import get_ctx

    # Security: path must be inside empty_lp_path
    ctx            = get_ctx()
    path_resolved  = os.path.realpath(path)
    root_resolved  = os.path.realpath(ctx.empty_lp_path)

    if not path_resolved.startswith(root_resolved):
        raise HTTPException(403, "Access denied.")

    if not os.path.exists(path_resolved):
        raise HTTPException(404, f"LP image not found.")

    ext       = path_resolved.lower().rsplit(".", 1)[-1]
    media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "png": "image/png",  "bmp": "image/bmp"}
    media     = media_map.get(ext, "application/octet-stream")

    return FileResponse(path_resolved, media_type=media)


# ─── Search PM endpoints ──────────────────────────────────────────────────────

@app.get("/api/search/pm", tags=["Search PM"])
def search_pm(q: str = "", search_type: str = "contains", cli: str = "all", _u: dict = Depends(auth.require("search.pm"))):
    """Search Prüfmerkmale across all PP in CadRuest."""
    from modules.search_pm import search_pm as _search
    valid = ("exact", "contains", "starts_with", "ends_with")
    if search_type not in valid:
        raise HTTPException(400, f"search_type must be one of {valid}")
    return _search(q, search_type, cli)


@app.get("/api/search/cli-list", tags=["Search PM"])
def get_cli_list(_u: dict = Depends(auth.require("search.pm"))):
    """Return unique CLI values across all PP in CadRuest."""
    from modules.search_pm import get_cli_list as _cli
    return {"cli_list": _cli()}


# ─── Sync ─────────────────────────────────────────────────────────────────────

@app.get("/api/sync/status", tags=["Sync"])
def sync_status(_u: dict = Depends(auth.current_user)):
    """Return the last sync result for each sync type + any currently running syncs."""
    from db.sync_log import get_sync_status
    return get_sync_status()


@app.post("/api/sync/run", tags=["Sync"])
def sync_run(sync_type: str = "full", background_tasks: BackgroundTasks = None, _u: dict = Depends(auth.require("sync.run"))):
    """
    Trigger a sync run in the background.
    sync_type: 'full' | 'pp' | 'cli' | 'pm_type' | 'ap'
    """
    valid = ("full", "pp", "cli", "pm_type", "ap")
    if sync_type not in valid:
        raise HTTPException(400, f"sync_type must be one of {valid}")
    from db.manager import run_sync
    background_tasks.add_task(run_sync, sync_type)
    return {"message": f"Sync '{sync_type}' started in background"}


@app.get("/api/ap/refresh", tags=["Inspection"])
def ap_refresh_stream(_u: dict = Depends(auth.require_flex("ap.refresh"))):
    """
    Stream AP refresh progress via Server-Sent Events.
    Checks PP file mtimes vs DB, updates changed PP, regenerates errors.
    Final event: data: __DONE__
    """
    from fastapi.responses import StreamingResponse
    from db.refresh_ap import refresh_ap_with_progress
    return StreamingResponse(
        refresh_ap_with_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── DB-backed AP endpoint ────────────────────────────────────────────────────

@app.get("/api/ap", tags=["Inspection"])
def get_ap_from_db(_u: dict = Depends(auth.require("inspection.run"))):
    """
    Return the last AP inspection result built from DB.
    Populated by POST /api/sync/run?sync_type=ap.
    Returns 404 if no AP sync has been run yet.
    """
    if _ap_memory["results"] is None:
        raise HTTPException(404, "No AP data available — run AP sync first.")
    return {
        "inspection_type": "ap",
        "timestamp":       _fmt(_ap_memory["timestamp"]),
        "duration_seconds": round(_ap_memory["duration"] or 0, 1),
        "count":           len(_ap_memory["results"]),
        "results":         _ap_memory["results"],
    }


# ─── Cache management ─────────────────────────────────────────────────────────

@app.post("/api/cache/clear", tags=["Admin"])
def clear_inspection_cache(_u: dict = Depends(auth.require("users.manage"))):
    """Clear the in-memory inspection results cache (AP/VB)."""
    for key in _cache:
        _cache[key]["data"]      = None
        _cache[key]["timestamp"] = None
    return {"message": "Inspection cache cleared"}


@app.get("/api/cache/file-stats", tags=["Admin"])
def file_cache_stats(_u: dict = Depends(auth.require("users.manage"))):
    """Return file cache statistics (L1 memory + L2 disk)."""
    from modules.file_cache import stats
    return stats()


@app.post("/api/cache/file-flush", tags=["Admin"])
def file_cache_flush(_u: dict = Depends(auth.require("users.manage"))):
    """Force write of file cache from memory to disk."""
    from modules.file_cache import flush_to_disk
    flush_to_disk()
    return {"message": "File cache flushed to disk"}


@app.post("/api/cache/file-clear", tags=["Admin"])
def file_cache_clear(_u: dict = Depends(auth.require("users.manage"))):
    """Clear file cache completely (memory + disk)."""
    from modules.file_cache import clear as fc_clear
    fc_clear()
    return {"message": "File cache cleared"}


# ─── Auth endpoints ───────────────────────────────────────────────────────────

class LoginIn(BaseModel):
    username: str
    password: str

class ChangePwIn(BaseModel):
    old_password: str
    new_password: str

class UserCreateIn(BaseModel):
    username: str
    password: str
    role:     str

class UserUpdateIn(BaseModel):
    role:     Optional[str] = None
    password: Optional[str] = None

class RolePermsIn(BaseModel):
    permissions: list[str]


@app.post("/api/auth/login", tags=["Auth"])
def auth_login(body: LoginIn):
    user = auth.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth.make_token(user["username"], user["role"])
    return {"token": token, "user": user}


@app.get("/api/auth/me", tags=["Auth"])
def auth_me(user: dict = Depends(auth.current_user)):
    return {
        "username":       user["username"],
        "role":           user["role"],
        "permissions":    sorted(user["permissions"]),
        "must_change_pw": user["must_change_pw"],
    }


@app.post("/api/auth/change-password", tags=["Auth"])
def auth_change_password(body: ChangePwIn, user: dict = Depends(auth.current_user)):
    try:
        auth.change_password(user["username"], body.old_password, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Password changed"}


@app.get("/api/auth/users", tags=["Auth"])
def auth_list_users(_: dict = Depends(auth.require("users.manage"))):
    return {"users": auth.list_users()}


@app.post("/api/auth/users", tags=["Auth"])
def auth_create_user(body: UserCreateIn, _: dict = Depends(auth.require("users.manage"))):
    try:
        return auth.create_user(body.username, body.password, body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/auth/users/{username}", tags=["Auth"])
def auth_update_user(username: str, body: UserUpdateIn,
                     _: dict = Depends(auth.require("users.manage"))):
    try:
        return auth.update_user(username, role=body.role, password=body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/auth/users/{username}", tags=["Auth"])
def auth_delete_user(username: str, user: dict = Depends(auth.require("users.manage"))):
    try:
        auth.delete_user(username, acting_user=user["username"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": f"User '{username}' deleted"}


@app.get("/api/auth/permissions", tags=["Auth"])
def auth_permissions(_: dict = Depends(auth.require("users.manage"))):
    return {"registry": list(auth.PERMISSIONS), "roles": auth.role_permissions()}


@app.put("/api/auth/roles/{role}/permissions", tags=["Auth"])
def auth_set_role_permissions(role: str, body: RolePermsIn,
                              _: dict = Depends(auth.require("users.manage"))):
    try:
        return {"roles": auth.set_role_permissions(role, body.permissions)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.on_event("startup")
def on_startup():
    """Initialise DB schema and load error registry at server startup."""
    from db.manager import init_db
    init_db()
    # Clean up any sync_log rows left in 'running' state from a previous crash/restart
    from db.schema import get_conn
    from datetime import datetime, timezone
    conn = get_conn()
    stale = conn.execute("SELECT COUNT(*) FROM sync_log WHERE status = 'running'").fetchone()[0]
    if stale:
        with conn:
            conn.execute(
                "UPDATE sync_log SET status='error', finished_at=?, error_msg=? WHERE status='running'",
                (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "interrupted by server restart")
            )
        logger.info(f"Startup: cleared {stale} stale 'running' sync_log entries")
    from modules.errors import load_error_registry
    load_error_registry()
    # Auth: create the default super user on first run (idempotent)
    import auth
    auth.ensure_default_admin()

@app.on_event("shutdown")
def on_shutdown():
    """Flush file cache and close DB connection on server shutdown."""
    from modules.file_cache import flush_to_disk
    from db.schema import close_conn
    logger.info("Shutdown: flushing file cache to disk...")
    flush_to_disk()
    close_conn()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _cache_valid(cache: dict) -> bool:
    return (
        cache["data"]      is not None
        and cache["timestamp"] is not None
        and (time.time() - cache["timestamp"]) < CACHE_TTL
    )


def _fmt(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


if __name__ == "__main__":
    x = get_image("8006746_20TOP_DMC", "hr")