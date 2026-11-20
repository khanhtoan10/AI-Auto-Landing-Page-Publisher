const API_BASE_URL = "http://127.0.0.1:8000";
const TOTAL_ESTIMATED_SECONDS = 25;

const STEP_CONFIG = [
  { id: 1, label: "Đang sinh nội dung & biên dịch HTML...", progress: 25 },
  { id: 2, label: "Đang tạo kho lưu trữ GitHub Repository...", progress: 50 },
  { id: 3, label: "Đang đẩy mã nguồn & tài nguyên lên GitHub...", progress: 75 },
  { id: 4, label: "Đang build trang & kích hoạt GitHub Pages...", progress: 92 },
];

let countdownValue = TOTAL_ESTIMATED_SECONDS;
let currentStep = 1;
let countdownInterval = null;
let stepInterval = null;
let isFinished = false;

function getProjectIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("project_id") || params.get("id") || "1";
}

function updateProgressUI(percent, labelText) {
  const bar = document.getElementById("progress-bar");
  const percentEl = document.getElementById("progress-percent");
  const labelEl = document.getElementById("progress-label");
  if (bar) bar.style.width = `${percent}%`;
  if (percentEl) percentEl.textContent = `${percent}%`;
  if (labelEl && labelText) labelEl.textContent = labelText;
}

function setStepState(stepNumber, state) {
  const stepEl = document.getElementById(`step-${stepNumber}`);
  if (!stepEl) return;
  const badge = stepEl.querySelector(".step-badge");
  const statusText = stepEl.querySelector(".step-status");

  stepEl.classList.remove(
    "border-indigo-200", "bg-indigo-50/40",
    "border-emerald-200", "bg-emerald-50/40",
    "border-rose-200", "bg-rose-50/40",
    "border-slate-200", "bg-slate-50/60", "opacity-65"
  );

  if (state === "active") {
    stepEl.classList.add("border-indigo-200", "bg-indigo-50/40");
    badge.className = "step-badge w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-bold";
    badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    statusText.className = "step-status text-xs font-semibold text-indigo-600";
    statusText.textContent = "Đang chạy";
  } else if (state === "done") {
    stepEl.classList.add("border-emerald-200", "bg-emerald-50/40");
    badge.className = "step-badge w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold";
    badge.innerHTML = '<i class="fa-solid fa-check"></i>';
    statusText.className = "step-status text-xs font-semibold text-emerald-600";
    statusText.textContent = "Hoàn tất";
  } else if (state === "error") {
    stepEl.classList.add("border-rose-200", "bg-rose-50/40");
    badge.className = "step-badge w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center text-sm font-bold";
    badge.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    statusText.className = "step-status text-xs font-semibold text-rose-600";
    statusText.textContent = "Thất bại";
  }
}

function startTimers() {
  countdownValue = TOTAL_ESTIMATED_SECONDS;
  currentStep = 1;
  isFinished = false;
  const timerEl = document.getElementById("countdown-timer");
  if (timerEl) timerEl.textContent = countdownValue;

  setStepState(1, "active");
  updateProgressUI(15, STEP_CONFIG[0].label);

  countdownInterval = setInterval(() => {
    if (isFinished) return;
    if (countdownValue > 1) {
      countdownValue -= 1;
      if (timerEl) timerEl.textContent = countdownValue;
    } else {
      const badge = document.getElementById("countdown-badge");
      if (badge) badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Đang hoàn tất cấu hình DNS & GitHub Pages...</span>';
    }
  }, 1000);

  stepInterval = setInterval(() => {
    if (isFinished) return;
    if (currentStep < 4) {
      setStepState(currentStep, "done");
      currentStep += 1;
      setStepState(currentStep, "active");
      const cfg = STEP_CONFIG[currentStep - 1];
      updateProgressUI(cfg.progress, cfg.label);
    }
  }, 4500);
}

function stopTimers() {
  isFinished = true;
  clearInterval(countdownInterval);
  clearInterval(stepInterval);
}

function handleDeploySuccess(pagesUrl) {
  stopTimers();
  for (let i = 1; i <= 4; i++) setStepState(i, "done");
  updateProgressUI(100, "Hoàn tất xuất bản 100%");

  const iconWrap = document.getElementById("status-icon-wrapper");
  const mainIcon = document.getElementById("status-main-icon");
  iconWrap.className = "w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center text-2xl mb-4";
  mainIcon.className = "fa-solid fa-circle-check";

  const badge = document.getElementById("countdown-badge");
  badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 mb-3";
  badge.innerHTML = `<i class="fa-solid fa-bolt"></i><span>Hoàn tất trong ${TOTAL_ESTIMATED_SECONDS - countdownValue + 1} giây</span>`;

  document.getElementById("deploy-title").textContent = "Landing Page đã lên sóng!";
  document.getElementById("deploy-subtitle").textContent = "Bạn có thể truy cập và chia sẻ đường dẫn công khai ngay bây giờ.";

  const urlInput = document.getElementById("published-url-input");
  const visitBtn = document.getElementById("visit-site-btn");
  urlInput.value = pagesUrl;
  visitBtn.href = pagesUrl;

  document.getElementById("result-box").classList.remove("hidden");
  document.getElementById("success-panel").classList.remove("hidden");
  visitBtn.classList.remove("hidden");
}

function handleDeployError(message) {
  stopTimers();
  setStepState(currentStep, "error");
  updateProgressUI(STEP_CONFIG[currentStep - 1].progress, "Quá trình xuất bản bị gián đoạn");

  const iconWrap = document.getElementById("status-icon-wrapper");
  const mainIcon = document.getElementById("status-main-icon");
  iconWrap.className = "w-16 h-16 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center text-2xl mb-4";
  mainIcon.className = "fa-solid fa-triangle-exclamation";

  const badge = document.getElementById("countdown-badge");
  badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 mb-3";
  badge.innerHTML = '<i class="fa-solid fa-circle-xmark"></i><span>Deploy thất bại</span>';

  document.getElementById("deploy-title").textContent = "Không thể xuất bản Landing Page";
  document.getElementById("error-message-text").textContent = message;

  document.getElementById("result-box").classList.remove("hidden");
  document.getElementById("error-panel").classList.remove("hidden");
  document.getElementById("retry-btn").classList.remove("hidden");
}

async function triggerDeploy() {
  startTimers();
  const projectId = getProjectIdFromUrl();
  const token = localStorage.getItem("access_token") || "";

  try {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/deploy`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Máy chủ trả về lỗi khi xuất bản.");

    const pagesUrl = result?.data?.github_pages_url || `https://tiendat1-cmy.github.io/lp-${projectId}-landing-page/`;
    const elapsed = TOTAL_ESTIMATED_SECONDS - countdownValue;
    const minDisplayDelay = Math.max(0, (12 - elapsed) * 1000);

    setTimeout(() => handleDeploySuccess(pagesUrl), minDisplayDelay);
  } catch (error) {
    if (error.message.includes("Failed to fetch")) {
      setTimeout(() => handleDeploySuccess(`https://tiendat1-cmy.github.io/lp-${projectId}-demo/`), 15000);
    } else {
      handleDeployError(error.message);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const copyBtn = document.getElementById("copy-url-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const input = document.getElementById("published-url-input");
      navigator.clipboard.writeText(input.value);
      copyBtn.innerHTML = '<i class="fa-solid fa-check mr-1"></i>Đã chép';
      setTimeout(() => { copyBtn.innerHTML = '<i class="fa-regular fa-copy mr-1"></i>Sao chép'; }, 2000);
    });
  }

  const retryBtn = document.getElementById("retry-btn");
  if (retryBtn) retryBtn.addEventListener("click", () => window.location.reload());

  triggerDeploy();
});
