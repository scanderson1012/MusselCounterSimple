# Mussel Counter Simple

Desktop app for running mussel detection with an Electron frontend and Python backend.

## Prerequisites

- Node.js 20+
- Python 3.11+

## Run Locally (Development on macOS/Linux)

### Download Everything

```bash
# while in /MusselCounterSimple
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
```

### Start The App For Testing

```bash
npm start
```

## Run Locally (Development on Windows)

### Download Everything

```powershell
# while in /MusselCounterSimple
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
npm ci
```

### Start The App For Testing

```powershell
npm start
```

## Build macOS `.dmg` (on macOS)

```bash
# while in /MusselCounterSimple
source .venv/bin/activate
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run make:desktop -- --platform=darwin --arch=arm64
find out/make -name "*.dmg"
```

## Build Windows `.exe` (on Windows)

```powershell
# while in /MusselCounterSimple
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
