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

module.exports = {
  packagerConfig: {
    asar: true,
    extraResource: extraResources,
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
