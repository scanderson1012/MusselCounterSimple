# Mussel Counter
Download: https://github.com/natewill/MusselCounterSimple/releases/tag/v0.1.0

Made by the CMDA Capstone Fall 2025 and Spring 2026 teams for a CMDA capstone project under the Virginia Tech Department of Fish and Wildlife Conservation.

<img src="docs/sponsor-advisor.png" alt="Sponsor and Advisor" width="700" />

## Context

This project was built to remove a major research bottleneck for juvenile freshwater mussel studies.  
Before this tool, researchers had to manually inspect, classify, and count thousands of mussels in microscope images, which took extensive time and effort.  
Mussel Counter helps automate that process by running a computer vision model (Fast R-CNN) so researchers can spend less time on manual counting and more time on conservation and analysis work.

Desktop app built with Electron, a React frontend, a FastAPI backend, and a SQL (SQLite) database.

### 1) Petri Dish Context

One dish can contain a huge number of juvenile mussels and debris, and counting them one-by-one takes a lot of time. This tool helps cut down that manual work and makes counting faster and more consistent.

<img src="docs/petri-dish.png" alt="Petri Dish Context" width="480" />

### 2) Example Model Input

This is the kind of microscope image the model receives. Instead of manually reviewing every image in a batch, the app processes them automatically and gives back results you can review quickly.

<img src="docs/model-input-1455.jpg" alt="Example Model Input" width="480" />

### 3) Example Model Output

This is the prediction output: each detected mussel gets a class label (`live` or `dead`) and a confidence score. That turns raw images into usable counts while still letting you inspect every prediction.

<img src="docs/model-output-1455.png" alt="Example Model Output" width="480" />

## App Screenshots

### Home Page

This is the launch point for a run. You can add images, pick the model, set the threshold, and start processing in a few clicks, so the workflow stays practical for day-to-day lab use.

<img src="docs/homepage.png" alt="Home Page" width="520" />

### After A Run

After the model finishes, the app summarizes outcomes across the run, including total images and live/dead counts, so users can move from raw image sets to clear results quickly.

<img src="docs/after-run.png" alt="After A Run" width="520" />

### Bounding Boxes After Run

This view overlays predicted bounding boxes directly on the image, which makes the model behavior transparent and easy to audit instead of treating predictions like a black box.

<img src="docs/bounding-boxes-after-run.png" alt="Bounding Boxes After Run" width="520" />

### Image Edit

This edit view keeps a human in the loop: you can correct labels or delete incorrect detections, and those edits persist in the database for reliable historical tracking.

<img src="docs/image-edit.png" alt="Image Edit" width="520" />

## Prerequisites

- Node.js 20+
- Python 3.11+

## Installer Downloads

Download the installer package that matches your operating system from the latest GitHub release.

- Windows 10/11 ZIP: `https://github.com/scanderson1012/MusselCounterSimple/releases/download/v0.1.0/mussel-counter-simple-win32-x64-0.1.0.zip`
- macOS DMG: add your release asset link here after upload

The desktop installers include:

- the bundled baseline model `baseline_fasterrcnn_model`
- the bundled baseline training dataset
- the bundled baseline test dataset

Current limitation:

- macOS currently runs on CPU only. Optional GPU runtime support is implemented for Windows only.

## Build From This Repository

If you are building the app yourself instead of downloading a release asset, do these steps first:

1. Install Python 3.
2. Install Node.js 20 or newer.
3. Download or clone this repository to your computer.
4. Open a terminal in the repository root folder.

The repository root folder is the folder that contains:

- `package.json`
- `backend`
- `frontend`
- `electron`

All build commands in this README should be run from that repository root folder.

### Install Python And Node.js First

If you have never used Python before, do this before running any commands below.

#### Windows

1. Install Python 3 from: `https://www.python.org/downloads/windows/`
2. During the Python installer, make sure you check the box:
   `Add Python to PATH`
3. Finish the Python installation.
4. Install Node.js 20 or newer from: `https://nodejs.org/`
5. Open a new PowerShell window after both installs finish.

#### macOS

1. Install Python 3 from: `https://www.python.org/downloads/macos/`
2. Install Node.js 20 or newer from: `https://nodejs.org/`
3. Open a new Terminal window after both installs finish.

### Clone The Repository

Use one of these two options:

#### Option 1: Clone with Git

If you already have Git installed, run:

```bash
git clone https://github.com/scanderson1012/MusselCounterSimple.git
cd MusselCounterSimple
```

#### Option 2: Download the ZIP

1. Open: `https://github.com/scanderson1012/MusselCounterSimple`
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Extract the ZIP.
5. Open a terminal inside the extracted `MusselCounterSimple` folder.

## Run Locally (Development on macOS/Linux)

### Download Everything

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
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
py -3 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
npm ci
```

### Start The App For Testing

```powershell
npm start
```

## Build Installer Packages

### Build macOS `.dmg` (on macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run make:desktop:mac -- --arch=arm64
find out/make -name "*.dmg"
```

### Build Windows `.zip` (Portable, on Windows)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run make:desktop:win
```

If PowerShell blocks `npm` with an `npm.ps1 cannot be loaded because running scripts is disabled on this system` error, use `npm.cmd` instead:

```powershell
& "C:\Program Files\nodejs\npm.cmd" ci
& "C:\Program Files\nodejs\npm.cmd" run make:desktop:win
```

Windows ZIP output will be under:

```text
out\make\zip\win32\...
```

To use it, extract the ZIP on Windows and run `mussel-counter-simple.exe` from the extracted folder.

To create a desktop shortcut on Windows, right-click `mussel-counter-simple.exe` and choose `Send to` -> `Desktop (create shortcut)`. Keep the full extracted app folder together and do not move only the `.exe` by itself.

### Optional Windows GPU Runtime Build

The default Windows installer is CPU-first. To include the optional NVIDIA GPU runtime in the Windows build, prepare a second build environment with the GPU requirements and build the GPU backend before running the Windows packaging command.

Detailed commands are in [docs/INSTALLER_BUILD.md](docs/INSTALLER_BUILD.md).

## How To Use The App

### Add A Model

To add a model in the app, click `Add Model` in the top-right, then select your `.pt` or `.pth` file.

Current support is limited to PyTorch RCNN models.

On first launch, the app already includes the bundled `baseline_fasterrcnn_model` together with its matching training and test datasets.

### Run Page (Home Page)

The home page is the `Run` page, where you run the model.

1. Click `Add Images` to select the images you want to process.
2. Choose the model you want to run.
3. Click `Start Run` to run the model.
4. After the model finishes, adjust the threshold slider if needed and click `Recalculate`.

### Threshold Slider

Each RCNN detection (bounding box) has a confidence score for its predicted class (`live` or `dead`).

- Default behavior is a threshold of `0.5` (50% confidence).
- Increasing the threshold (for example, `0.9`) keeps only high-confidence detections.
- Lowering the threshold (for example, `0.2` or `0.3`) includes lower-confidence detections.

The threshold controls what is included in:

- live/dead mussel counts
- displayed image bounding boxes

For example, at `0.9`, detections below 90% confidence are excluded from counts and hidden from the image view.

### Editing Detections

After a run finishes, click an image to review and edit detections.

- You can click an existing bounding box and change its class (`live` <-> `dead`).
- You can delete an existing bounding box.
- You currently cannot add new bounding boxes (not supported yet).

Edits are persisted in the SQL database, so they remain saved over time.

### View History Page

The `View History` page shows previous runs (prediction history).

For each run, the app stores details in SQL, including:

- images included in the run
- live/dead counts
- model used
- threshold and run configuration

You can review past runs and adjust threshold values for those runs as needed.

## Edit The Database (Terminal)

The database uses SQL with SQLite.

Quick terminal usage:

```bash
# while in /MusselCounterSimple
sqlite3 app_data/app.db
```

Inside the SQLite prompt:

```sql
.tables
SELECT * FROM runs LIMIT 10;
SELECT * FROM run_images LIMIT 10;
SELECT * FROM detections LIMIT 10;
```

Example edit:

```sql
UPDATE runs SET threshold_score = 0.6 WHERE id = 1;
```

Exit SQLite:

```sql
.quit
```
