/**
 * Trang tiến trình xuất bản Landing Page.
 *
 * Luồng thật:
 *   1. GET  /projects/{id}         – lấy tên dự án để hiển thị.
 *   2. POST /projects/{id}/deploy  – render, tạo repo, push GitHub, bật Pages.
 *
 * Progress bar chỉ là mô phỏng thời gian chờ; trạng thái thành công/thất bại
 * hoàn toàn phụ thuộc vào response thật của backend (không còn fallback giả).
 */
(function () {
  "use strict";

  const TOTAL_STEPS = 4;
  const STEP_PROGRESS = [18, 38, 62, 84];

  const state = {
    projectId: null,
    projectName: "",
    deploying: false,
    elapsed: 0,
    currentStep: 1,
    elapsedTimer: null,
    progressTimer: null,
    stepTimers: [],
  };

  const $ = (id) => document.getElementById(id);

  function getProjectIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("project_id") || params.get("id") || "";
  }

  function updateProgressUI(percent, labelText) {
    const bar = $("progress-bar");
    const percentEl = $("progress-percent");
    const labelEl = $("progress-label");
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    if (percentEl) percentEl.textContent = `${Math.round(percent)}%`;
    if (labelEl && labelText) labelEl.textContent = labelText;
  }

  function setStepState(stepNumber, stepState) {
    const stepEl = $(`step-${stepNumber}`);
    if (!stepEl) return;
    const badge = stepEl.querySelector(".step-badge");
    const statusText = stepEl.querySelector(".step-status");

    stepEl.classList.remove(
      "border-indigo-200", "bg-indigo-50/40",
      "border-emerald-200", "bg-emerald-50/40",
      "border-rose-200", "bg-rose-50/40",
      "border-slate-200", "bg-slate-50/60", "opacity-65"
    );

    if (stepState === "active") {
      stepEl.classList.add("border-indigo-200", "bg-indigo-50/40");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-bold";
        badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-semibold text-indigo-600";
        statusText.textContent = "Đang chạy";
      }
    } else if (stepState === "done") {
      stepEl.classList.add("border-emerald-200", "bg-emerald-50/40");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold";
        badge.innerHTML = '<i class="fa-solid fa-check"></i>';
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-semibold text-emerald-600";
        statusText.textContent = "Hoàn tất";
      }
    } else if (stepState === "error") {
      stepEl.classList.add("border-rose-200", "bg-rose-50/40");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center text-sm font-bold";
        badge.innerHTML = '<i class="fa-solid fa-xmark"></i>';
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-semibold text-rose-600";
        statusText.textContent = "Thất bại";
      }
    } else {
      stepEl.classList.add("border-slate-200", "bg-slate-50/60", "opacity-65");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-sm font-bold";
        badge.textContent = String(stepNumber);
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-medium text-slate-400";
        statusText.textContent = "Chờ xử lý";
      }
    }
  }

  function setElapsed(seconds) {
    const timerEl = $("countdown-timer");
    if (timerEl) timerEl.textContent = String(seconds);
  }

  function scheduleStep(callback, delay) {
    const timer = setTimeout(callback, delay);
    state.stepTimers.push(timer);
  }

  function startProgressSimulation() {
    stopTimers();
    state.elapsed = 0;
    state.currentStep = 1;
    setElapsed(0);
    updateProgressUI(8, "Đang khởi tạo quy trình xuất bản...");
    setStepState(1, "active");
    for (let i = 2; i <= TOTAL_STEPS; i++) setStepState(i, "pending");

    state.elapsedTimer = setInterval(() => {
      state.elapsed += 1;
      setElapsed(state.elapsed);
    }, 1000);

    state.progressTimer = setInterval(() => {
      const bar = $("progress-bar");
      const current = parseFloat((bar?.style.width || "8").replace("%", "")) || 8;
      if (current < 92) updateProgressUI(current + 1);
    }, 1800);

    scheduleStep(() => {
      if (state.currentStep !== 1) return;
      setStepState(1, "done");
      setStepState(2, "active");
      state.currentStep = 2;
      updateProgressUI(STEP_PROGRESS[1], "Đang tạo kho lưu trữ GitHub Repository...");
    }, 5000);

    scheduleStep(() => {
      if (state.currentStep !== 2) return;
      setStepState(2, "done");
      setStepState(3, "active");
      state.currentStep = 3;
      updateProgressUI(STEP_PROGRESS[2], "Đang đẩy mã nguồn & tài nguyên lên GitHub...");
    }, 12000);

    scheduleStep(() => {
      if (state.currentStep !== 3) return;
      setStepState(3, "done");
      setStepState(4, "active");
      state.currentStep = 4;
      updateProgressUI(STEP_PROGRESS[3], "Đang build trang & kích hoạt GitHub Pages...");
    }, 22000);
  }

  function stopTimers() {
    clearInterval(state.elapsedTimer);
    clearInterval(state.progressTimer);
    state.stepTimers.forEach((timer) => clearTimeout(timer));
    state.elapsedTimer = null;
    state.progressTimer = null;
    state.stepTimers = [];
  }

  function showResultPanels({ success, error }) {
    $("result-box")?.classList.remove("hidden");
    $("success-panel")?.classList.toggle("hidden", !success);
    $("error-panel")?.classList.toggle("hidden", !error);
    $("retry-btn")?.classList.toggle("hidden", !error);
    $("visit-site-btn")?.classList.toggle("hidden", !success);
    $("view-deployments-btn")?.classList.toggle("hidden", !success);
  }

  function handleDeploySuccess(pagesUrl) {
    stopTimers();
    for (let i = 1; i <= TOTAL_STEPS; i++) setStepState(i, "done");
    updateProgressUI(100, "Hoàn tất xuất bản 100%");

    const iconWrap = $("status-icon-wrapper");
    const mainIcon = $("status-main-icon");
    if (iconWrap) iconWrap.className = "w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center text-2xl mb-4";
    if (mainIcon) mainIcon.className = "fa-solid fa-circle-check";

    const badge = $("countdown-badge");
    if (badge) {
      badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 mb-3";
      badge.innerHTML = `<i class="fa-solid fa-bolt"></i><span>Hoàn tất trong ${state.elapsed} giây</span>`;
    }

    const title = $("deploy-title");
    const subtitle = $("deploy-subtitle");
    if (title) title.textContent = "Landing Page đã lên sóng!";
    if (subtitle) subtitle.textContent = "Bạn có thể truy cập và chia sẻ đường dẫn công khai ngay bây giờ.";

    const urlInput = $("published-url-input");
    const visitBtn = $("visit-site-btn");
    const historyBtn = $("view-deployments-btn");
    if (urlInput) urlInput.value = pagesUrl;
    if (visitBtn) visitBtn.href = pagesUrl;
    if (historyBtn) {
      historyBtn.href = `deployments.html${state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : ""}`;
    }

    showResultPanels({ success: true, error: false });
    try {
      sessionStorage.setItem(
        "flash_toast",
        JSON.stringify({
          type: "success",
          title: "Xuất bản thành công",
          message: "Landing Page đã được deploy lên GitHub Pages.",
        })
      );
    } catch (error) {
      /* sessionStorage có thể bị chặn – không ảnh hưởng luồng chính */
    }
    window.showToast?.("Xuất bản Landing Page thành công!", "success", "Hoàn tất");
  }

  function handleDeployError(message) {
    stopTimers();
    setStepState(state.currentStep || 1, "error");
    const percentText = $("progress-percent")?.textContent || "0%";
    updateProgressUI(parseFloat(percentText.replace("%", "")) || 20, "Quá trình xuất bản bị gián đoạn");

    const iconWrap = $("status-icon-wrapper");
    const mainIcon = $("status-main-icon");
    if (iconWrap) iconWrap.className = "w-16 h-16 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center text-2xl mb-4";
    if (mainIcon) mainIcon.className = "fa-solid fa-triangle-exclamation";

    const badge = $("countdown-badge");
    if (badge) {
      badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 mb-3";
      badge.innerHTML = '<i class="fa-solid fa-circle-xmark"></i><span>Deploy thất bại</span>';
    }

    const title = $("deploy-title");
    if (title) title.textContent = "Không thể xuất bản Landing Page";
    const errorText = $("error-message-text");
    if (errorText) errorText.textContent = message;

    showResultPanels({ success: false, error: true });
    window.showToast?.(message, "error", "Deploy thất bại");
  }

  function resetDeployUI() {
    const iconWrap = $("status-icon-wrapper");
    const mainIcon = $("status-main-icon");
    if (iconWrap) iconWrap.className = "w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-2xl mb-4 shadow-inner";
    if (mainIcon) mainIcon.className = "fa-solid fa-cloud-arrow-up fa-bounce";

    const badge = $("countdown-badge");
    if (badge) {
      badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 mb-3";
      badge.innerHTML = '<i class="fa-regular fa-clock"></i><span>Đã xử lý: <strong id="countdown-timer">0</strong> giây</span>';
    }

    const title = $("deploy-title");
    if (title) title.textContent = "Đang xuất bản Landing Page của bạn...";
    const subtitle = $("deploy-subtitle");
    if (subtitle) subtitle.textContent = "Hệ thống đang render HTML, tạo GitHub Repository và kích hoạt GitHub Pages. Vui lòng không đóng trình duyệt.";

    showResultPanels({ success: false, error: false });
    $("result-box")?.classList.add("hidden");
  }

  async function loadProjectInfo() {
    if (!state.projectId) return;
    try {
      const response = await apiRequest(`/projects/${state.projectId}`);
      const project = response?.data || {};
      state.projectName = project.product_name || project.campaign_name || "";
      if (state.projectName) {
        const title = $("deploy-title");
        if (title) title.textContent = `Đang xuất bản "${state.projectName}"...`;
      }
    } catch (error) {
      // Không chặn deploy nếu chỉ lỗi phần hiển thị tên dự án.
      console.debug("Không tải được thông tin dự án:", error.message);
    }
  }

  async function triggerDeploy() {
    if (state.deploying) return;

    if (!getToken()) {
      const prefix = window.location.pathname.includes("/pages/") ? "../" : "";
      window.location.href = `${prefix}login.html`;
      return;
    }

    if (!state.projectId) {
      handleDeployError("Thiếu mã dự án (?id=...). Vui lòng mở trang xuất bản từ danh sách dự án.");
      return;
    }

    state.deploying = true;
    resetDeployUI();
    startProgressSimulation();
    loadProjectInfo();

    try {
      const result = await apiRequest(`/projects/${state.projectId}/deploy`, {
        method: "POST",
      });

      const pagesUrl =
        result?.data?.github_pages_url ||
        result?.github_pages_url ||
        "";

      if (!pagesUrl) {
        throw new Error("Backend không trả về đường dẫn GitHub Pages sau khi deploy.");
      }

      handleDeploySuccess(pagesUrl);
    } catch (error) {
      console.error("Lỗi deploy:", error);
      handleDeployError(error.message || "Máy chủ trả về lỗi khi xuất bản.");
    } finally {
      state.deploying = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    state.projectId = getProjectIdFromUrl();

    const editBtn = $("back-edit-btn");
    if (editBtn && state.projectId) {
      editBtn.href = `edit-project.html?id=${encodeURIComponent(state.projectId)}`;
    }
    const historyBtn = $("view-deployments-btn");
    if (historyBtn && state.projectId) {
      historyBtn.href = `deployments.html?project_id=${encodeURIComponent(state.projectId)}`;
    }

    const copyBtn = $("copy-url-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        const input = $("published-url-input");
        if (!input || !input.value) return;
        try {
          await navigator.clipboard.writeText(input.value);
          copyBtn.innerHTML = '<i class="fa-solid fa-check mr-1"></i>Đã chép';
          setTimeout(() => {
            copyBtn.innerHTML = '<i class="fa-regular fa-copy mr-1"></i>Sao chép';
          }, 2000);
        } catch (error) {
          window.showToast?.("Trình duyệt không cho phép sao chép tự động.", "warning", "Sao chép");
        }
      });
    }

    $("retry-btn")?.addEventListener("click", triggerDeploy);
    triggerDeploy();
  });
})();
