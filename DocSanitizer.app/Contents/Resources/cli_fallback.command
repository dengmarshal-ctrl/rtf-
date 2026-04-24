#!/usr/bin/env bash
set -euo pipefail

APP_RESOURCES_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${DOCSANITIZER_DATA_DIR:-$HOME/Documents/DocSanitizer}"
INPUT_DIR="$DATA_DIR/input_docs"
OUTPUT_DIR="$DATA_DIR/output_docs"
VENV_DIR="${DOCSANITIZER_VENV_PATH:-$DATA_DIR/.venv}"
REQUIREMENTS_FILE="${DOCSANITIZER_REQUIREMENTS_FILE:-$APP_RESOURCES_DIR/requirements.txt}"
BATCH_SCRIPT="${DOCSANITIZER_BATCH_SCRIPT:-$APP_RESOURCES_DIR/local_batch_sanitize.py}"

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR"

echo "DocSanitizer 已切换到兼容模式（终端）。"
echo "输入目录: $INPUT_DIR"
echo "输出目录: $OUTPUT_DIR"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未检测到 python3，请先安装 Python 3。"
  exit 1
fi

if ! command -v soffice >/dev/null 2>&1 && ! command -v libreoffice >/dev/null 2>&1; then
  echo "[错误] 未检测到 LibreOffice（soffice），请先安装后再试。"
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS_FILE"

WORKERS=3
"$VENV_DIR/bin/python" "$BATCH_SCRIPT" \
  --input-dir "$INPUT_DIR" \
  --output-dir "$OUTPUT_DIR" \
  --workers "$WORKERS" \
  --retries 2 \
  --recursive \
  --overwrite

echo ""
echo "处理完成。结果目录: $OUTPUT_DIR"
echo "清单文件: $OUTPUT_DIR/sanitize_manifest.json"
