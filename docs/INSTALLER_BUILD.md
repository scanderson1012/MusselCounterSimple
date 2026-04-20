# Installer Build Guide

Start by installing Python 3 and Node.js 20+, then download or clone this repository, then open a terminal in the repository root folder before running any commands.

The repository root folder is the folder that contains:

- `package.json`
- `backend`
- `frontend`
- `electron`

## Install Python And Node.js First

If you have never used Python before, do this before running any build commands.

### Windows

1. Install Python 3 from: `https://www.python.org/downloads/windows/`
2. During the Python installer, check:
   `Add Python to PATH`
3. Finish the Python installation.
4. Install Node.js 20 or newer from: `https://nodejs.org/`
5. Open a new PowerShell window after installation.

### macOS

1. Install Python 3 from: `https://www.python.org/downloads/macos/`
2. Install Node.js 20 or newer from: `https://nodejs.org/`
3. Open a new Terminal window after installation.

## Clone Or Download The Repository

### Option 1: Clone with Git

```bash
git clone https://github.com/scanderson1012/MusselCounterSimple.git
cd MusselCounterSimple
```

### Option 2: Download the ZIP

1. Open: `https://github.com/scanderson1012/MusselCounterSimple`
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Extract the ZIP.
5. Open a terminal inside the extracted `MusselCounterSimple` folder.

This project ships as:

- Windows 10/11 portable ZIP
- macOS DMG

The packaged app always includes:

- the bundled baseline model `baseline_fasterrcnn_model`
- the bundled baseline training dataset
- the bundled baseline test dataset

## Windows 10/11 CPU-First Build

Build this on Windows.

```powershell
py -3 -m venv .venv-build-cpu
.\.venv-build-cpu\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run backend:build:cpu
npm run make:desktop:win
```

If PowerShell blocks `npm` with an `npm.ps1 cannot be loaded because running scripts is disabled on this system` error, use `npm.cmd` instead:

```powershell
& "C:\Program Files\nodejs\npm.cmd" ci
& "C:\Program Files\nodejs\npm.cmd" run backend:build:cpu
& "C:\Program Files\nodejs\npm.cmd" run make:desktop:win
```

Output:

```text
out\make\zip\win32\...
```

## Windows 10/11 Build With Optional GPU Runtime

Build this on Windows. The packaged app still starts on CPU by default, but it also includes a second optional GPU backend that can be activated from the first-launch GPU prompt or later from Settings.

You do not have to build the CPU and GPU versions at the same time. For example, you can:

1. build and package a CPU-only Windows version first,
2. come back later and build the GPU backend,
3. run the Windows packaging command again.

When you re-run the packaging command after `backend/dist_gpu/` exists, the new Windows package will include both the default CPU backend and the optional GPU backend.

### 1. Build the CPU backend

```powershell
py -3 -m venv .venv-build-cpu
.\.venv-build-cpu\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run backend:build:cpu
deactivate
```

### 2. Build the Windows GPU backend

```powershell
py -3 -m venv .venv-build-gpu
.\.venv-build-gpu\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-gpu-win.txt -r requirements-build.txt
npm run backend:build:gpu:win
deactivate
```

### 3. Build the Windows package

```powershell
.\.venv-build-cpu\Scripts\activate
npm run make:desktop:win
```

When `backend/dist_gpu/` exists, Electron Forge automatically bundles the optional Windows GPU backend into the app resources.

## macOS CPU-Only Build

Build this on macOS.

```bash
python3 -m venv .venv-build-mac
source .venv-build-mac/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run backend:build:cpu
npm run make:desktop:mac -- --arch=arm64
```

Output:

```text
out/make/.../*.dmg
```

Current limitation:

- macOS currently uses the CPU backend only.

## Test The CPU Installer Flow

Use a clean machine or remove old user data first.

### Windows

```powershell
Remove-Item -Recurse -Force "$env:APPDATA\mussel-counter-simple" -ErrorAction SilentlyContinue
```

### macOS

```bash
rm -rf "$HOME/Library/Application Support/mussel-counter-simple"
```

Then verify:

1. The app opens without Python installed.
2. The bundled baseline model appears on first launch.
3. The baseline training and test datasets are available to the bundled baseline model.
4. The app runs on CPU normally.

## Test The Optional Windows GPU Upgrade Flow

Use a Windows machine with a compatible NVIDIA GPU and a Windows package that includes `backend/dist_gpu`.

1. Launch the packaged app.
2. Confirm the first-launch GPU prompt appears.
3. Click `Enable GPU Runtime`.
4. Open Settings and confirm:
   - `Active runtime` shows `GPU-enabled backend`
   - `Active device` shows `GPU` when the CUDA runtime is available
5. Run:
   - inference
   - test evaluation
   - fine-tuning
6. Switch `Compute Mode` to `CPU only` and confirm the app still runs correctly.

## Release Asset Links For README

After uploading release assets, add links in `README.md` using this format:

- Windows ZIP:
  `https://github.com/<owner>/<repo>/releases/download/<tag>/<windows-asset-name>.zip`
- macOS DMG:
  `https://github.com/<owner>/<repo>/releases/download/<tag>/<macos-asset-name>.dmg`

If you also upload a macOS ZIP, you can add:

- macOS ZIP:
  `https://github.com/<owner>/<repo>/releases/download/<tag>/<macos-asset-name>.zip`
