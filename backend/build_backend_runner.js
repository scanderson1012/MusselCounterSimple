/**
 * Runs backend/build_backend.py from npm scripts.
 * It uses Python from the project .venv if available, otherwise system Python,
 * and forwards success/failure back to npm or CI.
 */
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const BUILD_REQUIREMENTS_PATH = path.join(PROJECT_ROOT, "requirements-build.txt");
const DEFAULT_VARIANT = "cpu";

function parse_cli_options() {
  const parsedOptions = {
    variant: DEFAULT_VARIANT,
  };
  for (const argument of process.argv.slice(2)) {
    if (argument.startsWith("--variant=")) {
      parsedOptions.variant = argument.split("=", 2)[1] || DEFAULT_VARIANT;
    }
  }
  return parsedOptions;
}

function get_variant_build_config(variant) {
  if (variant === "gpu-win") {
    return {
      executableName: "mussel-backend-gpu",
      distDir: path.join(PROJECT_ROOT, "backend", "dist_gpu"),
      buildDir: path.join(PROJECT_ROOT, "backend", "build_gpu"),
    };
  }
  return {
    executableName: "mussel-backend",
    distDir: path.join(PROJECT_ROOT, "backend", "dist"),
    buildDir: path.join(PROJECT_ROOT, "backend", "build"),
  };
}

function select_python_command() {
  // Returns the command string used to run Python
  // (for example: .../.venv/bin/python, python, or python3).
  // Prefer project-local virtualenv when available.
  const venvCandidate = process.platform === "win32"
    ? path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    : path.join(PROJECT_ROOT, ".venv", "bin", "python");
  if (fs.existsSync(venvCandidate)) {
    return venvCandidate;
  }

  // Fall back to system Python command names by platform.
  return process.platform === "win32" ? "python" : "python3";
}

const options = parse_cli_options();
const variantBuildConfig = get_variant_build_config(options.variant);
const pythonCommand = select_python_command();

// Ensure build-only Python tools (for example, PyInstaller) are available.
const installBuildRequirementsResult = spawnSync(
  pythonCommand,
  ["-m", "pip", "install", "-r", BUILD_REQUIREMENTS_PATH],
  {
    cwd: PROJECT_ROOT,
    stdio: "inherit",
    env: process.env,
  }
);
if (typeof installBuildRequirementsResult.status === "number" && installBuildRequirementsResult.status !== 0) {
  process.exit(installBuildRequirementsResult.status);
}
if (installBuildRequirementsResult.error) {
  throw installBuildRequirementsResult.error;
}

// Run the Python packager script synchronously so npm exits only after build completes.
const result = spawnSync(pythonCommand, [path.join(__dirname, "build_backend.py")], {
  cwd: PROJECT_ROOT,
  stdio: "inherit",
  env: {
    ...process.env,
    MUSSEL_BACKEND_EXECUTABLE_NAME: variantBuildConfig.executableName,
    MUSSEL_BACKEND_DIST_DIR: variantBuildConfig.distDir,
    MUSSEL_BACKEND_BUILD_DIR: variantBuildConfig.buildDir,
  },
});

// Propagate Python process exit code directly to this Node wrapper.
if (typeof result.status === "number") {
  process.exit(result.status);
}

// If process creation failed, surface the underlying error.
if (result.error) {
  throw result.error;
}

// Fallback non-zero exit if neither status nor error was provided.
process.exit(1);
