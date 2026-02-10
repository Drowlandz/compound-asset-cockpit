import argparse
import os
import shutil
import signal
import subprocess
import sys
import time

import streamlit.web.cli as stcli


def resolve_path(path):
    if getattr(sys, "frozen", False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)


def run_plain_streamlit():
    """Run streamlit in the current process (legacy behavior)."""
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
    ]
    return stcli.main()


def count_active_clients(port, server_pid):
    """
    Count established TCP peers connected to the streamlit port.
    Uses lsof on macOS.
    """
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:ESTABLISHED"],
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

    peers = set()
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        if pid == server_pid:
            continue
        peers.add(pid)
    return len(peers)


def run_streamlit_with_auto_stop(port=8501, idle_seconds=120, poll_seconds=3):
    """
    Launch streamlit as a child process and stop it after browser disconnect idle timeout.
    """
    app_path = resolve_path("app.py")
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    cmd = [
        sys.executable,
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


def parse_args():
    parser = argparse.ArgumentParser(description="Run IM streamlit app")
    parser.add_argument("--port", type=int, default=8501, help="Streamlit port")
    parser.add_argument(
        "--idle-seconds",
        type=int,
        default=int(os.environ.get("IM_IDLE_SECONDS", "120")),
        help="Auto-stop idle timeout after browser disconnect",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=3,
        help="Connection check interval",
    )
    parser.add_argument(
        "--no-auto-stop",
        action="store_true",
        help="Disable auto-stop and run streamlit in legacy mode",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.no_auto_stop or shutil.which("lsof") is None:
        if not args.no_auto_stop and shutil.which("lsof") is None:
            print("lsof not found, fallback to legacy mode (no auto-stop).")
        sys.exit(run_plain_streamlit())
    sys.exit(
        run_streamlit_with_auto_stop(
            port=args.port,
            idle_seconds=max(args.idle_seconds, 5),
            poll_seconds=max(args.poll_seconds, 1),
        )
    )
