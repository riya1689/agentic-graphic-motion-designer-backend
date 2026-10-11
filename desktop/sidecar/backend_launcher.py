from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _write_startup_log(message: str) -> None:
    """Keep a client-readable log when the packaged sidecar cannot start."""
    config_dir = os.getenv("AGENTIC_CONFIG_DIR", "").strip()
    if not config_dir:
        return

    try:
        log_file = Path(config_dir) / "logs" / "backend.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        # Logging must never prevent the backend from starting.
        pass


def _load_external_environment() -> None:
    from dotenv import load_dotenv

    candidates: list[Path] = []

    config_dir = os.getenv("AGENTIC_CONFIG_DIR")
    if config_dir:
        candidates.append(Path(config_dir) / ".env")

    executable_dir = Path(sys.executable).resolve().parent
    candidates.append(executable_dir / ".env")

    if not getattr(sys, "frozen", False):
        source_root = Path(__file__).resolve().parents[2]
        candidates.append(source_root / ".env")

    for parent in executable_dir.parents:
        candidates.append(parent / ".env")

    for env_file in candidates:
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            return


_load_external_environment()

# Packaged desktop builds are self-contained and never connect to PostgreSQL.
os.environ["STORAGE_BACKEND"] = "sqlite"
os.environ["AGENTIC_DESKTOP_MODE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

try:
    import uvicorn
    from server import app
except BaseException:
    _write_startup_log(
        "Backend import failed:\n" + traceback.format_exc(),
    )
    raise


def main() -> None:
    host = os.getenv("AGENTIC_BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("AGENTIC_BACKEND_PORT", "8000"))

    _write_startup_log(
        f"Starting backend host={host} port={port} storage=sqlite",
    )
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
        )
    except BaseException:
        _write_startup_log(
            "Backend process failed:\n" + traceback.format_exc(),
        )
        raise


if __name__ == "__main__":
    main()
