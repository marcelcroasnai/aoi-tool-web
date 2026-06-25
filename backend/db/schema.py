"""
AOI Tool - DB Schema
Manages the SQLite connection and table definitions.

Single connection per process (thread-safe via check_same_thread=False +
WAL mode). All other db modules import get_conn() from here.

DB file location: PROJECT_ROOT/aoi_tool.db
"""

import os
import sqlite3
import logging

import config as cfg

logger = logging.getLogger(__name__)

_DB_PATH = cfg.DB_PATH
_conn: sqlite3.Connection | None = None


# ─── Connection ───────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    """Return the shared SQLite connection, initialising it on first call."""
    global _conn
    if _conn is None:
        _conn = _init_connection(_DB_PATH)
    return _conn


def _init_connection(path: str) -> sqlite3.Connection:
    logger.info(f"DB: opening connection → {path}")
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # access columns by name
    conn.execute("PRAGMA journal_mode=WAL") # safe concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    logger.info("DB: connection ready (WAL mode, foreign keys ON)")
    return conn


def close_conn() -> None:
    """Close the shared connection — call on application shutdown."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
        logger.info("DB: connection closed")


# ─── Schema ───────────────────────────────────────────────────────────────────

_DDL_STATEMENTS = [

    # ── bg ────────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS bg (
        bg_name      TEXT PRIMARY KEY,
        active       INTEGER DEFAULT 1,
        kunde        TEXT,
        lp_nr        TEXT,
        medi         INTEGER DEFAULT 0,
        dmc          INTEGER DEFAULT 0,
        comp_bot     TEXT,
        comp_top     TEXT,
        pp_list      TEXT,
        project_name TEXT,
        mtime_pl     REAL,
        synced_at    TEXT
    )
    """,

    # ── pp ────────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS pp (
        pp_name       TEXT PRIMARY KEY,
        folder        TEXT,
        locked        INTEGER DEFAULT 0,
        cli           TEXT,
        medi          INTEGER DEFAULT 0,
        dmc           INTEGER DEFAULT 0,
        nutzen_in_lp  INTEGER,
        hinweis       TEXT,
        oldest_mod    TEXT,
        comp          TEXT,
        mtime_bbs     REAL,
        mtime_cad     REAL,
        mtime_def     REAL,
        mtime_desc    REAL,
        mtime_mod     REAL,
        mtime_par     REAL,
        mtime_pre     REAL,
        mtime_ref     REAL,
        mtime_size    REAL,
        mtime_hinweis REAL,
        synced_at     TEXT
    )
    """,

    # ── pp_pm ─────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS pp_pm (
        pp_name    TEXT NOT NULL REFERENCES pp(pp_name) ON DELETE CASCADE,
        pm_name    TEXT NOT NULL,
        ihl_nr     TEXT NOT NULL DEFAULT '',
        pm_type    TEXT CHECK(pm_type IN ('global', 'local')),
        refs_count INTEGER DEFAULT 0,
        PRIMARY KEY (pp_name, pm_name, ihl_nr)
    )
    """,

    # ── cli_global ────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS cli_global (
        pm_name               TEXT NOT NULL,
        cli                   TEXT NOT NULL,
        active_macros         TEXT,
        mtime_cle             REAL,
        mtime_mac             REAL,
        last_modified_mac_name TEXT,
        synced_at             TEXT,
        PRIMARY KEY (pm_name, cli)
    )
    """,

    # ── cli_local ─────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS cli_local (
        pm_name               TEXT NOT NULL,
        pp_name               TEXT NOT NULL,
        cli                   TEXT NOT NULL,
        active_macros         TEXT,
        mtime_cle             REAL,
        mtime_mac             REAL,
        last_modified_mac_name TEXT,
        synced_at             TEXT,
        PRIMARY KEY (pm_name, pp_name)
    )
    """,

    # ── error ─────────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS error (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        bg_name     TEXT,
        pp_name     TEXT,
        error_code  TEXT,
        error_type  TEXT,
        error_text  TEXT,
        open_file   TEXT,
        created_at  TEXT
    )
    """,

    # ── sync_log ──────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS sync_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sync_type   TEXT CHECK(sync_type IN ('pp', 'cli', 'ap', 'pm_type')),
        status      TEXT CHECK(status IN ('running', 'done', 'error')),
        total       INTEGER DEFAULT 0,
        changed     INTEGER DEFAULT 0,
        new         INTEGER DEFAULT 0,
        deleted     INTEGER DEFAULT 0,
        duration_s  REAL,
        error_msg   TEXT,
        started_at  TEXT,
        finished_at TEXT
    )
    """,

    # ── indexes ───────────────────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_pp_pm_pp     ON pp_pm(pp_name)",
    "CREATE INDEX IF NOT EXISTS idx_pp_pm_pm     ON pp_pm(pm_name)",
    "CREATE INDEX IF NOT EXISTS idx_cli_global   ON cli_global(pm_name)",
    "CREATE INDEX IF NOT EXISTS idx_cli_local_pp ON cli_local(pp_name)",
    "CREATE INDEX IF NOT EXISTS idx_error_bg     ON error(bg_name)",
    "CREATE INDEX IF NOT EXISTS idx_error_pp     ON error(pp_name)",
    "CREATE INDEX IF NOT EXISTS idx_sync_log     ON sync_log(sync_type, started_at)",
]


def init_schema() -> None:
    """
    Create all tables and indexes if they do not yet exist.
    Safe to call on every startup — uses CREATE IF NOT EXISTS throughout.
    """
    conn = get_conn()
    logger.info("DB: initialising schema …")
    try:
        with conn:
            _migrate_cli_local(conn)
            _migrate_pp_pm(conn)
            _migrate_bg_active(conn)
            _migrate_pp_folder(conn)
            for stmt in _DDL_STATEMENTS:
                conn.execute(stmt)
        logger.info("DB: schema ready")
    except Exception as e:
        logger.exception(f"DB: schema init failed: {e}")
        raise


def _migrate_cli_local(conn: sqlite3.Connection) -> None:
    """Drop cli_local if it still has the old FK on pp_name."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='cli_local'"
    ).fetchone()
    if row and "REFERENCES" in (row[0] or ""):
        logger.info("DB: migrating cli_local — removing FK constraint")
        conn.execute("DROP TABLE cli_local")


def _migrate_bg_active(conn: sqlite3.Connection) -> None:
    """Add active column to bg if missing."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bg)").fetchall()]
    if cols and "active" not in cols:
        logger.info("DB: migrating bg — adding active column")
        conn.execute("ALTER TABLE bg ADD COLUMN active INTEGER DEFAULT 1")


def _migrate_pp_folder(conn: sqlite3.Connection) -> None:
    """Add folder column to pp (CadRuest display name) and backfill it."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(pp)").fetchall()]
    if cols and "folder" not in cols:
        logger.info("DB: migrating pp — adding folder column")
        conn.execute("ALTER TABLE pp ADD COLUMN folder TEXT")
        conn.execute("UPDATE pp SET folder = pp_name WHERE folder IS NULL")


def _migrate_pp_pm(conn: sqlite3.Connection) -> None:
    """
    Recreate pp_pm with (pp_name, pm_name, ihl_nr) primary key
    and refs_count column if the old schema is detected.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='pp_pm'"
    ).fetchone()
    if row:
        sql = row[0] or ""
        needs_migration = (
            "ihl_nr" not in sql
            or "refs_count" not in sql
            or "PRIMARY KEY (pp_name, pm_name)" in sql  # old PK without ihl_nr
        )
        if needs_migration:
            logger.info("DB: migrating pp_pm — recreating with new schema")
            conn.execute("DROP TABLE pp_pm")



def get_db_path() -> str:
    return _DB_PATH
