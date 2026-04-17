const path = require("node:path");

module.exports = {
  packagerConfig: {
    asar: true,
    extraResource: [
      path.resolve(__dirname, "backend", "dist"),
      path.resolve(__dirname, "bundled_assets"),
      path.resolve(__dirname, "fasterrcnn_baseline.pth"),
    ],
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
