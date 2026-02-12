import argparse
import atexit
import os
import shutil
import sys
import tempfile

import streamlit.web.cli as stcli
from services.launcher_service import resolve_path as resolve_path_impl
from services.launcher_service import run_streamlit_with_auto_stop as run_streamlit_with_auto_stop_impl

_TEMP_ENTRY_DIR = None


def resolve_path(path):
    return resolve_path_impl(
        path=path,
        module_file=__file__,
        frozen=getattr(sys, "frozen", False),
        frozen_base=getattr(sys, "_MEIPASS", None),
    )


def _build_frozen_entry_script():
    """
    Build a tiny temporary script as Streamlit entrypoint in frozen mode.
    This keeps packaged app free from shipping project .py source files.
    """
    global _TEMP_ENTRY_DIR
    if _TEMP_ENTRY_DIR and os.path.exists(_TEMP_ENTRY_DIR):
        return os.path.join(_TEMP_ENTRY_DIR, "im_entry.py")

    temp_dir = tempfile.mkdtemp(prefix="im-entry-")
    entry_script = os.path.join(temp_dir, "im_entry.py")
    with open(entry_script, "w", encoding="utf-8") as f:
        f.write("import im_app  # noqa: F401\n")

    _TEMP_ENTRY_DIR = temp_dir

    def _cleanup():
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    atexit.register(_cleanup)
    return entry_script


def resolve_streamlit_entry_path():
    if getattr(sys, "frozen", False):
        return _build_frozen_entry_script()
    return resolve_path("app.py")


def run_plain_streamlit(port=8501):
    """Run streamlit in the current process (legacy behavior)."""
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    sys.argv = [
        "streamlit",
        "run",
        resolve_streamlit_entry_path(),
        f"--server.port={port}",
    ]
    return stcli.main()


def run_streamlit_with_auto_stop(port=8501, idle_seconds=120, poll_seconds=3):
    app_path = resolve_streamlit_entry_path()
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

    # In frozen executables, child-process mode using "sys.executable -m streamlit"
    # is not reliable because sys.executable points to this app binary itself.
    frozen = bool(getattr(sys, "frozen", False))
    if frozen or args.no_auto_stop or shutil.which("lsof") is None:
        if frozen:
            print("Frozen app detected, using legacy mode (no auto-stop).")
        elif not args.no_auto_stop and shutil.which("lsof") is None:
            print("lsof not found, fallback to legacy mode (no auto-stop).")
        sys.exit(run_plain_streamlit(port=args.port))
    sys.exit(
        run_streamlit_with_auto_stop(
            port=args.port,
            idle_seconds=max(args.idle_seconds, 5),
            poll_seconds=max(args.poll_seconds, 1),
        )
    )
