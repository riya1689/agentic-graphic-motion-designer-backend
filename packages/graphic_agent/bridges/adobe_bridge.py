"""
Adobe Ecosystem Integration Bridge (Phase 2)

RESPONSIBILITY:
- Detect local Adobe Illustrator and Photoshop installations
- Execute generated ExtendScript (.jsx) scripts via Windows COM / CLI
- Output native vector .ai and multi-layer .psd files directly from Adobe apps

IMPORTANT:
- Completely decoupled from Manager and Planner
- Graceful fallback if Adobe applications are not installed
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


# ============================================================
# ADOBE APPLICATION DETECTORS
# ============================================================

def is_illustrator_available() -> bool:
    """
    Check if Adobe Illustrator COM interface or executable is available.
    """
    try:
        import win32com.client
        app = win32com.client.Dispatch("Illustrator.Application")
        return app is not None
    except Exception:
        pass

    # Check common installation directories
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    adobe_dir = Path(program_files) / "Adobe"
    if adobe_dir.exists():
        for item in adobe_dir.glob("Adobe Illustrator*"):
            if (item / "Support Files" / "Contents" / "Windows" / "Illustrator.exe").exists():
                return True

    return False


def is_photoshop_available() -> bool:
    """
    Check if Adobe Photoshop COM interface or executable is available.
    """
    try:
        import win32com.client
        app = win32com.client.Dispatch("Photoshop.Application")
        return app is not None
    except Exception:
        pass

    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    adobe_dir = Path(program_files) / "Adobe"
    if adobe_dir.exists():
        for item in adobe_dir.glob("Adobe Photoshop*"):
            if (item / "Photoshop.exe").exists():
                return True

    return False


# ============================================================
# EXTENDSCRIPT (.JSX) EXECUTION
# ============================================================

def execute_illustrator_jsx(jsx_script_path: str | Path) -> bool:
    """
    Execute a JSX ExtendScript file inside Adobe Illustrator.
    """
    script_path = Path(jsx_script_path).resolve()
    if not script_path.exists():
        print(f"[ADOBE BRIDGE] JSX script not found: {script_path}")
        return False

    # 1. Try COM Automation
    try:
        import win32com.client
        app = win32com.client.Dispatch("Illustrator.Application")
        app.DoJavaScriptFile(str(script_path))
        print(f"[ADOBE BRIDGE] Executed Illustrator JSX via COM: {script_path.name}")
        return True
    except Exception as exc:
        print(f"[ADOBE BRIDGE] Illustrator COM notice ({exc}). Trying CLI fallback...")

    # 2. Try CLI Direct Executable
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    adobe_dir = Path(program_files) / "Adobe"
    if adobe_dir.exists():
        for item in adobe_dir.glob("Adobe Illustrator*"):
            exe_path = item / "Support Files" / "Contents" / "Windows" / "Illustrator.exe"
            if exe_path.exists():
                try:
                    subprocess.run(
                        [str(exe_path), "-r", str(script_path)],
                        timeout=60,
                        check=True,
                    )
                    print(f"[ADOBE BRIDGE] Executed Illustrator JSX via CLI: {script_path.name}")
                    return True
                except Exception as cli_exc:
                    print(f"[ADOBE BRIDGE] Illustrator CLI execution error: {cli_exc}")

    return False


def execute_photoshop_jsx(jsx_script_path: str | Path) -> bool:
    """
    Execute a JSX ExtendScript file inside Adobe Photoshop.
    """
    script_path = Path(jsx_script_path).resolve()
    if not script_path.exists():
        print(f"[ADOBE BRIDGE] JSX script not found: {script_path}")
        return False

    # 1. Try COM Automation
    try:
        import win32com.client
        app = win32com.client.Dispatch("Photoshop.Application")
        app.DoJavaScriptFile(str(script_path))
        print(f"[ADOBE BRIDGE] Executed Photoshop JSX via COM: {script_path.name}")
        return True
    except Exception as exc:
        print(f"[ADOBE BRIDGE] Photoshop COM execution notice ({exc}).")

    return False
