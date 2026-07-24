#!/usr/bin/env bash
set -euo pipefail

LABEL="com.david.equity-data-stack.update"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DEFAULT_DATA_ROOT="${REPO_ROOT}/DATA_ROOT"
DATA_ROOT="${DEFAULT_DATA_ROOT}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  ENV_DATA_ROOT="$(grep -E '^DATA_ROOT=' "${REPO_ROOT}/.env" | tail -n 1 | cut -d= -f2- || true)"
  if [[ -n "${ENV_DATA_ROOT}" ]]; then
    DATA_ROOT="${ENV_DATA_ROOT}"
  fi
fi

case "${DATA_ROOT}" in
  /*) ;;
  ./*) DATA_ROOT="${REPO_ROOT}/${DATA_ROOT#./}" ;;
  *) DATA_ROOT="${REPO_ROOT}/${DATA_ROOT}" ;;
esac

LOG_DIR="${DATA_ROOT}/logs/automation"
mkdir -p "${HOME}/Library/LaunchAgents" "${LOG_DIR}"

if [[ "${1:-install}" == "uninstall" ]]; then
  launchctl bootout "gui/${UID}/${LABEL}" 2>/dev/null || true
  rm -f "${PLIST_PATH}"
  echo "Uninstalled ${LABEL}"
  exit 0
fi

cat >"${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd '${REPO_ROOT}' &amp;&amp; '${REPO_ROOT}/.venv/bin/equity-stack' update</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/update.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/update.err.log</string>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/${UID}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID}" "${PLIST_PATH}"
launchctl enable "gui/${UID}/${LABEL}"

echo "Installed ${LABEL}"
echo "Schedule: daily at 06:30 local time"
echo "Logs: ${LOG_DIR}"
