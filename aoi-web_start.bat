@echo off
chcp 65001 >nul
title AOI Tool Starter

echo.
echo  ╔══════════════════════════════════════╗
echo  ║        AOI Tool v2.0 - Start         ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── Konfiguration ─────────────────────────────────────────────
:: Das Projektverzeichnis ist der Ordner, in dem diese Datei liegt.
:: Die Datei muss im Projekt-Hauptordner liegen (neben "backend" und "frontend").
set "PROJECT_DIR=%~dp0"
:: Abschließenden Backslash entfernen
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: Backend-Port
set BACKEND_PORT=57842
:: ──────────────────────────────────────────────────────────────

:: Prüfen, ob die Projektordner vorhanden sind
if not exist "%PROJECT_DIR%\backend" (
    echo  [FEHLER] Ordner "backend" wurde nicht gefunden.
    echo  Diese Datei muss im Projekt-Hauptordner liegen.
    echo.
    pause
    exit /b 1
)
if not exist "%PROJECT_DIR%\frontend" (
    echo  [FEHLER] Ordner "frontend" wurde nicht gefunden.
    echo  Diese Datei muss im Projekt-Hauptordner liegen.
    echo.
    pause
    exit /b 1
)

echo  [1/2] Backend wird gestartet ^(Port %BACKEND_PORT%^)...
start "AOI Backend" /d "%PROJECT_DIR%\backend" cmd /k "venv\Scripts\activate && uvicorn main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"

:: 3 Sekunden warten, bis das Backend gestartet ist
timeout /t 3 /nobreak >nul

echo  [2/2] Frontend wird gestartet ^(Port 3000^)...
start "AOI Frontend" /d "%PROJECT_DIR%\frontend" cmd /k "npm run dev"

:: 4 Sekunden warten, bis das Frontend gestartet ist
timeout /t 4 /nobreak >nul

echo.
echo  ✓ AOI Tool gestartet!
echo  Browser öffnen unter: http://localhost:3000
echo.

:: Browser automatisch öffnen
start http://localhost:3000

echo  Beliebige Taste drücken, um dieses Fenster zu schließen...
pause >nul
