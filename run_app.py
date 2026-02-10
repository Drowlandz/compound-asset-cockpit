import argparse
import os
import shutil
import sys

import streamlit.web.cli as stcli
from services.launcher_service import resolve_path as resolve_path_impl
from services.launcher_service import run_streamlit_with_auto_stop as run_streamlit_with_auto_stop_impl


def resolve_path(path):
    return resolve_path_impl(
        path=path,
        module_file=__file__,
        frozen=getattr(sys, "frozen", False),
        frozen_base=getattr(sys, "_MEIPASS", None),
    )


def run_plain_streamlit():
    """Run streamlit in the current process (legacy behavior)."""
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
    ]
    return stcli.main()


def run_streamlit_with_auto_stop(port=8501, idle_seconds=120, poll_seconds=3):
    app_path = resolve_path("app.py")
    return run_streamlit_with_auto_stop_impl(
        app_path=app_path,
        python_executable=sys.executable,
        port=port,
        idle_seconds=idle_seconds,
        poll_seconds=poll_seconds,
    )


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
