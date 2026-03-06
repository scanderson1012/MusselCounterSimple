# Mussel Counter
Download: https://github.com/natewill/MusselCounterSimple/releases/tag/v0.1.0

Made by Team Mussel Memory: Nate Williams, Austin Ashley, Fernando Gomez, and Siddharth Rakshit for a CMDA capstone project under the Virginia Tech Department of Fish and Wildlife Conservation.

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

## How To Use The App

### Add A Model

To add a model in the app, click `Add Model` in the top-right, then select your `.pt` or `.pth` file.

Current support is limited to PyTorch RCNN models.

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
