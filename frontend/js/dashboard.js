/**
 * Dashboard Tổng quan – đọc dữ liệu thật từ FastAPI.
 *
 * Endpoints:
 *   GET /projects/stats  – số liệu dự án, lượt sinh AI, deployment, template.
 *   GET /api/health      – trạng thái backend.
 */
(function () {
  "use strict";

  const STATUS_CONFIG = {
    draft: {
      label: "Bản nháp",
      badge: "bg-amber-50 text-amber-700 border-amber-200",
      iconBg: "bg-amber-50 border-amber-100 text-amber-600",
      icon: "fa-pen-ruler",
    },
    deploying: {
      label: "Đang deploy",
      badge: "bg-blue-50 text-blue-700 border-blue-200",
      iconBg: "bg-blue-50 border-blue-100 text-blue-600",
      icon: "fa-cloud-arrow-up",
    },
    published: {
      label: "Đã xuất bản",
      badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
      iconBg: "bg-emerald-50 border-emerald-100 text-emerald-600",
      icon: "fa-globe",
    },
    failed: {
      label: "Lỗi",
      badge: "bg-rose-50 text-rose-700 border-rose-200",
      iconBg: "bg-rose-50 border-rose-100 text-rose-600",
      icon: "fa-triangle-exclamation",
    },
  };

  const FALLBACK_CONFIG = {
    label: "Chưa xác định",
    badge: "bg-slate-100 text-slate-600 border-slate-200",
    iconBg: "bg-indigo-50 border-indigo-100 text-indigo-600",
    icon: "fa-laptop-code",
  };

  function $(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
  }

  function formatRelativeTime(value) {
    if (!value) return "Chưa cập nhật";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Chưa cập nhật";

    const diffMs = Date.now() - date.getTime();
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return "Vừa xong";
    if (minutes < 60) return `${minutes} phút trước`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} giờ trước`;

    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} ngày trước`;

    return date.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  function projectName(project) {
    return project.campaign_name || project.product_name || `Dự án #${project.id}`;
  }

  function buildProjectRow(project) {
    const config = STATUS_CONFIG[project.status] || FALLBACK_CONFIG;
    const row = document.createElement("div");
    row.className = "p-4 sm:px-5 flex items-center justify-between hover:bg-slate-50/80 transition";

    const left = document.createElement("div");
    left.className = "flex items-center gap-3.5 min-w-0";

    const iconBox = document.createElement("div");
    iconBox.className = `w-10 h-10 rounded-xl border flex items-center justify-center text-base shrink-0 ${config.iconBg}`;
    const icon = document.createElement("i");
    icon.className = `fa-solid ${config.icon}`;
    iconBox.appendChild(icon);

    const info = document.createElement("div");
    info.className = "truncate";

    const title = document.createElement("h4");
    title.className = "text-sm font-bold text-slate-800 truncate";
    title.textContent = projectName(project);

    const meta = document.createElement("div");
    meta.className = "flex flex-wrap items-center gap-2 mt-0.5";

    const time = document.createElement("span");
    time.className = "text-[11px] text-slate-400";
    time.textContent = `Cập nhật ${formatRelativeTime(project.updated_at || project.created_at)}`;

    const badge = document.createElement("span");
    badge.className = `text-[10px] px-2 py-0.5 rounded-full font-semibold border ${config.badge}`;
    badge.textContent = config.label;

    meta.append(time, badge);
    info.append(title, meta);
    left.append(iconBox, info);

    const actions = document.createElement("div");
    actions.className = "flex items-center gap-2 shrink-0";

    const previewLink = document.createElement("a");
    previewLink.href = `pages/preview.html?id=${encodeURIComponent(project.id)}`;
    previewLink.title = "Xem trước";
    previewLink.className =
      "p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition";
    previewLink.innerHTML = '<i class="fa-solid fa-eye text-sm"></i>';

    const editLink = document.createElement("a");
    editLink.href = `pages/edit-project.html?id=${encodeURIComponent(project.id)}`;
    editLink.title = "Chỉnh sửa";
    editLink.className =
      "p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition";
    editLink.innerHTML = '<i class="fa-solid fa-pen-to-square text-sm"></i>';

    actions.append(previewLink, editLink);

    if (project.github_pages_url) {
      const openLink = document.createElement("a");
      openLink.href = project.github_pages_url;
      openLink.target = "_blank";
      openLink.rel = "noopener noreferrer";
      openLink.title = "Mở trang đã xuất bản";
      openLink.className =
        "p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition";
      openLink.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square text-sm"></i>';
      actions.append(openLink);
    }

    row.append(left, actions);
    return row;
  }

  function renderRecentProjects(projects) {
    const container = $("recent-projects-list");
    if (!container) return;

    container.innerHTML = "";

    if (!Array.isArray(projects) || projects.length === 0) {
      const empty = document.createElement("div");
      empty.className = "p-10 text-center";
      empty.innerHTML = `
        <div class="w-12 h-12 mx-auto rounded-2xl bg-indigo-50 text-indigo-500 flex items-center justify-center text-xl mb-3">
          <i class="fa-solid fa-folder-open"></i>
        </div>
        <p class="text-sm font-bold text-slate-700">Chưa có dự án nào</p>
        <p class="text-xs text-slate-400 mt-1">Tạo Landing Page đầu tiên bằng AI để bắt đầu quản lý tại đây.</p>
        <a href="pages/create.html" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition">
          <i class="fa-solid fa-plus"></i>
          <span>Tạo dự án mới</span>
        </a>
      `;
      container.appendChild(empty);
      return;
    }

    projects.forEach((project) => container.appendChild(buildProjectRow(project)));
  }

  function applyStats(data) {
    setText("dash-total-projects", data.total_projects ?? 0);
    setText("dash-published-projects", data.published_projects ?? 0);
    setText("dash-generation-count", data.total_generations ?? 0);
    setText("dash-template-count", data.total_templates ?? 0);

    setText("dash-total-trend", `${data.draft_projects ?? 0} bản nháp`);
    setText("dash-total-note", `${data.deploying_projects ?? 0} dự án đang triển khai`);

    const publishedTotal = Number(data.total_projects || 0);
    const published = Number(data.published_projects || 0);
    const publishedRate = publishedTotal ? Math.round((published * 100) / publishedTotal) : 0;
    setText("dash-published-trend", `${publishedRate}% tổng dự án`);
    setText("dash-published-note", `${data.successful_deployments ?? 0} lần deploy thành công`);

    setText("dash-generation-badge", `${data.successful_generations ?? 0} thành công`);
    setText("dash-generation-note", `Gemini API • ${data.total_deployments ?? 0} lần xuất bản`);

    setText("dash-template-note", "Sẵn sàng để chọn khi tạo dự án");
  }

  async function loadHealth() {
    const hostEl = $("backend-status-host");
    const labelEl = $("backend-status-label");
    const dotEl = $("backend-status-dot");
    const noteEl = $("backend-status-note");
    const baseUrl = window.API_BASE_URL || window.location.origin;

    if (hostEl) hostEl.textContent = baseUrl.replace(/^https?:\/\//, "");

    try {
      await apiRequest("/api/health");
      if (labelEl) {
        labelEl.textContent = "● Online";
        labelEl.className = "text-emerald-600 font-bold";
      }
      if (dotEl) dotEl.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse";
      if (noteEl) noteEl.textContent = "FastAPI và cơ sở dữ liệu đã sẵn sàng.";
    } catch (error) {
      if (labelEl) {
        labelEl.textContent = "● Offline";
        labelEl.className = "text-rose-600 font-bold";
      }
      if (dotEl) dotEl.className = "w-2.5 h-2.5 rounded-full bg-rose-500";
      if (noteEl) noteEl.textContent = error.message || "Không thể kết nối tới backend.";
    }
  }

  async function loadDashboard() {
    const list = $("recent-projects-list");
    if (list) {
      list.innerHTML = `
        <div class="p-10 text-center">
          <i class="fa-solid fa-spinner fa-spin text-2xl text-indigo-400 mb-3"></i>
          <p class="text-sm text-slate-400 font-semibold">Đang tải dữ liệu tổng quan...</p>
        </div>
      `;
    }

    try {
      const response = await apiRequest("/projects/stats");
      const data = response?.data || {};
      applyStats(data);
      renderRecentProjects(data.recent_projects);
    } catch (error) {
      console.error("Lỗi tải dashboard:", error);
      if (list) {
        list.innerHTML = "";
        const box = document.createElement("div");
        box.className = "p-10 text-center";
        box.innerHTML = `
          <div class="w-12 h-12 mx-auto rounded-2xl bg-rose-50 text-rose-500 flex items-center justify-center text-xl mb-3">
            <i class="fa-solid fa-triangle-exclamation"></i>
          </div>
          <p class="text-sm font-bold text-rose-700">Không tải được dữ liệu tổng quan</p>
          <p class="text-xs text-slate-500 mt-1"></p>
          <button type="button" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition">
            <i class="fa-solid fa-rotate-right"></i>
            <span>Thử lại</span>
          </button>
        `;
        const message = box.querySelector("p.text-xs");
        if (message) message.textContent = error.message || "Vui lòng kiểm tra backend FastAPI.";
        box.querySelector("button")?.addEventListener("click", loadDashboard);
        list.appendChild(box);
      }
      window.showToast?.(error.message || "Không tải được dashboard.", "error", "Lỗi dữ liệu");
    }
  }

  window.loadDashboardData = loadDashboard;

  document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
    loadHealth();
  });
})();
