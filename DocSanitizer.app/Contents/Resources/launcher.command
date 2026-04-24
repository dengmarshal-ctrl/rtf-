#!/usr/bin/env bash
set -euo pipefail

APP_RESOURCES_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$APP_RESOURCES_DIR/../../.." && pwd)"
SCRIPT_PATH="$REPO_DIR/run_local_macos.command"

if [ ! -f "$SCRIPT_PATH" ]; then
  osascript -e 'display dialog "未找到 run_local_macos.command，请确保 .app 与脚本在同一项目目录中。" buttons {"确定"} default button "确定" with icon caution'
  exit 1
fi

chmod +x "$SCRIPT_PATH" || true
exec "$SCRIPT_PATH"
