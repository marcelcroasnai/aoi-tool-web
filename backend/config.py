"""
AOI Tool - Centralized configuration
Toate căile și URL-urile sunt definite aici, nu hardcodate în logică.
Pe RPi, drive-ul P:/ va fi montat via CIFS, ex: /mnt/aoi
"""

import os

# ─── Mount point ────────────────────────────────────────────────────────────────
# Pe Windows (original): P:/
# Pe RPi cu CIFS mount:  /mnt/aoi  (sau ce ai configurat în /etc/fstab)
# Detectare automată: dacă rulăm pe Windows, folosim P:/ direct
import platform

# ──────────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────────
EDV_SERVER = os.environ.get("AOI_DRIVE_ROOT", "P:/")
AOI_SERVER_PATH = os.path.join(EDV_SERVER, "aoi")

# ──────────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────────

# ─── Viscom SI paths ─────────────────────────────────────────────────────────────
CAD_RUEST_PATH        = os.path.join(AOI_SERVER_PATH, "Viscom_XM/Project/Si/Data/Cad_Ruest")
CLI_RUEST_PATH        = os.path.join(AOI_SERVER_PATH, "Viscom_XM/Project/Si/Data/Cli_Ruest")
VORBEREITUNG_PATH     = os.path.join(AOI_SERVER_PATH, "Angefangene Programme/Vorbereitung_AOI_XM")
PICTURE_PATH          = os.path.join(AOI_SERVER_PATH, "PICTURE")

# ─── EDV paths ─────────────────────────────────────────────────────────────
BG_INFO_PATH          = os.path.join(EDV_SERVER, "bginfo/8nr")
EMPTY_LP_PATH         = os.environ.get("AOI_EMPTY_LP_PATH", r"\\HAMBURG\Quins_QSWE\QUINSEASY\Projekte")


# ─── Project paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT          = os.environ.get("AOI_PROJECT_ROOT", "C:/Users/mcro/Documents/aoi-web/")

DB_PATH               = os.path.join(PROJECT_ROOT, "aoi_tool.db")
LOG_PATH              = os.path.join(PROJECT_ROOT, "logs")
ERRORS_XLS_FILE       = os.path.join(PROJECT_ROOT, "Docs/Errors.xlsx")
IDEAS_FILE            = os.path.join(PROJECT_ROOT, "Docs/ideas.json")
KUNDE_CSV_FILE        = os.environ.get("AOI_KUNDE_CSV",
                            os.path.join(PROJECT_ROOT, "Docs/kunde_names.csv"))


# ─── Auth ─────────────────────────────────────────────────────────────────────
# Credentials are stored hashed in a JSON file, separate from the inspection DB
# (which is truncated/rebuilt on every sync). Both files must be gitignored.
AUTH_FILE        = os.environ.get("AOI_AUTH_FILE",
                            os.path.join(PROJECT_ROOT, "auth_users.json"))
# Persistent JWT signing secret. Prefer the AOI_JWT_SECRET env var; if unset,
# auth.py reads/creates this file so tokens survive server restarts.
JWT_SECRET_FILE  = os.environ.get("AOI_JWT_SECRET_FILE",
                            os.path.join(PROJECT_ROOT, ".jwt_secret"))
JWT_TTL_SECONDS  = int(os.environ.get("AOI_JWT_TTL", str(8 * 3600)))   # 8h


# ─── Intranet ─────────────────────────────────────────────────────────────────────
AP_URL = os.environ.get(
    "AOI_AP_URL",
    "http://intranet.world.se.com/fertigung/info/auftragsplan.cgi?iieborder=1&mode=SMD"
)


# ─── Test paths ─────────────────────────────────────────────────────────────
TEST_PATH = os.environ.get("AOI_TEST_PATH", r"C:\Users\mcro\Documents\aoi-web\test")

# Paths
TEST_BG_INFO_PATH =     os.path.join(TEST_PATH, "bg_info")
TEST_CAD_RUEST_PATH =   os.path.join(TEST_PATH, "Cad_Ruest")
TEST_CLI_RUEST_PATH =   os.path.join(TEST_PATH, "Cli_Ruest")
TEST_PICTURE_PATH =     os.path.join(TEST_PATH, "PICTURE")
TEST_EMPTY_LP_PATH =    os.path.join(TEST_PATH, "EMPTY_LP")

TEST_VORBEREITUNG_PATH = VORBEREITUNG_PATH
TEST_IDEAS_FILE = IDEAS_FILE

# Files
TEST_AP_HTML_FILE = os.path.join(TEST_PATH, "ap.html")
TEST_KUNDE_CSV_FILE = KUNDE_CSV_FILE




# ─── Error severity colors ────────────────────────────────────────────────────────
ERROR_COLORS = {
    "red":          "#ef4444",   # roșu - eroare critică
    "orange":       "#f97316",   # portocaliu - sugestie
    "yellow":       "#eab308",   # galben - info
    "green":        "#22c55e",   # verde - ok
}
