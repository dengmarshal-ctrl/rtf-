# 文档页眉页脚清理工具

一个可交互的 Web 脚本，支持用户拖拽/选择本地文件上传，批量移除 `.docx` / `.doc` / `.rtf` 文档中的页眉页脚内容，并下载处理结果。

## 功能特性

- 支持批量上传与批量处理
- 支持大文件（100MB+）分片上传（默认 8MB/片）
- 支持 `.docx`、`.doc`、`.rtf`
- 处理进度脱敏展示（文件名遮蔽显示）
- 失败重试与错误隔离（单文件失败不影响其他文件）
- 处理完成后打包下载 ZIP（附带 `manifest.json`）

## 技术实现

- 后端：Flask
- 文档处理：
  - `.docx`：python-docx 直接移除各 section 的 header/footer 内容
  - `.doc` / `.rtf`：经 LibreOffice 转为 `.docx` 后处理，再转换回原格式
- 前端：原生 HTML/CSS/JavaScript（支持拖拽 + 文件选择器）

## 运行环境

1. Python 3.10+
2. LibreOffice（必须，处理 `.doc` / `.rtf` 依赖）

Ubuntu/Debian 安装 LibreOffice 示例：

```bash
sudo apt-get update
sudo apt-get install -y libreoffice
```

## 启动步骤

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

默认访问地址：`http://127.0.0.1:8000`

## 接口说明（核心）

- `POST /api/upload/init`：初始化上传任务（返回 upload_id）
- `POST /api/upload/chunk`：上传分片
- `POST /api/upload/complete`：通知服务端合并文件
- `POST /api/jobs/start`：开始批量清理任务
- `GET /api/jobs/<job_id>`：查询批量任务进度
- `GET /api/jobs/<job_id>/download`：下载处理结果 ZIP

## 稳定性设计

- 分片上传 + 服务端合并，避免大文件一次性请求导致失败
- 前端请求重试（指数退避）
- 后端文件大小、分片范围、完整性校验
- 任务异步处理，避免阻塞上传请求
- 单文件失败隔离，整体任务可继续执行

## 本地脚本版（推荐处理大量 RTF）

如果你有大量文件（尤其是 `.rtf`），建议直接在本地机器运行脚本，不走网页上传链路，速度和稳定性都会更好。

### 脚本文件

- `local_batch_sanitize.py`

### 主要能力

- 批量递归扫描目录下 `.docx/.doc/.rtf`
- 并发处理（可配置 worker 数）
- 实时显示处理进度、成功/失败统计
- 产出 `sanitize_manifest.json` 便于复盘失败原因

### 本地运行示例

```bash
python3 -m pip install -r requirements.txt

# 扫描 input_docs 目录，输出到 output_docs，使用 4 个并发进程
python3 local_batch_sanitize.py \
  --input-dir ./input_docs \
  --output-dir ./output_docs \
  --workers 4
```

### 双击即用（不用命令行）

仓库里已提供两个双击脚本：

- Windows：`run_local_windows.bat`
- macOS：`run_local_macos.command`

#### 使用步骤（Windows / macOS 通用）

1. 把待处理文件放到 `input_docs` 文件夹（脚本会自动创建）。
2. 双击对应脚本：
   - Windows 双击 `run_local_windows.bat`
   - macOS 双击 `run_local_macos.command`
3. 等待脚本执行完成，结果在 `output_docs` 目录。
4. 处理清单在 `output_docs/sanitize_manifest.json`。

首次运行会自动安装 Python 依赖，时间会稍长一些。

### macOS 一键应用（.app）

如果你不想手动跑命令，直接使用仓库内的应用包：

- `DocSanitizer.app`

使用方式：

1. 把整个项目文件夹放在本地（不要只拷贝 `.app`）。
2. 把待处理文件放到项目内 `input_docs` 文件夹。
3. 双击 `DocSanitizer.app`。
4. 程序会自动打开 Terminal 执行处理流程。
5. 结果在 `output_docs`，清单在 `output_docs/sanitize_manifest.json`。

> 首次打开若出现“无法验证开发者”提示：系统设置 -> 隐私与安全性 -> 允许打开，或右键应用选择“打开”。

可选参数：

- `--recursive`：递归扫描子目录（默认仅扫描当前目录）
- `--workers`：并发进程数，默认 `min(4, CPU核心数)`
- `--overwrite`：覆盖已存在输出文件
- `--retries`：单文件失败后重试次数（默认 1）

### 性能建议

- 大批量 `.rtf`/`.doc` 会走 LibreOffice 转换，建议在本地 SSD 目录运行
- 若出现少量 `rtf -> docx` 转换失败，优先把并发降到 `2~4` 再重跑失败文件
- `--workers` 可从 `2~6` 试起，观察 CPU 和内存占用
- 若只处理 `.docx`，速度通常会明显快于 `.rtf/.doc`
