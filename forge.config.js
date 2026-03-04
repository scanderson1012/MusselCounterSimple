const path = require("node:path");

module.exports = {
  packagerConfig: {
    asar: true,
    extraResource: [
      path.resolve(__dirname, "backend", "dist"),
    ],
  },
  makers: [
    {
      name: "@electron-forge/maker-squirrel",
      config: {
        authors: "Nate Williams, Austin Ashley, Fernando Gomez, Siddharth Rakshit",
        description: "Desktop app for running mussel detection with an Electron frontend and Python backend.",
      },
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin", "linux"],
    },
    {
      name: "@electron-forge/maker-dmg",
      platforms: ["darwin"],
      config: {},
    },
  ],
};
