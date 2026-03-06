# Mussel Counter

## Why We Made This

This project was built to remove a major research bottleneck for juvenile freshwater mussel studies.  
Before this tool, researchers had to manually inspect, classify, and count thousands of mussels in microscope images, which took extensive time and effort.  
Mussel Counter helps automate that process by running a computer vision model (Fast R-CNN) so researchers can spend less time on manual counting and more time on conservation and analysis work.

Desktop app for running mussel detection with an Electron frontend and Python backend.

![Sponsor and Advisor](docs/sponsor-advisor.png)

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
