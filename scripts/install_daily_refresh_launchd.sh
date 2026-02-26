#!/usr/bin/env bash
set -euo pipefail

LABEL="com.rowland.im.daily_refresh"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
RUN_HOUR="${RUN_HOUR:-23}"
RUN_MINUTE="${RUN_MINUTE:-0}"

PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/${LABEL}.plist"
LOG_DIR="${PROJECT_DIR}/logs"

mkdir -p "${PLIST_DIR}" "${LOG_DIR}"

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${PROJECT_DIR}/daily_refresh.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${RUN_HOUR}</integer>
        <key>Minute</key>
        <integer>${RUN_MINUTE}</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/daily_refresh.out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/daily_refresh.err.log</string>
</dict>
</plist>
PLIST

launchctl unload "${PLIST_PATH}" >/dev/null 2>&1 || true
launchctl load "${PLIST_PATH}"

cat <<MSG
Installed launchd job: ${LABEL}
Plist: ${PLIST_PATH}
Schedule: daily at ${RUN_HOUR}:${RUN_MINUTE}
Logs:
  ${LOG_DIR}/daily_refresh.out.log
  ${LOG_DIR}/daily_refresh.err.log

Useful commands:
  launchctl list | rg ${LABEL}
  launchctl unload ${PLIST_PATH}
MSG
