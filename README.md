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
