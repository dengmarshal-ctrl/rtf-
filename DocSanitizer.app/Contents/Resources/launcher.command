#!/usr/bin/env bash
set -euo pipefail

APP_RESOURCES_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="$APP_RESOURCES_DIR/local_gui_app.py"
LOG_DIR="$HOME/Library/Logs/DocSanitizer"
LAUNCH_LOG="$LOG_DIR/launcher.log"
mkdir -p "$LOG_DIR"
exec >>"$LAUNCH_LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] launcher start"

if [ ! -f "$SCRIPT_PATH" ]; then
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display dialog "应用包缺少 local_gui_app.py，请重新下载完整应用。" buttons {"确定"} default button "确定" with icon caution'
  else
    echo "应用包缺少 local_gui_app.py，请重新下载完整应用。"
  fi
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display dialog "未检测到 python3，请先安装 Python 3。" buttons {"确定"} default button "确定" with icon caution'
  else
    echo "未检测到 python3，请先安装 Python 3。"
  fi
  exit 1
fi

export DOCSANITIZER_DATA_DIR="$HOME/Documents/DocSanitizer"
export DOCSANITIZER_CRASH_LOG="$LOG_DIR/app-crash.log"
export DOCSANITIZER_BATCH_SCRIPT="$APP_RESOURCES_DIR/local_batch_sanitize.py"
export DOCSANITIZER_REQUIREMENTS_FILE="$APP_RESOURCES_DIR/requirements.txt"
export DOCSANITIZER_VENV_PATH="$HOME/Documents/DocSanitizer/.venv"
if python3 "$SCRIPT_PATH"; then
  exit 0
fi

if grep -q "No module named 'tkinter'" "$DOCSANITIZER_CRASH_LOG" 2>/dev/null; then
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display dialog "未检测到 tkinter 图形组件，将自动切换到命令行模式。处理结束后结果仍在 Documents/DocSanitizer/output_docs。" buttons {"确定"} default button "确定" with icon note'
  else
    echo "未检测到 tkinter，自动切换到命令行模式。"
  fi
  exec /bin/bash "$APP_RESOURCES_DIR/cli_fallback.command"
fi

exit 1
