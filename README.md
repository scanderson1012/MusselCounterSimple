# Mussel Counter
Download: https://github.com/natewill/MusselCounterSimple/releases/tag/v1.0.0

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

### Run Results Page

This is the main run workspace. Users can start a new run, choose a model family and version, add microscope images, adjust the detection threshold, start a run, recalculate counts without rerunning the model, and finalize reviewed labels so corrected detections can be reused later for fine-tuning.

Insert Run Results page screenshot here

### Prediction History Page

This page shows previous runs so users can reopen an older run, inspect its images, and review the saved results without losing historical context.

Insert Prediction History page screenshot here

### Image Review And Editing

This view is where users audit model results image-by-image. They can toggle bounding boxes, relabel detections, delete incorrect detections, and add brand-new bounding boxes for mussels the model missed. This is the main human-in-the-loop review step before saving corrected data for future model improvement.

Insert Image Review and Editing screenshot here

### Models Page

The Models page shows every saved model family and version in the app. Users can add a new model with its matching dataset zip, open model information, evaluate a version on its saved test set, fine-tune the newest version when enough reviewed images are available, export a model for sharing, and delete non-baseline models when needed.

Insert Models page screenshot here

### Add Model Workflow

When adding a model, the app asks for the model file, the matching Roboflow dataset zip, a model name, a description, and optional notes. This keeps model files tied to the data they came from so evaluation and later fine-tuning work correctly.

Insert Add Model modal screenshot here

### Model Information And Evaluation

Each model version has a saved information view that includes the description and evaluation metrics such as mAP, precision, and recall. This helps users compare versions and choose the right model for a run.

Insert Model Information screenshot here

### Settings Page

The Settings page controls two important app behaviors: how many reviewed images are required before fine-tuning becomes available, and whether the app should use automatic compute, CPU only, or GPU if available. On compatible Windows machines, the app can also enable the optional GPU runtime from here.

Insert Settings page screenshot here

### Usage Page

The Usage page gives in-app guidance for the full workflow, including running models, reviewing detections, finalizing reviewed labels, evaluating models, fine-tuning, exporting models, and the broader training and sharing process used by the team.

Insert Usage page screenshot here

## Prerequisites

For downloading and running the packaged desktop app:

- Windows 10 or Windows 11 for the Windows ZIP
- macOS for the macOS DMG

For opening the app during development from this repository:

- Node.js 20 or newer
- Python 3.11 or newer

## Installer Downloads

Download the installer package that matches your operating system from the latest GitHub release.

- Windows 10/11 ZIP: `https://github.com/scanderson1012/MusselCounterSimple/releases/download/v0.1.0/mussel-counter-simple-win32-x64-0.1.0.zip`
- macOS DMG: add your release asset link here after upload

The desktop installers include:

- the bundled baseline model family `baseline_fasterrcnn_model`
- the bundled baseline model file `baseline_fasterrcnn_model.pth`
- the bundled baseline training dataset `baseline_train`
- the bundled baseline test dataset `baseline_test`

Current limitation:

- macOS currently runs on CPU only
- optional GPU runtime support is implemented for Windows only

## Open The App During Development

Run these commands from the repository root, which is the folder that contains `package.json`, `backend`, `frontend`, and `electron`.

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
npm ci
npm start
```

### Windows

```powershell
py -3 -m venv ".venv"
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r "requirements.txt"
& "C:\Program Files\nodejs\npm.cmd" ci
& "C:\Program Files\nodejs\npm.cmd" start
```

If your PowerShell execution policies block script-based commands like `npm.ps1`, use the quoted `npm.cmd` form shown above. If virtual environment activation is blocked too, the direct `python.exe` path shown above avoids that issue.

## Build Desktop Packages

Use these steps when you want to create distributable app packages instead of just opening the app in development mode.

### macOS Build

Build this on a Mac.

```bash
python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-build.txt
npm ci
npm run make:desktop:mac -- --arch=arm64
```

The built DMG will be created under `out/make/`.

### Windows Build

Build this on Windows.

```powershell
py -3 -m venv ".venv-build"
& ".\.venv-build\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv-build\Scripts\python.exe" -m pip install -r "requirements.txt" -r "requirements-build.txt"
& "C:\Program Files\nodejs\npm.cmd" ci
& "C:\Program Files\nodejs\npm.cmd" run make:desktop:win
```

The built ZIP will be created under `out\make\`.

If your PowerShell execution policies block script-based commands like `npm.ps1`, use the quoted `npm.cmd` form shown above. If virtual environment activation is blocked too, the direct `python.exe` path shown above avoids that issue.

### Optional Windows GPU Build

If you want the Windows package to include the optional GPU runtime too, build the GPU backend first and then rerun the Windows packaging step.

```powershell
py -3 -m venv ".venv-build-gpu"
& ".\.venv-build-gpu\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv-build-gpu\Scripts\python.exe" -m pip install -r "requirements-gpu-win.txt" -r "requirements-build.txt"
& "C:\Program Files\nodejs\npm.cmd" run backend:build:gpu:win
& "C:\Program Files\nodejs\npm.cmd" run make:desktop:win
```

This produces one Windows app package that still works on CPU-only machines, while also allowing GPU acceleration on compatible Windows systems.

## How To Use The App

### 1. Start A New Run

The app opens on the Run Results page. Click `Start New Run`, choose the model family and version you want to use, then click `Add Images` to load microscope images into the current run.

### 2. Run A Model On Images

After choosing a model and adding images, click `Start Run`. The app processes the images and saves live and dead mussel detections for the run.

### 3. Adjust The Threshold

Each detection has a confidence score. The threshold controls which detections count toward the live and dead totals and which boxes stay visible in the image review pages.

- Lower thresholds keep more detections
- Higher thresholds keep only more confident detections
- `Recalculate` updates counts using the saved detections without rerunning the model

### 4. Review And Edit Detections

Open any image from a run to review detections in detail.

In the image review page, you can:

- toggle bounding boxes on and off
- relabel a detection from `live` to `dead` or from `dead` to `live`
- delete a detection that should not be there
- add a new bounding box when the model missed a mussel

This step is important because reviewed detections can later be reused to improve a model.

### 5. Finalize Reviewed Labels

After finishing review for a run, go back to the Run Results page and click `Finalize Reviewed Labels`. This saves the reviewed detections into the replay buffer for the model version that created the run.

Those saved reviewed images and detections are what the app uses later for fine-tuning.

### 6. Review Older Runs

Open the `Prediction History` page to revisit previous runs. You can reopen a run, inspect its images, and review the saved results later.

### 7. Add A New Model

Open the `Models` page and click `Add Model`.

To register a model, the app currently expects:

- a model file in `.pth` or `.pt` format
- the matching Roboflow dataset `.zip` used to create that model
- a model name
- a description
- optional notes

The bundled baseline model family `baseline_fasterrcnn_model` is already included on first launch.

### 8. Evaluate A Model On Its Test Set

On the `Models` page, click `Evaluate on Test Set` for the model version you want to check. The app uses that model version's saved test dataset and records evaluation metrics so you can compare model quality later.

### 9. Fine-Tune The Latest Model Version

The app can create a new model version from reviewed images that were saved through `Finalize Reviewed Labels`.

Fine-tuning becomes available when the newest version of a model has enough saved reviewed images based on the setting in the `Settings` page. When that threshold is reached, the app shows that fine-tuning is available.

To fine-tune:

1. Open `Settings` and confirm the fine-tuning thresholds you want.
2. Keep reviewing runs and finalizing reviewed labels until enough images have been saved.
3. Open `Models`.
4. Click `Fine-Tune` on the newest version of the model family.

When fine-tuning finishes, the app creates a new version of that model.

### 10. Export And Share A Model

On the `Models` page, click `Export` for a model version to save it as a shareable zip file. Another user can then add that exported model to their own copy of the app.

### 11. Configure Compute Settings

Open the `Settings` page to choose:

- `Automatic`
- `CPU only`
- `GPU if available`

If the app is running on a compatible Windows machine and the optional GPU runtime is installed, users can enable GPU acceleration there. If GPU is not available or not ready, the app still falls back to CPU.
