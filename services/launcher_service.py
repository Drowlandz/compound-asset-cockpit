from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Optional


def resolve_path(path: str, module_file: str, frozen: bool, frozen_base: Optional[str] = None) -> str:
    if frozen and frozen_base:
        basedir = frozen_base
    else:
        basedir = os.path.dirname(os.path.abspath(module_file))
    return os.path.join(basedir, path)


def count_active_clients(port: int, server_pid: int) -> Optional[int]:
    """
    Count established TCP peers connected to the streamlit port.
    Uses lsof on macOS.
    """
    try:
        result = subprocess.run(
            [
                "lsof",
                "-nP",
                "-a",
                "-p",
                str(server_pid),
                f"-iTCP:{port}",
                "-sTCP:ESTABLISHED",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    if result.returncode not in (0, 1):
        return None

    output = (result.stdout or "").strip()
    if not output:
        return 0

    lines = output.splitlines()
    if len(lines) <= 1:
        return 0
    return len(lines) - 1


def run_streamlit_with_auto_stop(
    app_path: str,
    python_executable: str,
    port: int = 8501,
    idle_seconds: int = 120,
    poll_seconds: int = 3,
) -> int:
    """
    Launch streamlit as a child process and stop it after browser disconnect idle timeout.
    """
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    cmd = [
        python_executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        f"--server.port={port}",
    ]
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(app_path), env=env)
    print(f"Streamlit started at http://localhost:{port} (PID {proc.pid})")
    print(f"Auto-stop enabled: idle {idle_seconds}s after last browser connection.")

    first_client_seen = False
    last_active_ts = time.monotonic()

    try:
        while proc.poll() is None:
            active_clients = count_active_clients(port, proc.pid)
            if active_clients is None:
                time.sleep(poll_seconds)
                continue

            now = time.monotonic()
            if active_clients > 0:
                if not first_client_seen:
                    print(f"Browser connected (connections={active_clients}).")
                first_client_seen = True
                last_active_ts = now
            elif first_client_seen and (now - last_active_ts) >= idle_seconds:
                print("No browser connection detected, stopping streamlit...")
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break

            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 130

    return proc.returncode if proc.returncode is not None else 0
