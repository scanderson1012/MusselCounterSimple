const path = require("node:path");
const fs = require("node:fs");

const extraResources = [
  path.resolve(__dirname, "backend", "dist"),
  path.resolve(__dirname, "bundled_assets"),
  path.resolve(__dirname, "baseline_fasterrcnn_model.pth"),
];
const optionalGpuBackendDirectory = path.resolve(__dirname, "backend", "dist_gpu");
if (fs.existsSync(optionalGpuBackendDirectory)) {
  extraResources.push(optionalGpuBackendDirectory);
}

// Keep generated runtimes and bundled assets out of app.asar.
// They are copied separately via extraResource, and including them twice
// can make the packaged app unnecessarily huge.
const packagerIgnore = [
  /^\/\.git($|\/)/,
  /^\/\.tmp_smoke($|\/)/,
  /^\/\.venv($|\/)/,
  /^\/\.venv-build-cpu($|\/)/,
  /^\/\.venv-build-gpu($|\/)/,
  /^\/app_data($|\/)/,
  /^\/out($|\/)/,
  /^\/backend\/build($|\/)/,
  /^\/backend\/build_gpu($|\/)/,
  /^\/backend\/dist($|\/)/,
  /^\/backend\/dist_gpu($|\/)/,
  /^\/bundled_assets($|\/)/,
  /^\/baseline_fasterrcnn_model\.pth$/,
];

module.exports = {
  packagerConfig: {
    asar: true,
    extraResource: extraResources,
    ignore: packagerIgnore,
  },
  makers: [
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin", "linux", "win32"],
    },
    {
      name: "@electron-forge/maker-dmg",
      platforms: ["darwin"],
      config: {},
    },
  ],
};
