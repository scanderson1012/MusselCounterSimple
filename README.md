# Mussel Counter Simple

Desktop app for running mussel detection with an Electron frontend and Python backend.

## Prerequisites

- Node.js 20+
- Python 3.11+

## Run Locally (Development)

```bash
cd /Users/natewilliams/Desktop/VT/capstone/MusselCounterSimple
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
npm start
```

## Build macOS `.dmg` (on macOS)

```bash
cd /Users/natewilliams/Desktop/VT/capstone/MusselCounterSimple
source .venv/bin/activate
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run make:desktop -- --platform=darwin --arch=arm64
find out/make -name "*.dmg"
```

## Build Windows `.exe` (on Windows)

```powershell
cd C:\path\to\MusselCounterSimple
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run make:desktop
```

Windows installer output will be under:

```text
out\make\squirrel.windows\...
```

## Build Windows `.exe` from GitHub Actions

This repo includes a workflow at:

```text
.github/workflows/build-windows.yml
```

Run it from **GitHub > Actions > Build Windows Desktop > Run workflow**.

The workflow uploads:
- `Setup.exe`
- `.nupkg`
- `RELEASES`

as an artifact named `windows-build-artifacts`.

