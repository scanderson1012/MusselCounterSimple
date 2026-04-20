/**
 * Electron main-process entrypoint.
 *
 * If you are new to Electron:
 * - The "main process" is the Node.js process that controls the desktop app lifecycle.
 * - The "renderer process" is the browser-like UI window that runs your frontend code.
 * - This file starts/stops the Python backend API, creates the app window, and exposes
 *   a small IPC API (`ipcMain.handle(...)`) so the renderer can ask the main process to
 *   do privileged work (filesystem, dialogs, backend proxy requests).
 */

const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const API_HOST = "127.0.0.1";
const DEFAULT_API_PORT = 8000;
const MAX_PORT_SCAN_COUNT = 40;
const BACKEND_STARTUP_TIMEOUT_MS = 120_000;
const BACKEND_READINESS_POLL_MS = 500;
const ROOT_DIR = path.resolve(__dirname, "..");
const UI_INDEX_PATH = path.join(ROOT_DIR, "frontend", "dist", "index.html");

let backendProcess = null;
let mainWindow = null;
let backendPort = DEFAULT_API_PORT;
let backendBaseUrl = `http://${API_HOST}:${DEFAULT_API_PORT}`;

/** Pause execution for a fixed number of milliseconds. */
function waitMilliseconds(durationMilliseconds) {
  return new Promise((resolve) => {
    setTimeout(resolve, durationMilliseconds);
  });
}

/**
 * Select the Python command used in development mode.
 *
 * Priority:
 * 1) Project virtualenv (`.venv`)
 * 2) System Python command (`python` on Windows, `python3` elsewhere)
 */
function getPythonCommand() {
  const projectVenvCandidate = process.platform === "win32"
    ? path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    : path.join(ROOT_DIR, ".venv", "bin", "python");
  if (fs.existsSync(projectVenvCandidate)) {
    return projectVenvCandidate;
  }

  return process.platform === "win32" ? "python" : "python3";
}

/** Return the packaged backend executable path used in production builds. */
function getPackagedBackendExecutablePath() {
  const executableName = process.platform === "win32"
    ? "mussel-backend.exe"
    : "mussel-backend";
  return path.join(process.resourcesPath, "dist", executableName);
}

/** Test whether a TCP port is currently free on localhost. */
function isPortAvailable(port) {
  return new Promise((resolve) => {
    const testServer = net.createServer();

    testServer.once("error", (error) => {
      if (error && error.code === "EADDRINUSE") {
        resolve(false);
        return;
      }
      resolve(false);
    });

    testServer.once("listening", () => {
      testServer.close(() => resolve(true));
    });

    testServer.listen(port, API_HOST);
  });
}

/** Find the first available backend port, starting at 8000. */
async function findAvailableBackendPort() {
  for (let offset = 0; offset < MAX_PORT_SCAN_COUNT; offset += 1) {
    const candidatePort = DEFAULT_API_PORT + offset;
    // eslint-disable-next-line no-await-in-loop
    const available = await isPortAvailable(candidatePort);
    if (available) {
      return candidatePort;
    }
  }

  throw new Error(
    `Could not find a free backend port in range ${DEFAULT_API_PORT}-${DEFAULT_API_PORT + MAX_PORT_SCAN_COUNT - 1}`
  );
}

/**
 * Start the backend server process (packaged binary or dev uvicorn command).
 *
 * This function is idempotent: if already running, it returns immediately.
 */
async function startBackendServer() {
  if (backendProcess) {
    return;
  }

  // Use a free local port so startup still works when 8000 is occupied.
  backendPort = await findAvailableBackendPort();
  backendBaseUrl = `http://${API_HOST}:${backendPort}`;
  if (backendPort !== DEFAULT_API_PORT) {
    process.stdout.write(
      `[backend] default port ${DEFAULT_API_PORT} in use, using ${backendPort} instead\n`
    );
  }

  // Packaged app: run prebuilt backend executable bundled in app resources.
  if (app.isPackaged) {
    const executablePath = getPackagedBackendExecutablePath();
    if (!fs.existsSync(executablePath)) {
      throw new Error(`Packaged backend executable not found: ${executablePath}`);
    }
    const backendDataDir = path.join(app.getPath("userData"), "backend");
    const packagedWorkingDirectory = process.resourcesPath;
    const bundledAssetsDir = path.join(process.resourcesPath, "bundled_assets");
    const baselineModelPath = path.join(process.resourcesPath, "fasterrcnn_baseline.pth");

    backendProcess = spawn(executablePath, [], {
      cwd: packagedWorkingDirectory,
      env: {
        ...process.env,
        MUSSEL_API_HOST: API_HOST,
        MUSSEL_API_PORT: String(backendPort),
        MUSSEL_APP_DATA_DIR: backendDataDir,
        MUSSEL_BUNDLED_ASSETS_DIR: bundledAssetsDir,
        MUSSEL_BASELINE_MODEL_PATH: baselineModelPath,
      },
      stdio: "pipe",
    });
  } else {
    // Development mode: run backend directly with Python + Uvicorn.
    const pythonCommand = getPythonCommand();
    backendProcess = spawn(
      pythonCommand,
      ["-m", "uvicorn", "backend.main:app", "--host", API_HOST, "--port", String(backendPort)],
      {
        cwd: ROOT_DIR,
        env: process.env,
        stdio: "pipe",
      }
    );
  }

  // Forward backend logs to Electron process output for easier debugging.
  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });

  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });

  backendProcess.on("error", (error) => {
    process.stderr.write(`[backend] failed to start: ${String(error)}\n`);
  });

  backendProcess.on("exit", (code, signal) => {
    backendProcess = null;
    process.stdout.write(
      `[backend] exited (code=${String(code)}, signal=${String(signal)})\n`
    );
  });
}

/** Probe backend health by calling `/models`. */
async function isBackendReady() {
  try {
    const response = await fetch(`${backendBaseUrl}/models`);
    return response.ok;
  } catch {
    return false;
  }
}

/** Wait until backend responds successfully or timeout expires. */
async function waitForBackendReady() {
  const startupDeadline = Date.now() + BACKEND_STARTUP_TIMEOUT_MS;

  while (Date.now() < startupDeadline) {
    if (!backendProcess) {
      throw new Error("Backend process exited before becoming ready.");
    }

    // eslint-disable-next-line no-await-in-loop
    if (await isBackendReady()) {
      return;
    }

    // eslint-disable-next-line no-await-in-loop
    await waitMilliseconds(BACKEND_READINESS_POLL_MS);
  }

  throw new Error("Backend did not become ready in time.");
}

/** Stop backend process if one is currently running. */
function stopBackendServer() {
  if (!backendProcess) {
    return;
  }

  if (!backendProcess.killed) {
    backendProcess.kill("SIGTERM");
  }
}

/** Create the main application window and load the frontend HTML. */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 680,
    show: false,
    backgroundColor: "#f4f7ef",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(UI_INDEX_PATH);
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });
}

// IPC endpoint: renderer asks for current backend base URL.
ipcMain.handle("backend:base-url", async () => {
  return backendBaseUrl;
});

// IPC endpoint: renderer asks if backend is responding.
ipcMain.handle("backend:is-ready", async () => {
  return isBackendReady();
});

// IPC endpoint: renderer sends API requests; main process proxies them to backend.
ipcMain.handle("backend:request", async (_event, request) => {
  const method = String(request?.method ?? "GET").toUpperCase();
  const apiPath = String(request?.apiPath ?? "/");
  const normalizedPath = apiPath.startsWith("/") ? apiPath : `/${apiPath}`;
  const url = `${backendBaseUrl}${normalizedPath}`;

  const options = {
    method,
    headers: {},
  };

  if (request?.body !== undefined) {
    options.headers["content-type"] = "application/json";
    options.body = JSON.stringify(request.body);
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new Error(`Could not reach the backend. ${String(error?.message ?? error)}`);
  }
  const responseText = await response.text();

  // Try JSON first; fall back to plain text.
  let responseData = null;
  if (responseText) {
    try {
      responseData = JSON.parse(responseText);
    } catch {
      responseData = responseText;
    }
  }

  if (!response.ok) {
    // Normalize backend error payload to a readable desktop error message.
    const detail = responseData && typeof responseData === "object" && "detail" in responseData
      ? responseData.detail
      : responseData;
    throw new Error(
      `Request failed (${method} ${normalizedPath}): ${String(detail ?? response.statusText)}`
    );
  }

  return responseData;
});

// IPC endpoint: open native file picker for a model file and return its path.
ipcMain.handle("dialog:pick-model", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Model File",
    properties: ["openFile"],
    filters: [
      { name: "Model Files", extensions: ["pth", "pt", "onnx", "bin"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  const sourcePath = result.filePaths[0];
  const fileName = path.basename(sourcePath);
  return { fileName, filePath: sourcePath };
});

// IPC endpoint: open native file picker for a Roboflow dataset zip.
ipcMain.handle("dialog:pick-dataset-zip", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Dataset Zip File",
    properties: ["openFile"],
    filters: [
      { name: "Zip Files", extensions: ["zip"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  const sourcePath = result.filePaths[0];
  const fileName = path.basename(sourcePath);
  return { fileName, filePath: sourcePath };
});

// IPC endpoint: download one backend-served file through a save dialog.
ipcMain.handle("backend:download-file", async (_event, request) => {
  const apiPath = String(request?.apiPath ?? "/");
  const normalizedPath = apiPath.startsWith("/") ? apiPath : `/${apiPath}`;
  const defaultFileName = String(request?.defaultFileName ?? "download.bin");

  const saveResult = await dialog.showSaveDialog(mainWindow, {
    title: "Export Model",
    defaultPath: defaultFileName,
  });
  if (saveResult.canceled || !saveResult.filePath) {
    return { saved: false };
  }

  let response;
  try {
    response = await fetch(`${backendBaseUrl}${normalizedPath}`);
  } catch (error) {
    throw new Error(`Could not reach the backend. ${String(error?.message ?? error)}`);
  }
  if (!response.ok) {
    const responseText = await response.text();
    throw new Error(responseText || `Download failed with status ${response.status}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  fs.writeFileSync(saveResult.filePath, Buffer.from(arrayBuffer));
  return { saved: true, filePath: saveResult.filePath };
});

// IPC endpoint: open an external URL in the user's default browser.
ipcMain.handle("shell:open-external", async (_event, request) => {
  const rawUrl = String(request?.url ?? "").trim();
  if (!rawUrl) {
    throw new Error("No URL provided.");
  }
  await shell.openExternal(rawUrl);
  return { opened: true };
});

// IPC endpoint: open native file picker for input images.
ipcMain.handle("dialog:pick-images", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Mussel Images",
    properties: ["openFile", "multiSelections"],
    filters: [
      { name: "Images", extensions: ["jpg", "jpeg", "png", "bmp", "tif", "tiff"] },
    ],
  });

  if (result.canceled) {
    return [];
  }

  return result.filePaths;
});

// App startup sequence:
// 1) start backend
// 2) wait until it is reachable
// 3) create the UI window
app.whenReady().then(async () => {
  try {
    await startBackendServer();
    await waitForBackendReady();
    createWindow();
  } catch (error) {
    process.stderr.write(`[backend] startup failed: ${String(error)}\n`);
    app.quit();
    return;
  }

  // macOS convention: clicking dock icon should reopen a window.
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Ensure backend is terminated when app is quitting.
app.on("before-quit", () => {
  stopBackendServer();
});

// On macOS apps usually stay open without windows; other platforms quit.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
