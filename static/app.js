const CHUNK_SIZE = 8 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".docx", ".doc", ".rtf"];
const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024;
const RETRY_DELAYS = [700, 1400, 2800];

const state = {
  files: [],
  jobId: "",
  busy: false,
};

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const pickFilesBtn = document.getElementById("pick-files-btn");
const startBtn = document.getElementById("start-btn");
const fileList = document.getElementById("file-list");
const globalProgressBar = document.getElementById("global-progress-bar");
const globalProgressText = document.getElementById("global-progress-text");
const jobSummary = document.getElementById("job-summary");
const downloadSection = document.getElementById("download-section");
const downloadBtn = document.getElementById("download-btn");
const toast = document.getElementById("toast");

function maskFilename(fileName) {
  const dotIndex = fileName.lastIndexOf(".");
  const stem = dotIndex >= 0 ? fileName.slice(0, dotIndex) : fileName;
  const ext = dotIndex >= 0 ? fileName.slice(dotIndex) : "";
  if (stem.length <= 1) return `*${ext}`;
  if (stem.length === 2) return `${stem[0]}*${ext}`;
  return `${stem[0]}${"*".repeat(stem.length - 2)}${stem[stem.length - 1]}${ext}`;
}

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let i = 1; i < units.length && value >= 1024; i += 1) {
    value /= 1024;
    unit = units[i];
  }
  return `${value.toFixed(2)} ${unit}`;
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function showToast(message, error = false) {
  toast.textContent = message;
  toast.className = `toast ${error ? "error" : "ok"}`;
  window.setTimeout(() => {
    toast.className = "toast";
  }, 2600);
}

function validFile(file) {
  const lowerName = file.name.toLowerCase();
  const validExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  if (!validExt) return "仅支持 .docx / .doc / .rtf";
  if (file.size <= 0) return "文件为空";
  if (file.size > MAX_FILE_SIZE) return "单个文件不能超过 2GB";
  return "";
}

function renderFiles() {
  fileList.innerHTML = "";
  state.files.forEach((item) => {
    const row = document.createElement("div");
    row.className = "file-row";
    row.innerHTML = `
      <div class="file-meta">
        <span class="name">${item.maskedName}</span>
        <span>${humanSize(item.file.size)}</span>
      </div>
      <div class="status">${item.statusText} | ${item.message || "待处理"}</div>
      <div class="progress-wrap">
        <div class="progress-bar">
          <div class="progress-value" style="width:${item.progress}%"></div>
        </div>
        <div class="progress-text">${item.progress}%</div>
      </div>
    `;
    fileList.appendChild(row);
  });
  const canStart = state.files.length > 0 && !state.busy;
  startBtn.disabled = !canStart;
}

function addFiles(fileList) {
  const existing = new Set(state.files.map((f) => `${f.file.name}:${f.file.size}`));
  let added = 0;
  Array.from(fileList).forEach((file) => {
    const key = `${file.name}:${file.size}`;
    if (existing.has(key)) return;
    const validationError = validFile(file);
    if (validationError) {
      showToast(`${maskFilename(file.name)}: ${validationError}`, true);
      return;
    }
    state.files.push({
      file,
      maskedName: maskFilename(file.name),
      statusText: "等待上传",
      progress: 0,
      message: "",
      uploadId: "",
      fileId: "",
    });
    existing.add(key);
    added += 1;
  });
  if (added > 0) {
    showToast(`已添加 ${added} 个文件`);
  }
  renderFiles();
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `请求失败: ${response.status}`);
  }
  return payload;
}

async function requestWithRetry(url, options = {}) {
  let lastError = null;
  const maxAttempts = RETRY_DELAYS.length + 1;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await requestJson(url, options);
    } catch (error) {
      lastError = error;
      if (attempt === maxAttempts) {
        break;
      }
      await sleep(RETRY_DELAYS[attempt - 1]);
    }
  }
  throw lastError || new Error("请求失败");
}

async function initUpload(item, totalChunks) {
  const payload = await requestWithRetry("/api/upload/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: item.file.name,
      size: item.file.size,
      chunk_size: CHUNK_SIZE,
      total_chunks: totalChunks,
    }),
  });
  item.uploadId = payload.upload_id;
}

async function uploadSingleChunk(uploadId, index, blob) {
  const form = new FormData();
  form.append("upload_id", uploadId);
  form.append("chunk_index", String(index));
  form.append("chunk", blob, `part-${index}.bin`);
  return requestWithRetry("/api/upload/chunk", {
    method: "POST",
    body: form,
  });
}

async function completeUpload(item) {
  const payload = await requestWithRetry("/api/upload/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: item.uploadId }),
  });
  item.fileId = payload.file_id;
}

async function uploadOneFile(item) {
  item.statusText = "初始化上传";
  item.progress = 1;
  renderFiles();

  const totalChunks = Math.ceil(item.file.size / CHUNK_SIZE);
  await initUpload(item, totalChunks);

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    const start = chunkIndex * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, item.file.size);
    const chunkBlob = item.file.slice(start, end);
    await uploadSingleChunk(item.uploadId, chunkIndex, chunkBlob);
    const uploadPercent = Math.round(((chunkIndex + 1) / totalChunks) * 100);
    item.statusText = "上传中";
    item.progress = Math.min(uploadPercent, 99);
    renderFiles();
  }

  await completeUpload(item);
  item.statusText = "上传完成";
  item.message = "等待批量处理";
  item.progress = 100;
  renderFiles();
}

function updateOverallProgress(value) {
  const safe = Math.max(0, Math.min(100, value));
  globalProgressBar.style.width = `${safe}%`;
  globalProgressText.textContent = `${safe}%`;
}

async function uploadAll() {
  for (const item of state.files) {
    item.message = "";
  }
  renderFiles();
  updateOverallProgress(0);
  let completed = 0;

  for (const item of state.files) {
    try {
      await uploadOneFile(item);
      completed += 1;
      updateOverallProgress(Math.round((completed / state.files.length) * 45));
    } catch (error) {
      item.statusText = "上传失败";
      item.message = error.message;
      item.progress = 100;
      renderFiles();
      throw error;
    }
  }
}

async function startJob(fileIds) {
  const payload = await requestWithRetry("/api/jobs/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_ids: fileIds }),
  });
  return payload.job_id;
}

function syncFileStatusFromJob(files) {
  const map = new Map(files.map((f) => [f.file_id, f]));
  state.files.forEach((item) => {
    if (!item.fileId || !map.has(item.fileId)) return;
    const serverData = map.get(item.fileId);
    item.statusText =
      serverData.status === "processing"
        ? "处理中"
        : serverData.status === "done"
        ? "处理完成"
        : serverData.status === "failed"
        ? "处理失败"
        : "排队中";
    item.progress = serverData.progress;
    item.message = serverData.message;
  });
}

async function pollJobStatus(jobId) {
  while (true) {
    const status = await requestWithRetry(`/api/jobs/${jobId}`);
    syncFileStatusFromJob(status.files);
    renderFiles();

    const processPart = Math.round((status.overall_progress / 100) * 55);
    updateOverallProgress(45 + processPart);
    jobSummary.textContent = `总数 ${status.total}，成功 ${status.done}，失败 ${status.failed}`;

    if (status.download_ready) {
      downloadSection.classList.remove("hidden");
      updateOverallProgress(100);
      showToast("处理完成，可下载结果包");
      break;
    }
    await sleep(1200);
  }
}

async function handleStart() {
  if (state.files.length === 0 || state.busy) {
    showToast("请先选择文件", true);
    return;
  }

  state.busy = true;
  startBtn.disabled = true;
  startBtn.textContent = "处理中...";
  downloadSection.classList.add("hidden");
  jobSummary.textContent = "开始上传";
  updateOverallProgress(0);

  try {
    await uploadAll();
    const ids = state.files.map((item) => item.fileId).filter(Boolean);
    state.jobId = await startJob(ids);
    jobSummary.textContent = "上传完成，正在处理文档";
    await pollJobStatus(state.jobId);
  } catch (error) {
    showToast(error.message, true);
    jobSummary.textContent = "任务失败，请检查文件后重试";
  } finally {
    state.busy = false;
    startBtn.disabled = false;
    startBtn.textContent = "开始批量处理";
    renderFiles();
  }
}

function preventDefaults(event) {
  event.preventDefault();
  event.stopPropagation();
}

["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, preventDefaults, false);
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, () => dropZone.classList.add("dragover"), false);
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, () => dropZone.classList.remove("dragover"), false);
});

dropZone.addEventListener("drop", (event) => {
  const files = event.dataTransfer?.files || [];
  addFiles(files);
});

pickFilesBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (event) => {
  addFiles(event.target.files || []);
  fileInput.value = "";
});
startBtn.addEventListener("click", handleStart);
downloadBtn.addEventListener("click", () => {
  if (!state.jobId) return;
  window.location.href = `/api/jobs/${state.jobId}/download`;
});

renderFiles();
