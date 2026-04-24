@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"
title 本地批量清理页眉页脚（Windows）

echo.
echo =============================================
echo   本地批量清理页眉页脚（.docx/.doc/.rtf）
echo =============================================
echo.

if not exist "input_docs" mkdir "input_docs"
if not exist "output_docs" mkdir "output_docs"

echo 请先把要处理的文件放到：input_docs 文件夹
echo 处理结果会输出到：output_docs 文件夹
echo.
pause

if exist ".venv\Scripts\python.exe" goto VENV_READY

echo [1/4] 正在创建 Python 虚拟环境...
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m venv ".venv"
) else (
  python -m venv ".venv"
)
if errorlevel 1 (
  echo.
  echo [错误] 创建虚拟环境失败。请先安装 Python 3（并勾选 Add to PATH）。
  pause
  exit /b 1
)

:VENV_READY
echo [2/4] 正在安装依赖（首次会稍慢）...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [错误] 依赖安装失败，请检查网络后重试。
  pause
  exit /b 1
)

where soffice >nul 2>nul
if errorlevel 1 (
  echo.
  echo [提示] 未检测到 soffice（LibreOffice）。
  echo      .doc/.rtf 处理依赖 LibreOffice，未安装时可能失败。
  echo      下载地址: https://www.libreoffice.org/download/download-libreoffice/
  echo.
)

set WORKERS=4
set /p INPUT_WORKERS=请输入并发数（直接回车=4）:
if not "%INPUT_WORKERS%"=="" set WORKERS=%INPUT_WORKERS%

echo.
echo [3/4] 开始处理，请稍候...
".venv\Scripts\python.exe" local_batch_sanitize.py ^
  --input-dir "%cd%\input_docs" ^
  --output-dir "%cd%\output_docs" ^
  --workers %WORKERS% ^
  --recursive ^
  --overwrite

set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE%==0 (
  echo [4/4] 处理完成，全部成功。
) else (
  echo [4/4] 处理完成，但存在失败项。请查看 output_docs\sanitize_manifest.json
)
echo.
echo 结果目录：%cd%\output_docs
pause
exit /b %EXIT_CODE%
