#!/usr/bin/env python3
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_IMPORT_ERROR = None
except Exception as exc:  # noqa: BLE001
    tk = None
    filedialog = None
    messagebox = None
    ttk = None
    TK_IMPORT_ERROR = exc

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = Path.home() / "Documents" / "DocSanitizer"


def resolve_data_dir() -> Path:
    explicit = os.environ.get("DOCSANITIZER_DATA_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    base_as_text = str(BASE_DIR)
    if ".app/Contents/Resources" in base_as_text or not os.access(BASE_DIR, os.W_OK):
        return DEFAULT_DATA_ROOT
    return BASE_DIR


DATA_DIR = resolve_data_dir()
SCRIPT_PATH = Path(os.environ.get("DOCSANITIZER_BATCH_SCRIPT", BASE_DIR / "local_batch_sanitize.py")).expanduser().resolve()
REQUIREMENTS_PATH = Path(
    os.environ.get("DOCSANITIZER_REQUIREMENTS_FILE", BASE_DIR / "requirements.txt")
).expanduser().resolve()
DEFAULT_INPUT_DIR = DATA_DIR / "input_docs"
DEFAULT_OUTPUT_DIR = DATA_DIR / "output_docs"
VENV_PATH = Path(os.environ.get("DOCSANITIZER_VENV_PATH", DATA_DIR / ".venv")).expanduser().resolve()
CRASH_LOG_PATH = Path(os.environ.get("DOCSANITIZER_CRASH_LOG", DATA_DIR / "app-crash.log")).expanduser().resolve()


def detect_python_bin() -> Path:
    if (VENV_PATH / "bin" / "python").exists():
        return VENV_PATH / "bin" / "python"
    if (VENV_PATH / "Scripts" / "python.exe").exists():
        return VENV_PATH / "Scripts" / "python.exe"
    return detect_system_python_bin()


def detect_system_python_bin() -> Path:
    explicit = os.environ.get("DOCSANITIZER_PYTHON_BIN", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit).resolve()

    if Path(sys.executable).exists():
        return Path(sys.executable).resolve()

    for candidate in (
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
    ):
        path = Path(candidate)
        if path.exists():
            return path

    found = shutil.which("python3")
    if found:
        return Path(found).resolve()
    return Path("python3")


def detect_soffice() -> bool:
    return bool(shutil.which("soffice") or shutil.which("libreoffice"))


def ensure_dirs() -> None:
    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class App(tk.Tk if tk is not None else object):  # type: ignore[misc]
    def __init__(self):
        super().__init__()
        self.title("DocSanitizer 本地应用")
        self.geometry("820x620")
        self.minsize(760, 560)

        self.input_dir = tk.StringVar(value=str(DEFAULT_INPUT_DIR))
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.workers = tk.IntVar(value=2)
        self.retries = tk.IntVar(value=2)
        self.overwrite = tk.BooleanVar(value=True)
        self.recursive = tk.BooleanVar(value=True)
        self.progress_text = tk.StringVar(value="等待开始")
        self.status_text = tk.StringVar(value="就绪")

        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._process: subprocess.Popen | None = None
        self._last_manifest: Path | None = None

        ensure_dirs()
        self._build_ui()
        self.after(150, self._poll_queue)
        self._append_log("欢迎使用 DocSanitizer 本地应用")
        self._append_log(f"数据目录: {DATA_DIR}")
        self._append_log(f"输入目录默认: {self.input_dir.get()}")
        self._append_log(f"输出目录默认: {self.output_dir.get()}")
        self._append_log(f"批处理脚本: {SCRIPT_PATH}")
        self._append_log(f"依赖文件: {REQUIREMENTS_PATH}")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        path_box = ttk.LabelFrame(root, text="目录设置", padding=10)
        path_box.pack(fill=tk.X)

        ttk.Label(path_box, text="输入目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(path_box, textvariable=self.input_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(path_box, text="选择", command=self._pick_input_dir).grid(row=0, column=2, sticky="e")

        ttk.Label(path_box, text="输出目录").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(path_box, textvariable=self.output_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(path_box, text="选择", command=self._pick_output_dir).grid(
            row=1, column=2, sticky="e", pady=(8, 0)
        )

        path_box.columnconfigure(1, weight=1)

        options_box = ttk.LabelFrame(root, text="处理参数", padding=10)
        options_box.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(options_box, text="并发数").grid(row=0, column=0, sticky="w")
        workers_spin = ttk.Spinbox(options_box, from_=1, to=8, textvariable=self.workers, width=8)
        workers_spin.grid(row=0, column=1, sticky="w", padx=(8, 16))

        ttk.Label(options_box, text="失败重试").grid(row=0, column=2, sticky="w")
        retries_spin = ttk.Spinbox(options_box, from_=0, to=5, textvariable=self.retries, width=8)
        retries_spin.grid(row=0, column=3, sticky="w", padx=(8, 16))

        ttk.Checkbutton(options_box, text="递归子目录", variable=self.recursive).grid(row=0, column=4, sticky="w")
        ttk.Checkbutton(options_box, text="覆盖已存在输出", variable=self.overwrite).grid(row=0, column=5, sticky="w", padx=(8, 0))

        for col in range(6):
            options_box.columnconfigure(col, weight=1 if col in (4, 5) else 0)

        action_box = ttk.Frame(root)
        action_box.pack(fill=tk.X, pady=(10, 0))

        self.start_btn = ttk.Button(action_box, text="开始处理", command=self._start)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(action_box, text="停止", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(action_box, text="打开输入目录", command=self._open_input_dir).pack(side=tk.RIGHT)
        ttk.Button(action_box, text="打开输出目录", command=self._open_output_dir).pack(side=tk.RIGHT, padx=(0, 8))

        progress_box = ttk.LabelFrame(root, text="进度", padding=10)
        progress_box.pack(fill=tk.X, pady=(10, 0))

        self.progress_bar = ttk.Progressbar(progress_box, mode="determinate", maximum=100)
        self.progress_bar.pack(fill=tk.X)
        ttk.Label(progress_box, textvariable=self.progress_text).pack(anchor="w", pady=(6, 0))
        ttk.Label(progress_box, textvariable=self.status_text).pack(anchor="w", pady=(2, 0))

        log_box = ttk.LabelFrame(root, text="运行日志", padding=10)
        log_box.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_box, height=18, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{text}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _pick_input_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.input_dir.get())
        if selected:
            self.input_dir.set(selected)

    def _pick_output_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get())
        if selected:
            self.output_dir.set(selected)

    def _open_input_dir(self) -> None:
        self._open_path(Path(self.input_dir.get()))

    def _open_output_dir(self) -> None:
        self._open_path(Path(self.output_dir.get()))

    def _open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["open", str(path)], check=False)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开目录失败", str(exc))

    def _validate(self) -> bool:
        if not SCRIPT_PATH.exists():
            messagebox.showerror("缺少脚本", f"未找到处理脚本: {SCRIPT_PATH}")
            return False
        if not REQUIREMENTS_PATH.exists():
            messagebox.showerror("缺少依赖文件", f"未找到 requirements.txt: {REQUIREMENTS_PATH}")
            return False
        if not detect_soffice():
            messagebox.showerror(
                "缺少 LibreOffice",
                "未检测到 soffice/libreoffice。\n请先安装 LibreOffice 再运行。",
            )
            return False
        if self.workers.get() < 1:
            messagebox.showwarning("参数错误", "并发数必须 >= 1")
            return False
        if self.retries.get() < 0:
            messagebox.showwarning("参数错误", "重试次数不能小于 0")
            return False
        Path(self.input_dir.get()).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir.get()).mkdir(parents=True, exist_ok=True)
        return True

    def _ensure_venv_and_deps(self) -> None:
        python3_bin = detect_system_python_bin()
        if str(python3_bin) == "python3":
            raise RuntimeError("未找到 python3，请先安装 Python 3。")

        python_bin = detect_python_bin()
        if not (VENV_PATH / "bin" / "python").exists() and not (VENV_PATH / "Scripts" / "python.exe").exists():
            self._queue.put(("log", "首次运行：正在创建虚拟环境..."))
            subprocess.run([str(python3_bin), "-m", "venv", str(VENV_PATH)], check=True)
            python_bin = detect_python_bin()

        self._queue.put(("log", "正在安装/更新依赖（首次可能稍慢）..."))
        subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)], check=True)

    def _start(self) -> None:
        if self._running:
            return
        if not self._validate():
            return

        self._running = True
        self._last_manifest = Path(self.output_dir.get()) / "sanitize_manifest.json"
        self.progress_bar["value"] = 0
        self.progress_text.set("准备启动...")
        self.status_text.set("运行中")
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self._append_log("=" * 64)
        self._append_log("任务启动")

        worker = threading.Thread(target=self._run_task, daemon=True)
        worker.start()

    def _stop(self) -> None:
        if self._process and self._running:
            self._append_log("请求停止任务...")
            self._process.terminate()

    def _build_command(self) -> list[str]:
        python_bin = detect_python_bin()
        cmd = [
            str(python_bin),
            str(SCRIPT_PATH),
            "--input-dir",
            self.input_dir.get(),
            "--output-dir",
            self.output_dir.get(),
            "--workers",
            str(self.workers.get()),
            "--retries",
            str(self.retries.get()),
            "--overwrite" if self.overwrite.get() else "",
            "--recursive" if self.recursive.get() else "",
        ]
        return [arg for arg in cmd if arg]

    def _run_task(self) -> None:
        try:
            self._ensure_venv_and_deps()
            cmd = self._build_command()
            self._queue.put(("log", f"执行命令: {' '.join(cmd)}"))
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert self._process.stdout is not None
            for line in self._process.stdout:
                line = line.rstrip()
                self._queue.put(("log", line))
                self._queue.put(("parse_progress", line))

            exit_code = self._process.wait()
            if exit_code == 0:
                self._queue.put(("done", "success"))
            else:
                self._queue.put(("done", f"failed:{exit_code}"))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("done", f"error:{exc}"))
        finally:
            self._process = None

    def _parse_progress(self, line: str) -> None:
        if line.startswith("[") and "/" in line:
            try:
                prefix = line.split("]", 1)[0].strip("[")
                current, total = prefix.split("/", 1)
                current_num = int(current)
                total_num = int(total)
                if total_num > 0:
                    percent = int((current_num / total_num) * 100)
                    self.progress_bar["value"] = percent
                    self.progress_text.set(f"处理中: {current_num}/{total_num} ({percent}%)")
            except Exception:
                return
        elif line.startswith("- 成功:") or line.startswith("- 失败:") or line.startswith("- 跳过:"):
            self.status_text.set(line)

    def _on_done(self, result: str) -> None:
        self._running = False
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.progress_bar["value"] = 100 if result == "success" else self.progress_bar["value"]

        if result == "success":
            self.progress_text.set("处理完成")
            self.status_text.set("全部任务完成")
            self._append_log("任务完成")
            if self._last_manifest and self._last_manifest.exists():
                try:
                    data = json.loads(self._last_manifest.read_text(encoding="utf-8"))
                    summary = data.get("summary", {})
                    msg = (
                        f"完成。\n成功: {summary.get('success', 0)}\n"
                        f"失败: {summary.get('failed', 0)}\n"
                        f"输出目录: {self.output_dir.get()}"
                    )
                    messagebox.showinfo("处理完成", msg)
                except Exception:
                    messagebox.showinfo("处理完成", f"输出目录: {self.output_dir.get()}")
        else:
            self.progress_text.set("处理结束（含失败）")
            self.status_text.set(result)
            self._append_log(f"任务结束: {result}")
            messagebox.showwarning(
                "处理结束",
                "任务已结束但存在失败项。\n请查看日志与 sanitize_manifest.json。",
            )

    def _poll_queue(self) -> None:
        while True:
            try:
                event, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if event == "log":
                self._append_log(payload)
            elif event == "parse_progress":
                self._parse_progress(payload)
            elif event == "done":
                self._on_done(payload)
        self.after(150, self._poll_queue)


def main() -> int:
    try:
        if TK_IMPORT_ERROR is not None:
            raise RuntimeError(f"无法加载 tkinter 图形组件: {TK_IMPORT_ERROR}")
        app = App()
        app.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001
        details = traceback.format_exc()
        CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CRASH_LOG_PATH.write_text(details, encoding="utf-8")
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    (
                        'display alert "DocSanitizer 启动失败" '
                        f'message "错误信息已写入: {CRASH_LOG_PATH}" as critical'
                    ),
                ],
                check=False,
            )
        except Exception:
            pass
        print(f"DocSanitizer 启动失败: {exc}", file=sys.stderr)
        print(details, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
