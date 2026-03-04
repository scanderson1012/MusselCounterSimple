const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const API_HOST = "127.0.0.1";
const DEFAULT_API_PORT = 8000;
const MAX_PORT_SCAN_COUNT = 40;
const ROOT_DIR = path.resolve(__dirname, "..");
const UI_INDEX_PATH = path.join(ROOT_DIR, "frontend", "index.html");

let backendProcess = null;
let mainWindow = null;
let backendPort = DEFAULT_API_PORT;
let backendBaseUrl = `http://${API_HOST}:${DEFAULT_API_PORT}`;

function getPythonCommand() {
  if (process.env.PYTHON_BIN) {
    return process.env.PYTHON_BIN;
  }

  const projectVenvCandidate = process.platform === "win32"
    ? path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    : path.join(ROOT_DIR, ".venv", "bin", "python");
  if (fs.existsSync(projectVenvCandidate)) {
    return projectVenvCandidate;
  }

  if (process.env.VIRTUAL_ENV) {
    const candidate = process.platform === "win32"
      ? path.join(process.env.VIRTUAL_ENV, "Scripts", "python.exe")
      : path.join(process.env.VIRTUAL_ENV, "bin", "python");

    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function getPackagedBackendExecutablePath() {
  const executableName = process.platform === "win32"
    ? "mussel-backend.exe"
    : "mussel-backend";
  return path.join(process.resourcesPath, "dist", executableName);
}

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

async function startBackendServer() {
  if (backendProcess) {
    return;
  }

  backendPort = await findAvailableBackendPort();
  backendBaseUrl = `http://${API_HOST}:${backendPort}`;
  if (backendPort !== DEFAULT_API_PORT) {
    process.stdout.write(
      `[backend] default port ${DEFAULT_API_PORT} in use, using ${backendPort} instead\n`
    );
  }

  if (app.isPackaged) {
    const executablePath = getPackagedBackendExecutablePath();
    if (!fs.existsSync(executablePath)) {
      throw new Error(`Packaged backend executable not found: ${executablePath}`);
    }
    const backendDataDir = path.join(app.getPath("userData"), "backend");
    const packagedWorkingDirectory = process.resourcesPath;

    backendProcess = spawn(executablePath, [], {
      cwd: packagedWorkingDirectory,
      env: {
        ...process.env,
        MUSSEL_API_HOST: API_HOST,
        MUSSEL_API_PORT: String(backendPort),
        MUSSEL_APP_DATA_DIR: backendDataDir,
      },
      stdio: "pipe",
    });
  } else {
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

function stopBackendServer() {
  if (!backendProcess) {
    return;
  }

  if (!backendProcess.killed) {
    backendProcess.kill("SIGTERM");
  }
}

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

ipcMain.handle("backend:base-url", async () => {
  return backendBaseUrl;
});

ipcMain.handle("backend:is-ready", async () => {
  try {
    const response = await fetch(`${backendBaseUrl}/models`);
    return response.ok;
  } catch {
    return false;
  }
});

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

  const response = await fetch(url, options);
  const responseText = await response.text();

  let responseData = null;
  if (responseText) {
    try {
      responseData = JSON.parse(responseText);
    } catch {
      responseData = responseText;
    }
  }

  if (!response.ok) {
    const detail = responseData && typeof responseData === "object" && "detail" in responseData
      ? responseData.detail
      : responseData;
    throw new Error(
      `Request failed (${method} ${normalizedPath}): ${String(detail ?? response.statusText)}`
    );
  }

  return responseData;
});

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

  // Get models dir from backend API
  let modelsDir;
  try {
    const response = await fetch(`${backendBaseUrl}/models`);
    const data = await response.json();
    modelsDir = data.models_dir;
  } catch {
    throw new Error("Could not determine models directory from backend.");
  }

  const destPath = path.join(modelsDir, fileName);
  if (fs.existsSync(destPath)) {
    return { fileName, alreadyExists: true };
  }

  fs.copyFileSync(sourcePath, destPath);
  return { fileName, alreadyExists: false };
});

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

app.whenReady().then(async () => {
  try {
    await startBackendServer();
    createWindow();
  } catch (error) {
    process.stderr.write(`[backend] startup failed: ${String(error)}\n`);
    app.quit();
    return;
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopBackendServer();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
