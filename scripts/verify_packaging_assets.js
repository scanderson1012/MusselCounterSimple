const fs = require("node:fs");
const path = require("node:path");

const PROJECT_ROOT = path.resolve(__dirname, "..");

const requiredPaths = [
  path.join(PROJECT_ROOT, "baseline_fasterrcnn_model.pth"),
  path.join(PROJECT_ROOT, "bundled_assets", "baseline_train", "images"),
  path.join(PROJECT_ROOT, "bundled_assets", "baseline_train", "labels"),
  path.join(PROJECT_ROOT, "bundled_assets", "baseline_test", "images"),
  path.join(PROJECT_ROOT, "bundled_assets", "baseline_test", "labels"),
];

const missingPaths = requiredPaths.filter((requiredPath) => !fs.existsSync(requiredPath));

if (missingPaths.length > 0) {
  process.stderr.write("Packaging is missing required bundled baseline assets:\n");
  for (const missingPath of missingPaths) {
    process.stderr.write(`- ${missingPath}\n`);
  }
  process.exit(1);
}

process.stdout.write("Bundled baseline assets verified.\n");
