# AOI Tool v2.0 — Web Edition

Interfață web pentru inspecția programelor AOI Viscom SI (departament SMD).
Înlocuiește aplicația desktop legacy (Python/Tkinter). Rulează pe **Raspberry Pi**,
accesibilă din orice browser din rețeaua locală.

---

## Arhitectură

```
Browser (orice PC din rețea)
        ↕  HTTP
  Frontend React/Vite (port 3000)  ──proxy /api──►  Backend FastAPI (port 8000)
                                                          ↕
                                              SQLite (WAL) — sursa de adevăr
                                                          ↕
                                  Drive P:/ montat via CIFS (Cad_Ruest / Cli_Ruest)
                                  Intranet firmă (Auftragsplan)
```

- **SQLite (WAL mode)** este sursa unică de adevăr pentru `bg`, `pp`, `pp_pm`,
  `cli_global`, `cli_local`, `error`, `sync_log`.
- **AP (Auftragsplan)** nu se persistă — se ține în memorie și se reîmprospătează
  cu progres în timp real prin **SSE**.
- **Test mode vs live mode**: `live` citește de pe `P:/`; `test` folosește fixturi
  locale din `AOI_TEST_PATH`.

---

## 1. Instalare

### 1.1 Backend (Python 3.11+)

```bash
cd backend
python3 -m venv venv          # venv-ul NU se transferă între OS — se recreează nativ
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # editează căile pentru mediul tău
uvicorn main:app --host 0.0.0.0 --port 8000
```

Documentație API automată: `http://<IP>:8000/docs`

### 1.2 Frontend (Node 20+)

```bash
cd frontend
npm install
npm run dev                   # dezvoltare (port 3000, proxy /api → backend)
npm run build                 # producție → frontend/dist/
```

Recomandat pentru RPi: **build pe Windows**, apoi servește `dist/` de pe RPi.

### 1.3 Montare drive P:/ via CIFS (RPi)

```bash
sudo apt install cifs-utils
sudo mkdir -p /mnt/aoi
# /etc/fstab:
# //SERVER_IP/aoi  /mnt/aoi  cifs  username=USER,password=PASS,uid=1000,gid=1000,iocharset=utf8  0  0
sudo mount -a
```

---

## 2. Configurare

Toate căile sunt în `backend/config.py`, fiecare cu fallback la valoarea curentă,
deci pot fi suprascrise prin variabile de mediu fără a edita codul.
Vezi `backend/.env.example`.

| Variabilă            | Default (Windows)                         | Descriere                              |
|----------------------|-------------------------------------------|----------------------------------------|
| `AOI_DRIVE_ROOT`     | `P:/`                                      | Rădăcina serverului (CIFS pe RPi: `/mnt/aoi`) |
| `AOI_PROJECT_ROOT`   | `C:/Users/.../aoi-web/`                     | Locul DB-ului, `logs/`, `Docs/`        |
| `AOI_AP_URL`         | URL intranet Auftragsplan                  | Sursa planului de producție            |
| `AOI_EMPTY_LP_PATH`  | UNC intern Quins                           | Cale proiecte empty-LP (Windows)       |
| `AOI_KUNDE_CSV`      | `<project_root>/Docs/kunde_names.csv`      | CSV nume clienți                       |
| `AOI_TEST_PATH`      | `.../aoi-web/test`                          | Fixturi pentru test mode               |

Frontend (`frontend/.env`, opțional): `VITE_API_URL=http://<IP_BACKEND>:8000`.

> **Notă pentru repo public:** `config.py` conține valori interne implicite
> (hostname intranet, căi UNC). Dacă publici repo-ul în afara organizației,
> golește aceste default-uri și bazează-te exclusiv pe variabilele de mediu.

---

## 3. Sincronizare (DB)

Orchestrat de `db/manager.py` → `run_sync(type)`:

| Tip        | Rulează                                                        |
|------------|---------------------------------------------------------------|
| `bg`       | `sync_bg`                                                      |
| `pp`       | `sync_pp`                                                      |
| `cli`      | `sync_cli` (global + local)                                    |
| `pm_type`  | pasul de rezolvare `pm_type` (Option B, deferred)             |
| `ap`       | `sync_errors` (refresh AP + generare erori) — rulează și `pm_type` |
| `full`     | `cli` → `pp` → `pm_type`                                       |

Erorile sunt numerotate (1–79, din registrul Excel) și mapate pe culori:
critic → roșu, sugestie → portocaliu, info → galben.

---

## 4. Autostart cu systemd (RPi)

Un exemplu de unit este în `deploy/aoi-backend.service`:

```bash
sudo cp deploy/aoi-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aoi-backend
```

---

## 5. Structura proiectului

```
aoi-web/
├── backend/
│   ├── main.py              # FastAPI app, endpoints, AP în memorie
│   ├── config.py            # Căi centralizate (override prin env)
│   ├── models.py            # Modele Pydantic
│   ├── requirements.txt
│   ├── .env.example
│   ├── db/
│   │   ├── schema.py        # Schema SQLite (WAL) + migrări
│   │   ├── manager.py       # Orchestrare run_sync()
│   │   ├── sync_bg.py / sync_pp.py / sync_cli.py
│   │   ├── sync_pm_type.py  # Rezolvare pm_type (global/local)
│   │   ├── sync_errors.py   # Generare erori + build răspuns
│   │   ├── refresh_ap.py    # Refresh AP via SSE
│   │   └── sync_log.py
│   └── modules/
│       ├── intranet.py      # Scraping AP + citire pl.txt
│       ├── pp_inspect.py    # Detectare/inspecție PP (Cad/Cli_Ruest)
│       ├── search_pm.py     # Căutare PM (DB-backed)
│       ├── file_cache.py    # Cache L1 (memorie) + L2 (JSON disk)
│       ├── app_context.py   # Context + mod test/live
│       ├── errors.py
│       └── pipeline.py      # Pipeline vechi (folosit în test mode)
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── api.js
    │   ├── components/      # InspectionTable, PpSubRow, ImageViewer, SyncBar, ...
    │   └── constants/       # themes.js, translations.js
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## 6. Note operaționale

- **DB / cache nu se comit** — `.gitignore` exclude `*.db*`, `logs/`, cache JSON,
  `Docs/ideas.json`.
- **venv** trebuie recreat nativ pe RPi (cel de Windows nu se transferă).
- La pornire, intrările `sync_log` rămase „running” după un restart trebuie curățate.

---

## Licență

Vezi `LICENSE`. Implicit: proprietar / uz intern. Înlocuiește dacă publici sub
o licență open-source.
