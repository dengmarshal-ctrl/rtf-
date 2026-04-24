#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_DIR="$SCRIPT_DIR/input_docs"
OUTPUT_DIR="$SCRIPT_DIR/output_docs"
VENV_DIR="$SCRIPT_DIR/.venv"

mkdir -p "$INPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "============================================"
echo " 文档页眉页脚清理 - 本地双击版 (macOS/Linux)"
echo "============================================"
echo ""
echo "输入目录: $INPUT_DIR"
echo "输出目录: $OUTPUT_DIR"
echo ""
echo "请把要处理的 .docx/.doc/.rtf 文件放进 input_docs 文件夹。"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未找到 python3，请先安装 Python 3。"
  read -r -p "按回车键退出..."
  exit 1
fi

if ! command -v soffice >/dev/null 2>&1 && ! command -v libreoffice >/dev/null 2>&1; then
  echo "[错误] 未检测到 LibreOffice。"
  echo "请先安装 LibreOffice（用于 .doc/.rtf 转换）。"
  echo ""
  echo "macOS 可使用: brew install --cask libreoffice"
  read -r -p "按回车键退出..."
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "正在创建虚拟环境..."
  python3 -m venv "$VENV_DIR"
fi

echo "正在安装/更新依赖..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"

WORKERS=3
if command -v sysctl >/dev/null 2>&1; then
  CPU_COUNT="$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"
  if [[ "$CPU_COUNT" =~ ^[0-9]+$ ]]; then
    if [ "$CPU_COUNT" -lt 3 ]; then
      WORKERS="$CPU_COUNT"
    elif [ "$CPU_COUNT" -gt 4 ]; then
      WORKERS=4
    else
      WORKERS="$CPU_COUNT"
    fi
  fi
fi
if [ "$WORKERS" -lt 1 ]; then
  WORKERS=1
fi

echo ""
echo "开始处理，workers=$WORKERS ..."
echo ""

"$VENV_DIR/bin/python" "$SCRIPT_DIR/local_gui_app.py"

echo ""
echo "处理完成。结果目录: $OUTPUT_DIR"
echo "清单文件: $OUTPUT_DIR/sanitize_manifest.json"
echo ""
read -r -p "按回车键关闭窗口..."
