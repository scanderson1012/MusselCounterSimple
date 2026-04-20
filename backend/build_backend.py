"""Build a standalone backend binary for desktop packaging so end users do not need Python
installed."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


# Keep build paths relative to this file so command behavior is stable from any current working directory.
BACKEND_DIRECTORY = Path(__file__).resolve().parent
SERVER_ENTRY = BACKEND_DIRECTORY / "server_entry.py"
EXECUTABLE_NAME = os.getenv("MUSSEL_BACKEND_EXECUTABLE_NAME", "mussel-backend")
DIST_DIRECTORY = Path(
    os.getenv("MUSSEL_BACKEND_DIST_DIR", str(BACKEND_DIRECTORY / "dist"))
).expanduser().resolve()
BUILD_DIRECTORY = Path(
    os.getenv("MUSSEL_BACKEND_BUILD_DIR", str(BACKEND_DIRECTORY / "build"))
).expanduser().resolve()
SPEC_DIRECTORY = BACKEND_DIRECTORY
SCHEMA_PATH = BACKEND_DIRECTORY / "schema.sql"


def build_backend_executable() -> None:
    """Create a one-file backend executable for Electron packaged builds."""
    # PyInstaller expects different path separators for --add-data on Windows vs POSIX.
    add_data_separator = ";" if sys.platform.startswith("win") else ":"
    add_data_arg = f"{SCHEMA_PATH}{add_data_separator}backend"

    # Build one standalone binary and include schema.sql so DB init works in packaged mode.
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        EXECUTABLE_NAME,
        "--distpath",
        str(DIST_DIRECTORY),
        "--workpath",
        str(BUILD_DIRECTORY),
        "--specpath",
        str(SPEC_DIRECTORY),
        "--add-data",
        add_data_arg,
        # Uvicorn uses dynamic imports; these keep packaging deterministic.
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        str(SERVER_ENTRY),
    ]

    # Fail fast if PyInstaller returns non-zero so CI/build scripts stop immediately.
    subprocess.run(command, check=True)


if __name__ == "__main__":
    build_backend_executable()
