/**
 * Trang Lịch sử xuất bản – đọc dữ liệu thật từ FastAPI.
 *
 * Endpoints:
 *   GET /deployments        – danh sách deployment (phân trang, lọc theo dự án).
 *   GET /deployments/stats  – số liệu tổng hợp cho banner.
 *   POST /projects/{id}/deploy – xuất bản lại một dự án.
 */
(function () {
  "use strict";

  const PAGE_SIZE = 10;
  const STATUS_CONFIG = {
    active: {
      label: "Đang hoạt động",
      badge: "bg-emerald-100 text-emerald-800",
      iconWrap: "bg-indigo-50 border border-indigo-100 text-indigo-600",
      icon: "fa-globe",
      dot: "relative inline-flex rounded-full h-2 w-2 bg-emerald-500",
      ping: true,
    },
    superseded: {
      label: "Phiên bản cũ",
      badge: "bg-slate-100 text-slate-600",
      iconWrap: "bg-slate-100 text-slate-500",
      icon: "fa-box-archive",
      dot: "",
      ping: false,
    },
    failed: {
      label: "Thất bại",
      badge: "bg-rose-100 text-rose-700",
      iconWrap: "bg-rose-50 border border-rose-100 text-rose-600",
      icon: "fa-triangle-exclamation",
      dot: "",
      ping: false,
    },
    processing: {
      label: "Đang xử lý",
      badge: "bg-amber-100 text-amber-800",
      iconWrap: "bg-amber-50 border border-amber-100 text-amber-600",
      icon: "fa-spinner fa-spin",
      dot: "",
      ping: false,
    },
  };

  const state = {
    items: [],
    filtered: [],
    page: 1,
    status: "all",
    keyword: "",
    projectId: "",
    stats: null,
    loading: false,
    redeploying: new Set(),
  };

  const $ = (id) => document.getElementById(id);

  // ── Helpers ───────────────────────────────────────────────────────
  function escapeHtml(value) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(value === null || value === undefined ? "" : String(value)));
    return div.innerHTML;
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatRelative(value) {
    if (!value) return "Chưa xác định";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Chưa xác định";

    const diffMs = Date.now() - date.getTime();
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return "Vừa xong";
    if (minutes < 60) return `${minutes} phút trước`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} giờ trước`;

    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} ngày trước`;

    return formatDateTime(value);
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
      return "Đang xử lý";
    }
    const total = Math.max(0, Math.round(Number(seconds)));
    if (total < 60) return `${total} giây`;
    const minutes = Math.floor(total / 60);
    const remain = total % 60;
    return remain ? `${minutes} phút ${remain} giây` : `${minutes} phút`;
  }

  function projectName(item) {
    return item.project_name || item.campaign_name || item.product_name || `Dự án #${item.project_id}`;
  }

  function shortSha(sha) {
    const value = String(sha || "").trim();
    if (!value) return "—";
    return value.length > 10 ? value.slice(0, 7) : value;
  }

  function resolveStatus(item) {
    if (item.view_status) return item.view_status;
    if (item.status === "Success") return item.is_latest_success ? "active" : "superseded";
    if (item.status === "Failed") return "failed";
    return "processing";
  }

  function statusCell(status) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.processing;
    if (config.ping) {
      return `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${config.badge}">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span>${config.label}</span>
        </span>
      `;
    }
    const icon = status === "processing" ? "fa-spinner fa-spin" : status === "failed" ? "fa-circle-xmark" : "fa-clock-rotate-left";
    return `
      <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${config.badge}">
        <i class="fa-solid ${icon} text-[10px]"></i>
        <span>${config.label}</span>
      </span>
    `;
  }

  function rowHtml(item) {
    const status = resolveStatus(item);
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.processing;
    const url = item.page_url || "";
    const name = projectName(item);
    const errorMessage = status === "failed" ? String(item.error_message || "").trim() : "";
    const isRedeploying = state.redeploying.has(Number(item.project_id));

    const urlHtml = url
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="text-xs font-mono text-indigo-600 hover:underline flex items-center gap-1 truncate max-w-[260px]">
           <span class="truncate">${escapeHtml(url.replace(/^https?:\/\//, ""))}</span>
           <i class="fa-solid fa-arrow-up-right-from-square text-[9px] shrink-0"></i>
         </a>`
      : `<span class="text-xs text-slate-400">Chưa có đường dẫn công khai</span>`;

    const errorHtml = errorMessage
      ? `<p class="text-[11px] text-rose-600 mt-1 line-clamp-2" title="${escapeHtml(errorMessage)}">
           <i class="fa-solid fa-circle-exclamation mr-1"></i>${escapeHtml(errorMessage)}
         </p>`
      : "";

    const openAction = url
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="Mở trang trực tiếp" class="w-8 h-8 rounded-lg border border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50 flex items-center justify-center transition">
           <i class="fa-solid fa-arrow-up-right-from-square text-xs"></i>
         </a>`
      : "";

    const copyAction = url
      ? `<button type="button" data-action="copy" data-url="${escapeHtml(url)}" title="Sao chép đường dẫn" class="w-8 h-8 rounded-lg border border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50 flex items-center justify-center transition">
           <i class="fa-regular fa-copy text-xs"></i>
         </button>`
      : "";

    const redeployAction = `
      <button type="button" data-action="redeploy" data-project-id="${escapeHtml(item.project_id)}"
        ${isRedeploying || status === "processing" ? "disabled" : ""}
        title="Xuất bản lại dự án" class="w-8 h-8 rounded-lg border border-slate-200 text-slate-500 hover:text-emerald-600 hover:border-emerald-200 hover:bg-emerald-50/50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition">
        <i class="fa-solid ${isRedeploying ? "fa-spinner fa-spin" : "fa-arrows-rotate"} text-xs"></i>
      </button>
    `;

    return `
      <tr class="hover:bg-slate-50/80 transition-colors group">
        <td class="py-4 px-4 sm:px-6">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl ${config.iconWrap} flex items-center justify-center text-base shrink-0">
              <i class="fa-solid ${config.icon}"></i>
            </div>
            <div class="min-w-0">
              <div class="font-bold text-slate-900 group-hover:text-indigo-600 transition truncate max-w-xs sm:max-w-sm">${escapeHtml(name)}</div>
              <div class="flex items-center gap-2 mt-0.5">${urlHtml}</div>
              ${errorHtml}
            </div>
          </div>
        </td>
        <td class="py-4 px-4">${statusCell(status)}</td>
        <td class="py-4 px-4">
          <div class="flex flex-col">
            <span class="font-mono text-xs font-semibold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded w-fit" title="${escapeHtml(item.commit_sha || "")}">${escapeHtml(shortSha(item.commit_sha))}</span>
            <span class="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
              <i class="fa-regular fa-clock text-[10px] text-indigo-500"></i>
              <span>${escapeHtml(formatDuration(item.duration_seconds))}</span>
            </span>
          </div>
        </td>
        <td class="py-4 px-4">
          <div class="text-xs font-medium text-slate-800">${escapeHtml(formatRelative(item.start_time))}</div>
          <div class="text-[11px] text-slate-400">${escapeHtml(formatDateTime(item.start_time))}</div>
        </td>
        <td class="py-4 px-4 text-right pr-6">
          <div class="flex items-center justify-end gap-1.5">
            ${openAction}
            ${copyAction}
            <a href="version-history.html?id=${encodeURIComponent(item.project_id)}" title="Lịch sử phiên bản" class="w-8 h-8 rounded-lg border border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50 flex items-center justify-center transition">
              <i class="fa-solid fa-code-branch text-xs"></i>
            </a>
            ${redeployAction}
          </div>
        </td>
      </tr>
    `;
  }

  function filteredItems() {
    const keyword = state.keyword.trim().toLowerCase();
    return state.items.filter((item) => {
      const status = resolveStatus(item);
      if (state.status !== "all" && status !== state.status) return false;
      if (!keyword) return true;

      const haystack = [
        projectName(item),
        item.page_url,
        item.commit_sha,
        item.error_message,
        item.project_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(keyword);
    });
  }

  function updateCounts() {
    const counts = { all: state.items.length, active: 0, superseded: 0, failed: 0, processing: 0 };
    state.items.forEach((item) => {
      const status = resolveStatus(item);
      if (counts[status] !== undefined) counts[status] += 1;
    });

    Object.entries(counts).forEach(([key, value]) => {
      const el = $(`count-${key}`);
      if (el) el.textContent = String(value);
    });
  }

  function updateFilterButtons() {
    ["all", "active", "superseded", "failed", "processing"].forEach((status) => {
      const btn = $(`btn-status-${status}`);
      if (!btn) return;
      const active = status === state.status;
      btn.className = active
        ? "px-3 py-1.5 rounded-lg bg-white text-indigo-600 shadow-xs font-bold transition whitespace-nowrap"
        : "px-3 py-1.5 rounded-lg hover:text-slate-900 font-semibold transition text-slate-600 whitespace-nowrap";
    });
  }

  function renderPagination(totalPages) {
    const prev = $("btn-prev-page");
    const next = $("btn-next-page");
    const indicator = $("page-indicator");
    if (prev) prev.disabled = state.page <= 1;
    if (next) next.disabled = state.page >= totalPages;
    if (indicator) indicator.textContent = String(state.page);
  }

  function render() {
    const tbody = $("deployments-table-body");
    if (!tbody) return;

    state.filtered = filteredItems();
    const totalPages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
    if (state.page > totalPages) state.page = totalPages;

    const start = (state.page - 1) * PAGE_SIZE;
    const pageItems = state.filtered.slice(start, start + PAGE_SIZE);

    if (pageItems.length === 0) {
      const isEmpty = state.items.length === 0;
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="py-12 text-center text-slate-400">
            <div class="w-12 h-12 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400 mb-3 text-lg">
              <i class="fa-solid ${isEmpty ? "fa-cloud-arrow-up" : "fa-magnifying-glass"}"></i>
            </div>
            <p class="text-sm font-semibold text-slate-700">${isEmpty ? "Chưa có bản triển khai nào" : "Không tìm thấy bản triển khai phù hợp"}</p>
            <p class="text-xs text-slate-400 mt-1">${isEmpty ? "Hãy tạo Landing Page và bấm Xuất bản để bắt đầu." : "Hãy thử đổi từ khóa tìm kiếm hoặc bỏ chọn bộ lọc."}</p>
            ${isEmpty ? '<a href="create.html" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition"><i class="fa-solid fa-plus"></i>Tạo trang mới</a>' : ""}
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = pageItems.map(rowHtml).join("");
    }

    const showing = $("showing-count");
    const total = $("total-count");
    if (showing) showing.textContent = String(pageItems.length);
    if (total) total.textContent = String(state.filtered.length);

    updateCounts();
    updateFilterButtons();
    renderPagination(totalPages);
  }

  function renderLoading() {
    const tbody = $("deployments-table-body");
    if (!tbody) return;
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-12 text-center">
          <i class="fa-solid fa-spinner fa-spin text-2xl text-indigo-400 mb-3"></i>
          <p class="text-sm text-slate-400 font-semibold">Đang tải lịch sử xuất bản...</p>
        </td>
      </tr>
    `;
    ["all", "active", "superseded", "failed", "processing"].forEach((key) => {
      const el = $(`count-${key}`);
      if (el) el.textContent = "—";
    });
  }

  function renderError(message) {
    const tbody = $("deployments-table-body");
    if (!tbody) return;
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-12 text-center">
          <div class="w-12 h-12 mx-auto rounded-2xl bg-rose-50 text-rose-500 flex items-center justify-center mb-3 text-lg">
            <i class="fa-solid fa-triangle-exclamation"></i>
          </div>
          <p class="text-sm font-bold text-rose-700">Không tải được lịch sử xuất bản</p>
          <p class="text-xs text-slate-500 mt-1 max-w-lg mx-auto" id="deployments-error-message"></p>
          <button type="button" onclick="reloadDeployments()" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition">
            <i class="fa-solid fa-rotate-right"></i>
            <span>Thử lại</span>
          </button>
        </td>
      </tr>
    `;
    const messageEl = $("deployments-error-message");
    if (messageEl) messageEl.textContent = message || "Vui lòng kiểm tra backend FastAPI.";
  }

  function applyStats() {
    const stats = state.stats || {};
    const items = state.items;

    const live = stats.live_projects !== undefined
      ? Number(stats.live_projects) || 0
      : items.filter((item) => resolveStatus(item) === "active").length;
    const total = stats.total_deployments !== undefined
      ? Number(stats.total_deployments) || 0
      : items.length;

    let rate = stats.success_rate;
    if (rate === undefined || rate === null) {
      const successful = Number(stats.successful_deployments);
      rate = total ? Math.round(((Number.isNaN(successful) ? items.filter((i) => resolveStatus(i) !== "failed").length : successful) * 100) / total) : 0;
    }

    const liveEl = $("stat-live-count");
    const totalEl = $("stat-total-count");
    const rateEl = $("stat-success-rate");
    if (liveEl) liveEl.textContent = String(live);
    if (totalEl) totalEl.textContent = String(total);
    if (rateEl) rateEl.textContent = `${rate}%`;
  }

  // ── Actions ───────────────────────────────────────────────────────
  async function copyUrl(url) {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      window.showToast?.("Đã sao chép đường dẫn Landing Page.", "success", "Sao chép");
    } catch (error) {
      window.showToast?.("Trình duyệt không cho phép sao chép tự động.", "warning", "Sao chép");
    }
  }

  async function redeploy(projectId, button) {
    const id = Number(projectId);
    if (!id || state.redeploying.has(id)) return;

    const confirmed = window.confirm(
      "Xuất bản lại dự án này lên GitHub Pages?\nQuá trình có thể mất vài chục giây."
    );
    if (!confirmed) return;

    state.redeploying.add(id);
    if (button) {
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-xs"></i>';
    }
    window.showToast?.("Đang xuất bản lại dự án...", "info", "Đang deploy");

    try {
      const response = await apiRequest(`/projects/${id}/deploy`, { method: "POST" });
      const pagesUrl = response?.data?.github_pages_url || response?.github_pages_url || "";
      window.showToast?.(
        pagesUrl
          ? `Xuất bản thành công: ${pagesUrl}`
          : "Xuất bản lại dự án thành công.",
        "success",
        "Hoàn tất"
      );
      await loadDeployments();
    } catch (error) {
      console.error("Deploy lại thất bại:", error);
      window.showToast?.(error.message || "Không thể xuất bản lại dự án.", "error", "Deploy thất bại");
      if (button) {
        button.disabled = false;
        button.innerHTML = '<i class="fa-solid fa-arrows-rotate text-xs"></i>';
      }
    } finally {
      state.redeploying.delete(id);
    }
  }

  function handleTableClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const action = button.dataset.action;
    if (action === "copy") {
      copyUrl(button.dataset.url);
    } else if (action === "redeploy") {
      redeploy(button.dataset.projectId, button);
    }
  }

  function applyProjectScope() {
    const note = $("project-scope-note");
    if (!note || !state.projectId) return;

    const first = state.items[0];
    note.textContent = first ? ` • ${projectName(first)}` : ` • Dự án #${state.projectId}`;
    note.classList.remove("hidden");
  }

  // ── Load ──────────────────────────────────────────────────────────
  async function loadDeployments(showLoading = true) {
    if (state.loading) return;
    state.loading = true;
    if (showLoading) renderLoading();

    const listParams = new URLSearchParams({ page_size: "100" });
    const statsParams = new URLSearchParams();
    if (state.projectId) {
      listParams.set("project_id", state.projectId);
      statsParams.set("project_id", state.projectId);
    }

    try {
      const [listResponse, statsResponse] = await Promise.all([
        apiRequest(`/deployments?${listParams.toString()}`),
        apiRequest(`/deployments/stats${statsParams.toString() ? `?${statsParams.toString()}` : ""}`).catch(
          (error) => {
            console.warn("Không tải được thống kê deployment:", error.message);
            return null;
          }
        ),
      ]);

      const payload = listResponse?.data || {};
      state.items = Array.isArray(payload.items) ? payload.items : [];
      state.stats = statsResponse?.data || null;
      state.page = 1;

      applyStats();
      applyProjectScope();
      updateCounts();
      render();
    } catch (error) {
      console.error("Lỗi tải lịch sử xuất bản:", error);
      renderError(error.message || "Vui lòng kiểm tra backend FastAPI.");
      window.showToast?.(error.message || "Không tải được lịch sử xuất bản.", "error", "Lỗi dữ liệu");
    } finally {
      state.loading = false;
    }
  }

  async function reloadDeployments() {
    if (state.loading) return;
    await loadDeployments();
    window.showToast?.("Đã cập nhật lịch sử xuất bản mới nhất.", "info", "Làm mới");
  }

  function setStatusFilter(status) {
    state.status = status || "all";
    state.page = 1;
    render();
  }

  function changePage(delta) {
    const totalPages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
    const next = state.page + delta;
    if (next < 1 || next > totalPages) return;
    state.page = next;
    render();
  }

  // ── Init ──────────────────────────────────────────────────────────
  window.reloadDeployments = reloadDeployments;
  window.setStatusFilter = setStatusFilter;
  window.changePage = changePage;

  document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    state.projectId = params.get("project_id") || params.get("id") || "";

    const docsLink = $("swagger-docs-link");
    if (docsLink) docsLink.href = `${window.API_BASE_URL || ""}/docs`;

    $("search-input")?.addEventListener("input", (event) => {
      state.keyword = event.target.value || "";
      state.page = 1;
      render();
    });

    $("deployments-table-body")?.addEventListener("click", handleTableClick);

    loadDeployments();
  });
})();
