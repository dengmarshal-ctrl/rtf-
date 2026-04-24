#!/usr/bin/env bash
set -euo pipefail

APP_RESOURCES_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$APP_RESOURCES_DIR/../../.." && pwd)"
SCRIPT_PATH="$REPO_DIR/local_gui_app.py"

if [ ! -f "$SCRIPT_PATH" ]; then
  osascript -e 'display dialog "未找到 local_gui_app.py，请确保 .app 与项目在同一目录。" buttons {"确定"} default button "确定" with icon caution'
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "未检测到 python3，请先安装 Python 3。" buttons {"确定"} default button "确定" with icon caution'
  exit 1
fi

exec python3 "$SCRIPT_PATH"
