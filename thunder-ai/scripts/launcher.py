"""Cross-platform launcher used by START_THUNDER.* / STOP_THUNDER.*

start: check Python, create .venv on first run, install pinned requirements, init the DB,
       start the engine and the dashboard in the background, open http://127.0.0.1:8501
stop:  stop both cleanly.
Uses only the standard library so it runs before anything is installed.
"""
from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
DATA = ROOT / "data"
URL = "http://127.0.0.1:8501"
PY_URL = "https://www.python.org/downloads/"


def say(msg: str) -> None:
    print(f"[THUNDER] {msg}", flush=True)


def vpy() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_python() -> None:
    if sys.version_info < (3, 11):
        say(f"Python 3.11 or newer is needed (found {sys.version.split()[0]}). Download it from {PY_URL}")
        input("Press Enter to close…")
        sys.exit(1)


def ensure_env() -> None:
    req = ROOT / "requirements.txt"
    stamp = VENV / ".req-hash"
    h = hashlib.sha256(req.read_bytes()).hexdigest()
    if not vpy().exists():
        say("First run: creating a private Python environment (one time, a few minutes)…")
        venv.EnvBuilder(with_pip=True).create(VENV)
    if not stamp.exists() or stamp.read_text() != h:
        say("Installing the required packages (pinned versions)…")
        subprocess.check_call([str(vpy()), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(req)])
        stamp.write_text(h)


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e.setdefault("THUNDER_DATA_DIR", str(DATA))
    return e


def spawn(args: list[str], name: str) -> int:
    DATA.mkdir(exist_ok=True)
    (DATA / "logs").mkdir(exist_ok=True)
    log = open(DATA / "logs" / f"{name}.out", "ab")
    kw = {"cwd": str(ROOT), "env": env(), "stdout": log, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(args, **kw)
    (DATA / f"{name}.pid").write_text(str(p.pid))
    return p.pid


def alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def pid_of(name: str) -> int | None:
    f = DATA / f"{name}.pid"
    if f.exists():
        try:
            pid = int(f.read_text().strip())
            return pid if alive(pid) else None
        except ValueError:
            return None
    return None


def start(demo: bool = False) -> None:
    ensure_python()
    ensure_env()
    subprocess.check_call([str(vpy()), "-c", "from thunder.db import connect; connect().close()"], cwd=str(ROOT), env=env())
    if not pid_of("engine"):
        say("Starting the engine (the part that trades on paper 24/7)…")
        spawn([str(vpy()), "-m", "thunder.engine.main"] + (["--demo"] if demo else []), "engine")
    if not pid_of("dashboard"):
        say("Starting the dashboard…")
        spawn([str(vpy()), "-m", "streamlit", "run", str(ROOT / "thunder" / "dashboard" / "app.py"),
               "--server.address", "127.0.0.1", "--server.port", "8501", "--server.headless", "true"], "dashboard")
    for _ in range(60):
        try:
            urllib.request.urlopen(URL, timeout=1)
            break
        except Exception:
            time.sleep(1)
    say(f"Ready: {URL}  (you can close this window; THUNDER keeps running. Use STOP_THUNDER to stop it.)")
    webbrowser.open(URL)


def stop() -> None:
    for name in ("dashboard", "engine"):
        pid = pid_of(name)
        if pid:
            say(f"Stopping {name}…")
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
                else:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
            except OSError:
                pass
        (DATA / f"{name}.pid").unlink(missing_ok=True)
    say("THUNDER stopped.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "stop":
        stop()
    else:
        start(demo="--demo" in sys.argv)
