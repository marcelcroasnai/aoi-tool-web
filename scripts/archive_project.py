#!/usr/bin/env python3
"""
AOI Tool - Archive helper

Arhiveaza doar fisierele relevante pentru colaborare (cod sursa, config,
fara dependinte instalate, fara cache-uri, fara fisiere binare mari).

Ruleaza din radacina proiectului (folderul care contine `backend/` si `frontend/`):
    python archive_project.py

Output: aoi-tool-web_YYYYMMDD_HHMMSS.zip in acelasi folder.
"""

import os
import zipfile
from datetime import datetime
from pathlib import Path

# ─── Configurare ──────────────────────────────────────────────────────────────

# Foldere care se exclud complet (nume de folder, oriunde apar in arbore)
EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__", ".git",
    "dist", "build", ".pytest_cache", ".mypy_cache",
    "uploads", "outputs",  # foldere de date, nu de cod
}

# Extensii de fisiere care se exclud (cache-uri, binare, log-uri)
EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".db", ".db-journal", ".db-wal", ".db-shm",
    ".log", ".lock",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".ico",  # imagini generate/test
    ".zip", ".tar", ".gz",
}

# Fisiere specifice care se exclud (dupa nume exact)
EXCLUDE_FILENAMES = {
    "package-lock.json", "yarn.lock",
    "aoi_tool.db", "file_cache.json",
    ".DS_Store", "Thumbs.db",
}

# Extensii incluse explicit (cod sursa + config relevante)
INCLUDE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".md", ".txt",
    ".html", ".css",
    ".toml", ".cfg", ".ini", ".env.example",
    ".yml", ".yaml",
}

# Foldere radacina de cautat (relativ la locul de unde se ruleaza scriptul)
SEARCH_ROOTS = ["backend", "frontend"]

# Fisiere individuale din radacina proiectului, daca exista
ROOT_FILES = [
    "README.md", "requirements.txt", ".gitignore",
]


# ─── Logica ───────────────────────────────────────────────────────────────────

def should_include(path: Path) -> bool:
    """Decide daca un fisier trebuie inclus in arhiva."""
    if path.name in EXCLUDE_FILENAMES:
        return False
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return False
    if path.suffix.lower() not in INCLUDE_EXTENSIONS:
        return False
    return True


def should_skip_dir(dirname: str) -> bool:
    return dirname in EXCLUDE_DIRS or dirname.startswith(".")


def collect_files(project_root: Path) -> list[Path]:
    """Colecteaza toate fisierele relevante din backend/ si frontend/."""
    collected: list[Path] = []

    for root_name in SEARCH_ROOTS:
        root_path = project_root / root_name
        if not root_path.is_dir():
            print(f"  (folder '{root_name}' nu exista, se omite)")
            continue

        for dirpath, dirnames, filenames in os.walk(root_path):
            # filtreaza folderele excluse in-place, ca os.walk sa nu intre in ele
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            for filename in filenames:
                file_path = Path(dirpath) / filename
                if should_include(file_path):
                    collected.append(file_path)

    # fisiere individuale din radacina
    for fname in ROOT_FILES:
        fpath = project_root / fname
        if fpath.is_file():
            collected.append(fpath)

    return collected


def make_archive(project_root: Path) -> Path:
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"aoi-tool-web_{timestamp}.zip"
    archive_path = project_root / archive_name

    files = collect_files(project_root)

    if not files:
        print("Nu s-au gasit fisiere relevante. Verifica ca scriptul ruleaza din radacina proiectului.")
        return archive_path

    print(f"Se arhiveaza {len(files)} fisiere...")

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            arcname = file_path.relative_to(project_root)
            zf.write(file_path, arcname)
            print(f"  + {arcname}")

    size_kb = archive_path.stat().st_size / 1024
    print(f"\nArhiva creata: {archive_path}  ({size_kb:.1f} KB, {len(files)} fisiere)")
    return archive_path


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    print(f"Radacina proiect: {project_root}\n")
    make_archive(project_root)
