"""
Launcher script for Economic Indicators Dashboard
"""

import os
import sys
import subprocess
import webbrowser
import threading
import time
from pathlib import Path


def _shortcut_path():
    if sys.platform == 'win32':
        return Path.home() / "Desktop" / "Economic Dashboard.lnk"
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop / "economic-dashboard.desktop"
    return Path.home() / ".local" / "share" / "applications" / "economic-dashboard.desktop"


def create_shortcut():
    """Create a desktop shortcut. Returns True if created, False if already exists, raises on failure."""
    if _shortcut_path().exists():
        return False
    if sys.platform == 'win32':
        _create_windows_shortcut()
    else:
        _create_linux_shortcut()
    return True


def _find_script():
    """Locate the get-data executable, raising if not found."""
    import shutil
    # shutil.which respects PATH — most reliable
    found = shutil.which("get-data")
    if found:
        return Path(found)
    # Fallback: find the Scripts directory next to the running Python.
    # System Python (Windows): C:\PythonXX\python.exe  → Scripts at C:\PythonXX\Scripts
    # Venv       (Windows): C:\venv\Scripts\python.exe → Scripts at C:\venv\Scripts
    python_dir = Path(sys.executable).parent
    if sys.platform == 'win32':
        # If python.exe is already inside a Scripts folder (venv), don't add it again.
        scripts_dir = python_dir if python_dir.name.lower() == 'scripts' else python_dir / 'Scripts'
    else:
        scripts_dir = python_dir
    for name in ("get-data.exe", "get-data"):
        candidate = scripts_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate the get-data script. "
        "Make sure the package is installed and its Scripts folder is on PATH."
    )


def _create_windows_shortcut():
    shortcut_path = _shortcut_path()
    target = _find_script()

    # Use escaped backslashes inside the PowerShell string literals
    lnk = str(shortcut_path).replace("'", "''")
    tgt = str(target).replace("'", "''")

    ps_script = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath='{tgt}';"
        f"$s.Description='Economic Indicators Dashboard';"
        f"$s.Save()"
    )
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", ps_script,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell error: {result.stderr.strip()}")
    print(f"Shortcut created at: {shortcut_path}")


def _create_linux_shortcut():
    shortcut_path = _shortcut_path()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    scripts_dir = Path(sys.executable).parent
    target = scripts_dir / "get-data"

    content = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=Economic Dashboard\n"
        "Comment=Macroeconomic Data Explorer\n"
        f"Exec={target}\n"
        "Icon=utilities-terminal\n"
        "Terminal=false\n"
        "Categories=Office;Finance;\n"
    )
    shortcut_path.write_text(content)
    os.chmod(shortcut_path, 0o755)
    print(f"Shortcut created at: {shortcut_path}")


def open_browser(url, delay=2):
    """Open browser after a short delay to allow server to start"""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    """Launch the Streamlit dashboard"""

    # Create desktop shortcut on first run if it doesn't exist yet
    try:
        create_shortcut()
    except Exception as e:
        print(f"Warning: Could not create desktop shortcut: {e}")

    # Get the path to app.py
    app_path = Path(__file__).parent / "app.py"

    if not app_path.exists():
        print(f"[ERROR] Could not find app.py at {app_path}")
        sys.exit(1)

    port = 8501
    url = f"http://localhost:{port}"

    streamlit_args = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false"
    ]

    print("Launching Economic Indicators Dashboard...")
    print(f"App location: {app_path}")
    print(f"Opening browser at: {url}")
    print("\n" + "="*60)
    print("Press Ctrl+C to stop the dashboard")
    print("="*60 + "\n")

    browser_thread = threading.Thread(target=open_browser, args=(url,))
    browser_thread.daemon = True
    browser_thread.start()

    try:
        subprocess.run(streamlit_args)
    except KeyboardInterrupt:
        print("\n\nDashboard stopped. Goodbye!")
    except Exception as e:
        print(f"\n[ERROR] Error launching dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
