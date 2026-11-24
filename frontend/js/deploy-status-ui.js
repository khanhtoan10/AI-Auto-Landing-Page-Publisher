/**
 * T02C0FE: Đồng bộ trạng thái deploy GitHub Pages, hiển thị nhãn trạng thái,
 * nút "Truy cập website" (chỉ hiện khi build xong) và nút "Copy link"
 * trên Dashboard (index.html) và trang Dự án (pages/projects.html).
 */
(function () {
    const FALLBACK_PROJECTS = [
        {
            id: 1,
            campaign_name: "SaaS Analytics Landing Page",
            status: "published",
            deploy_status: "Success",
            is_built: true,
            github_pages_url: "https://tiendat1-cmy.github.io/lp-1-saas-analytics/",
            updated_at: "2 giờ trước",
            icon: "fa-laptop-code",
            iconBg: "bg-indigo-50 border-indigo-100 text-indigo-600",
        },
        {
            id: 2,
            campaign_name: "Ra Mắt Chuỗi Cà Phê Cold Brew",
            status: "building",
            deploy_status: "Building",
            is_built: false,
            github_pages_url: null,
            updated_at: "Đang xử lý GitHub Pages",
            icon: "fa-mug-saucer",
            iconBg: "bg-amber-50 border-amber-100 text-amber-600",
        },
        {
            id: 3,
            campaign_name: "Khóa Học Fitness Online 30 Ngày",
            status: "published",
            deploy_status: "Success",
            is_built: true,
            github_pages_url: "https://tiendat1-cmy.github.io/lp-3-fitness-30-ngay/",
            updated_at: "3 ngày trước",
            icon: "fa-dumbbell",
            iconBg: "bg-rose-50 border-rose-100 text-rose-600",
        },
    ];

    function getApiBase() {
        if (window.API_BASE_URL) return window.API_BASE_URL.replace(/\/$/, "");
        return "http://127.0.0.1:8000";
    }

    function getAuthHeaders() {
        const token =
            localStorage.getItem("access_token") ||
            localStorage.getItem("token") ||
            sessionStorage.getItem("access_token");
        return token ? { Authorization: `Bearer ${token}` } : {};
    }

    window.copyWebsiteUrl = async function (url, btnEl) {
        if (!url) return;
        try {
            await navigator.clipboard.writeText(url);
        } catch (_) {
            const input = document.createElement("input");
            input.value = url;
            document.body.appendChild(input);
            input.select();
            document.execCommand("copy");
            document.body.removeChild(input);
        }

        if (btnEl) {
            const originalHtml = btnEl.innerHTML;
            btnEl.innerHTML = '<i class="fa-solid fa-check text-emerald-600"></i> <span>Đã copy</span>';
            btnEl.classList.add("border-emerald-300", "bg-emerald-50", "text-emerald-700");
            setTimeout(() => {
                btnEl.innerHTML = originalHtml;
                btnEl.classList.remove("border-emerald-300", "bg-emerald-50", "text-emerald-700");
            }, 1800);
        }

        if (typeof window.showToast === "function") {
            window.showToast(`Đã sao chép link: ${url}`, "success", "Copy thành công");
        }
    };

    function getStatusBadge(project) {
        const deployStatus = (project.deploy_status || "").toLowerCase();
        const isBuilt = Boolean(project.is_built && project.github_pages_url);

        if (isBuilt) {
            return `
        <span class="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          Đã xuất bản
        </span>`;
        }
        if (["building", "rendering", "creating repo", "pushing code", "enabling pages", "queued"].includes(deployStatus) || project.status === "building") {
            return `
        <span class="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-sky-50 text-sky-700 border border-sky-200">
          <i class="fa-solid fa-spinner fa-spin text-[9px]"></i>
          Đang build Pages...
        </span>`;
        }
        if (deployStatus === "failed" || deployStatus === "errored") {
            return `
        <span class="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <i class="fa-solid fa-circle-exclamation text-[9px]"></i>
          Lỗi deploy
        </span>`;
        }
        return `
      <span class="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        Chưa xuất bản
      </span>`;
    }

    function renderProjectRow(project, basePath) {
        const isBuilt = Boolean(project.is_built && project.github_pages_url);
        const title = project.campaign_name || project.product_name || `Dự án #${project.id}`;
        const subtitle = project.updated_at || "Sẵn sàng xuất bản";
        const icon = project.icon || "fa-globe";
        const iconBg = project.iconBg || "bg-indigo-50 border-indigo-100 text-indigo-600";
        const editHref = `${basePath}create.html?id=${project.id}`;
        const deployHref = `${basePath}deploy.html?project_id=${project.id}`;

        // Nút "Truy cập website" và "Copy link" CHỈ HIỆN KHI ĐÃ BUILD XONG (isBuilt === true)
        const publishedActions = isBuilt
            ? `
        <a href="${project.github_pages_url}" target="_blank" rel="noopener noreferrer"
           class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition"
           title="Mở website đã xuất bản">
          <i class="fa-solid fa-arrow-up-right-from-square text-[11px]"></i>
          <span>Truy cập website</span>
        </a>
        <button type="button"
                onclick="window.copyWebsiteUrl('${project.github_pages_url}', this)"
                class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 transition"
                title="Sao chép đường dẫn website">
          <i class="fa-regular fa-copy text-[11px]"></i>
          <span>Copy link</span>
        </button>`
            : `
        <a href="${deployHref}"
           class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition"
           title="Xuất bản lên GitHub Pages">
          <i class="fa-solid fa-rocket text-[11px]"></i>
          <span>Deploy</span>
        </a>`;

        return `
      <div class="p-4 sm:px-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/80 transition" data-project-id="${project.id}">
        <div class="flex items-center gap-3.5 min-w-0">
          <div class="w-10 h-10 rounded-xl border flex items-center justify-center text-base shrink-0 font-bold ${iconBg}">
            <i class="fa-solid ${icon}"></i>
          </div>
          <div class="min-w-0">
            <h4 class="text-sm font-bold text-slate-800 truncate">${title}</h4>
            <div class="flex flex-wrap items-center gap-2 mt-1">
              <span class="text-[11px] text-slate-400">${subtitle}</span>
              ${getStatusBadge(project)}
            </div>
            ${isBuilt
                ? `<p class="text-[11px] font-mono text-indigo-600 truncate mt-1 max-w-md">${project.github_pages_url}</p>`
                : ""
            }
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2 shrink-0">
          ${publishedActions}
          <a href="${editHref}" class="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition" title="Chỉnh sửa">
            <i class="fa-solid fa-pen-to-square text-sm"></i>
          </a>
        </div>
      </div>`;
    }

    async function enrichWithDeployStatus(projects) {
        const headers = getAuthHeaders();
        return Promise.all(
            projects.map(async (proj) => {
                try {
                    const res = await fetch(`${getApiBase()}/projects/${proj.id}/deploy-status`, { headers });
                    if (!res.ok) throw new Error("status_unavailable");
                    const payload = await res.json();
                    const st = payload.data || {};
                    return {
                        ...proj,
                        deploy_status: st.deploy_status || proj.deploy_status,
                        is_built: Boolean(st.is_built),
                        github_pages_url: st.is_built ? st.github_pages_url : null,
                    };
                } catch (_) {
                    const fallbackBuilt =
                        Boolean(proj.is_built) ||
                        (proj.status === "published" && Boolean(proj.github_pages_url));
                    return {
                        ...proj,
                        is_built: fallbackBuilt,
                        github_pages_url: fallbackBuilt ? proj.github_pages_url : null,
                    };
                }
            })
        );
    }

    async function loadAndRenderProjects() {
        const container = document.getElementById("recent-projects-list");
        if (!container) return;

        const isSubPage = window.location.pathname.includes("/pages/");
        const basePath = isSubPage ? "" : "pages/";

        let projects = [];
        try {
            const res = await fetch(`${getApiBase()}/projects`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("fetch_projects_failed");
            const json = await res.json();
            projects = Array.isArray(json.data) && json.data.length > 0 ? json.data : FALLBACK_PROJECTS;
        } catch (_) {
            projects = FALLBACK_PROJECTS;
        }

        const enriched = await enrichWithDeployStatus(projects);
        container.innerHTML = enriched.map((p) => renderProjectRow(p, basePath)).join("");

        const totalEl = document.getElementById("dash-total-projects");
        const pubEl = document.getElementById("dash-published-projects");
        if (totalEl) totalEl.textContent = String(enriched.length);
        if (pubEl) pubEl.textContent = String(enriched.filter((p) => p.is_built).length);
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadAndRenderProjects();
    });
})();