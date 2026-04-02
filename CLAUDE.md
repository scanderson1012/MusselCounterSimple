# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A desktop Electron app for automated juvenile freshwater mussel detection/classification in microscope images. Uses a Fast R-CNN (PyTorch) model to detect mussels, classify them as live/dead, and store results in SQLite. Researchers can adjust thresholds and manually correct detections.

## Commands

### Development

```bash
# Full setup
python3 -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
npm ci

# Start dev app (builds frontend first, then launches Electron)
npm start

# Build frontend only
npm run frontend:build

# Build backend executable only (requires requirements-build.txt installed)
npm run backend:build
```

### Packaging

```bash
# Windows portable ZIP
npm run make:desktop

# macOS DMG
npm run make:desktop -- --platform=darwin --arch=arm64
```

### Database (manual inspection/editing)

```bash
sqlite3 app_data/app.db
```

## Architecture

### Three-Layer Stack

```
React (frontend/dist/) ←── IPC/HTTP proxy ──→ Electron (electron/) ←──→ FastAPI (backend/)
                                                                              ↕
                                                                       SQLite (app_data/app.db)
```

**Electron main process** (`electron/main.js`) spawns the Python FastAPI backend on a dynamic port (8000–8039), then proxies all API calls from the renderer via IPC. The renderer never directly calls HTTP — it calls `window.desktopAPI` methods exposed by `electron/preload.js`, which sends IPC messages to the main process.

**Frontend** (`frontend/src/`) is a React SPA with hash-based routing (`/#/`, `/#/history`, `/#/run/:id`, `/#/run/:id/image/:imageId`). All state lives in `App.jsx`. Key hooks: `useRunActions.js` (API operations) and `useDetectionCanvas.js` (canvas bounding box rendering).

**Backend** (`backend/`) is FastAPI + Uvicorn. Entry point is `backend/main.py`. All routes are in `backend/api.py`. The core prediction workflow lives in `backend/predict_service.py` → `execute_predict_request()`.

### Key Backend Patterns

- **Singleton job**: Only one model execution can run at a time, enforced via global state in `backend/run_jobs.py`. Frontend polls `GET /predict/run-jobs/{run_job_id}` every 500ms.
- **Threshold is applied at count-time, not insert-time**: All raw detections are stored. Counts in `run_images` and `runs` tables are recalculated when the threshold changes, without re-running the model.
- **Image deduplication**: Images stored by SHA-256 hash. Same file uploaded twice reuses the stored copy.
- **Model caching**: Fast R-CNN cached by file path + mtime in `backend/model_execution.py`. Auto-detects GPU, falls back to CPU.
- **Soft deletes**: Detections use `is_deleted` flag; `is_edited` marks user corrections.

### Database Schema (key tables)

- `runs` — one row per inference run; stores model name, threshold, aggregate counts
- `images` — deduplicated image files (SHA-256)
- `run_images` — junction table linking runs ↔ images; stores per-image counts
- `detections` — bounding boxes with class (`live`/`dead`), confidence, edit/delete flags

### Build Pipeline

1. `npm run frontend:build` → Vite builds React to `frontend/dist/`
2. `npm run backend:build` → Node script calls PyInstaller (`backend/build_backend.py`) → `backend/dist/mussel-backend[.exe]`
3. `electron-forge make` → Packages everything into platform ZIP/DMG; backend binary included as `extraResource`

### Data Flow for a Prediction Run

1. User picks images + model → frontend calls `POST /predict`
2. Backend creates a `run` record, links images, spawns background thread
3. Background thread: load model → infer each image → insert detections → update counts
4. Frontend polls run-job status; on completion, renders image grid with overlaid boxes
5. User adjusts threshold → `POST /recalculate` → backend re-aggregates counts without re-inferring
