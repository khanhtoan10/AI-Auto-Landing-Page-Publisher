/**
 * Quản lý trang Kho Giao Diện Mẫu (Templates Page)
 * AI Auto Landing Page Publisher
 *
 * Đáp ứng đầy đủ yêu cầu:
 * 1. Template Grid: Lấy dữ liệu từ GET /templates, hiển thị Thumbnail, Tên, Mô tả, Nút "Xem trước", Nút "Chọn mẫu"
 * 2. Template Preview: Modal responsive, hiển thị tên, mô tả, nội dung HTML thực tế qua iframe sandbox
 * 3. Select Template: Quản lý biến template_id, hiển thị trạng thái trực quan cho Card (viền nổi bật, nút "Đã chọn")
 * 4. Campaign Integration: Lưu template_id và chuyển tiếp sang create.html?template_id={id}
 * 5. Trạng thái giao diện: Loading (skeleton), Error (thử lại), Empty, Image Error (fallback SVG), Selected
 */

(function () {
  'use strict';

  // "" là giá trị hợp lệ khi frontend được FastAPI phục vụ cùng origin.
  const apiBaseUrl = typeof window.API_BASE_URL === 'string' ? window.API_BASE_URL : 'http://127.0.0.1:8000';
  let rawTemplates = [];
  let currentSearchQuery = '';
  let currentSort = 'popular';
  let activePreviewTemplate = null;
  let selectedTemplateId = null;

  // Đọc template_id đã lưu trong sessionStorage hoặc URL param (nếu có)
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const paramId = urlParams.get('template_id');
    if (paramId) {
      selectedTemplateId = parseInt(paramId, 10);
    } else {
      const stored = sessionStorage.getItem('selected_template_id');
      if (stored) selectedTemplateId = parseInt(stored, 10);
    }
  } catch (e) {
    console.warn('Không thể đọc template_id lưu trữ:', e);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[character];
    });
  }

  /**
   * Tạo ảnh fallback SVG gradient chuẩn CRO khi thumbnail bị lỗi hoặc không có ảnh
   */
  function createFallbackSvg(name, id) {
    const palette = [
      ['#4f46e5', '#7c3aed'],
      ['#e11d48', '#f43f5e'],
      ['#0284c7', '#06b6d4'],
      ['#059669', '#10b981'],
      ['#d97706', '#f59e0b'],
    ];
    const colors = palette[(id || 1) % palette.length];
    const cleanName = escapeHtml(name || 'Landing Page Template');

    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="600" height="380" viewBox="0 0 600 380">
        <defs>
          <linearGradient id="g_${id}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="${colors[0]}"/>
            <stop offset="100%" stop-color="${colors[1]}"/>
          </linearGradient>
        </defs>
        <rect width="600" height="380" fill="url(#g_${id})"/>
        <circle cx="550" cy="50" r="140" fill="#ffffff" opacity="0.08"/>
        <circle cx="40" cy="340" r="160" fill="#ffffff" opacity="0.05"/>
        <rect x="30" y="30" width="540" height="320" rx="16" fill="#ffffff" opacity="0.08" stroke="#ffffff" stroke-width="1.5" stroke-opacity="0.2"/>
        <text x="60" y="175" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="24" font-weight="800" fill="#ffffff">${cleanName}</text>
        <text x="60" y="215" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="13" font-weight="600" fill="#ffffff" opacity="0.9">Mẫu Chuẩn CRO • Tối Ưu Mobile &amp; SEO</text>
        <rect x="60" y="245" width="130" height="32" rx="8" fill="#ffffff" opacity="0.25"/>
        <text x="80" y="266" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="12" font-weight="700" fill="#ffffff">Preview HTML</text>
      </svg>
    `;
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg.trim());
  }

  function resolveThumbnail(template) {
    const rawUrl = template.thumbnail || template.thumbnail_url;
    if (!rawUrl || typeof rawUrl !== 'string' || rawUrl.trim() === '') {
      return createFallbackSvg(template.name, template.id);
    }
    const trimmed = rawUrl.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('data:')) {
      return trimmed;
    }
    if (trimmed.startsWith('/')) {
      return `${apiBaseUrl}${trimmed}`;
    }
    return `${apiBaseUrl}/${trimmed}`;
  }

  function normalizeTemplates(response) {
    if (response && response.success === false) {
      throw new Error(response.message || 'API không thể tải danh sách template.');
    }

    const items = response && Array.isArray(response.data)
      ? response.data
      : Array.isArray(response) ? response : null;
    if (!items) throw new Error('Dữ liệu API templates không đúng định dạng.');

    return items.map(function (item) {
      if (!item || !Number.isInteger(Number(item.id)) || !item.name) {
        throw new Error('API trả về template thiếu ID hoặc tên.');
      }

      return {
        id: Number(item.id),
        name: String(item.name),
        description: String(item.description || ''),
        thumbnail: resolveThumbnail(item),
        placeholders: Array.isArray(item.placeholders)
          ? item.placeholders.map(String)
          : []
      };
    });
  }

  function renderLoadingState() {
    const grid = document.getElementById('templates-grid');
    grid.innerHTML = `
      <div class="col-span-full grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        ${[1, 2, 3].map(function () { return `
          <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-4 space-y-4 animate-pulse">
            <div class="h-48 bg-slate-200 rounded-2xl w-full"></div>
            <div class="h-5 bg-slate-200 rounded-lg w-3/4"></div>
            <div class="h-3.5 bg-slate-200 rounded-lg w-full"></div>
            <div class="h-9 bg-slate-200 rounded-xl w-full"></div>
          </div>
        `; }).join('')}
      </div>
    `;
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.classList.add('hidden');
  }

  async function loadTemplatesFromApi() {
    renderLoadingState();

    try {
      let response;
      if (typeof window.apiRequest === 'function') {
        response = await window.apiRequest('/templates');
      } else {
        const fetchResponse = await fetch(`${apiBaseUrl}/templates`);
        if (!fetchResponse.ok) throw new Error(`HTTP ${fetchResponse.status}`);
        response = await fetchResponse.json();
      }

      rawTemplates = normalizeTemplates(response);
      const countEl = document.getElementById('total-templates-count');
      if (countEl) countEl.textContent = rawTemplates.length;

      const catEl = document.querySelector('[data-cat="all"] span');
      if (catEl) catEl.textContent = `(${rawTemplates.length})`;

      renderTemplates();
      updateSelectedBanner();
      return true;
    } catch (error) {
      console.error('Lỗi khi tải templates từ API:', error);
      document.getElementById('templates-grid').innerHTML = `
        <div class="col-span-full text-center py-12 px-6 bg-white rounded-3xl border border-rose-200 shadow-sm">
          <div class="w-14 h-14 mx-auto rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center text-2xl mb-3">
            <i class="fa-solid fa-triangle-exclamation"></i>
          </div>
          <h4 class="text-base font-bold text-slate-800">Không thể kết nối đến API Templates</h4>
          <p class="text-xs text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">${escapeHtml(error.message)}</p>
          <button onclick="loadTemplatesFromApi()" class="mt-4 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-md transition flex items-center gap-2 mx-auto">
            <i class="fa-solid fa-rotate-right"></i><span>Thử tải lại</span>
          </button>
        </div>
      `;
      return false;
    }
  }

  function getFilteredTemplates() {
    const query = currentSearchQuery.trim().toLocaleLowerCase();
    const list = rawTemplates.filter(function (item) {
      return !query || [
        item.name,
        item.description,
        item.placeholders.join(' ')
      ].join(' ').toLocaleLowerCase().includes(query);
    });

    if (currentSort === 'newest') {
      list.sort(function (a, b) { return b.id - a.id; });
    } else if (currentSort === 'conversion') {
      list.sort(function (a, b) {
        return b.placeholders.length - a.placeholders.length || a.name.localeCompare(b.name);
      });
    }
    return list;
  }

  /**
   * Chọn Template theo ID
   * Cập nhật trạng thái trực quan: viền nổi bật, nút đổi thành "Đã chọn"
   */
  function selectTemplate(templateId) {
    const id = parseInt(templateId, 10);
    if (isNaN(id)) return;

    selectedTemplateId = id;

    // Lưu vào sessionStorage để duy trì khi chuyển bước
    try {
      sessionStorage.setItem('selected_template_id', String(id));
    } catch (e) {}

    const selectedItem = rawTemplates.find(function (t) { return t.id === id; });

    // Render lại để cập nhật visual state cho các card
    renderTemplates();
    updateSelectedBanner();

    if (window.showToast && selectedItem) {
      window.showToast(`Đã chọn mẫu: "${selectedItem.name}"`, 'success', 'Chọn Template');
    }

    // Phát sự kiện toàn cục
    window.dispatchEvent(new CustomEvent('template:selected', {
      detail: { templateId: id, template: selectedItem }
    }));
  }

  /**
   * Hiển thị thanh thông báo nổi bên dưới khi có template được chọn
   */
  function updateSelectedBanner() {
    let banner = document.getElementById('selected-template-floating-bar');
    if (!selectedTemplateId) {
      if (banner) banner.classList.add('hidden');
      return;
    }

    const item = rawTemplates.find(function (t) { return t.id === selectedTemplateId; });
    if (!item) {
      if (banner) banner.classList.add('hidden');
      return;
    }

    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'selected-template-floating-bar';
      banner.className = 'fixed bottom-5 left-1/2 -translate-x-1/2 z-50 max-w-xl w-full px-4 animate-bounce-subtle';
      document.body.appendChild(banner);
    }

    banner.innerHTML = `
      <div class="bg-slate-900 text-white px-5 py-3.5 rounded-2xl shadow-2xl border border-slate-700 flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
            <i class="fa-solid fa-circle-check"></i>
          </div>
          <div class="truncate">
            <span class="text-[11px] uppercase tracking-wider text-slate-400 font-bold block">Mẫu đang chọn</span>
            <span class="text-xs sm:text-sm font-extrabold text-white truncate block">${escapeHtml(item.name)}</span>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button onclick="clearSelection()" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition">
            Bỏ chọn
          </button>
          <button onclick="proceedToCreate()" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-lg shadow-indigo-600/30 transition flex items-center gap-1.5">
            <span>Tạo chiến dịch</span>
            <i class="fa-solid fa-arrow-right"></i>
          </button>
        </div>
      </div>
    `;
    banner.classList.remove('hidden');
  }

  function clearSelection() {
    selectedTemplateId = null;
    try {
      sessionStorage.removeItem('selected_template_id');
    } catch (e) {}
    renderTemplates();
    updateSelectedBanner();
  }

  function proceedToCreate() {
    if (!selectedTemplateId) return;
    window.location.href = `create.html?template_id=${selectedTemplateId}`;
  }

  function renderTemplates() {
    const grid = document.getElementById('templates-grid');
    const emptyState = document.getElementById('empty-state');
    const list = getFilteredTemplates();
    const countEl = document.getElementById('filtered-count');
    if (countEl) countEl.textContent = list.length;

    if (!list.length) {
      grid.innerHTML = '';
      if (emptyState) {
        emptyState.classList.remove('hidden');
        const title = emptyState.querySelector('h4');
        const description = emptyState.querySelector('p');
        if (rawTemplates.length) {
          if (title) title.textContent = 'Không tìm thấy mẫu phù hợp';
          if (description) description.textContent = 'Vui lòng thử từ khóa khác hoặc đặt lại bộ lọc.';
        } else {
          if (title) title.textContent = 'Chưa có giao diện mẫu';
          if (description) description.textContent = 'Hiện API chưa có template nào trong cơ sở dữ liệu.';
        }
      }
      return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    grid.innerHTML = list.map(function (item) {
      const isSelected = (selectedTemplateId === item.id);
      const fallbackSvg = createFallbackSvg(item.name, item.id);
      const thumbUrl = item.thumbnail || fallbackSvg;

      const tags = item.placeholders.length
        ? item.placeholders.slice(0, 4).map(function (tag) {
          return `<span class="text-[10px] font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/60">${escapeHtml(tag.replace(/_/g, ' '))}</span>`;
        }).join('')
        : '<span class="text-[10px] text-slate-400">Tối ưu chuẩn CRO</span>';

      return `
        <article class="template-card group bg-white rounded-3xl border ${isSelected ? 'border-indigo-600 ring-4 ring-indigo-500/20 shadow-xl bg-indigo-50/10' : 'border-slate-200 shadow-sm hover:shadow-xl hover:border-indigo-300'} transition-all duration-300 flex flex-col overflow-hidden relative">
          
          <!-- Badge Đang chọn nếu Card được chọn -->
          ${isSelected ? `
            <div class="absolute top-3 left-3 z-20 bg-indigo-600 text-white font-extrabold text-[11px] px-3 py-1 rounded-full shadow-lg flex items-center gap-1.5 animate-fadeIn">
              <i class="fa-solid fa-circle-check"></i>
              <span>Đang chọn</span>
            </div>
          ` : ''}

          <!-- Thumbnail với Image Error Fallback an toàn -->
          <div class="relative h-48 bg-slate-900 overflow-hidden">
            <img 
              src="${escapeHtml(thumbUrl)}" 
              alt="${escapeHtml(item.name)}" 
              class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              loading="lazy"
              onerror="this.onerror=null; this.src='${fallbackSvg}';"
            />
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent"></div>
            
            <div class="absolute top-3 right-3 z-10">
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-slate-900/70 backdrop-blur-md text-indigo-300 border border-white/10 shadow-xs">
                Mẫu #${item.id}
              </span>
            </div>

            <div class="absolute bottom-3 left-3 right-3 z-10 flex items-center gap-1.5 text-[11px] text-white/90 font-medium">
              <i class="fa-solid fa-layer-group text-indigo-300 text-xs"></i>
              <span>${item.placeholders.length} thành phần tùy biến</span>
            </div>
          </div>

          <!-- Card Body -->
          <div class="p-5 flex-1 flex flex-col justify-between space-y-4">
            <div class="space-y-2">
              <h4 class="text-base font-extrabold text-slate-900 group-hover:text-indigo-600 transition truncate" title="${escapeHtml(item.name)}">
                ${escapeHtml(item.name)}
              </h4>
              <p class="text-xs text-slate-500 leading-relaxed line-clamp-2">
                ${escapeHtml(item.description || 'Giao diện landing page tối ưu chuyển đổi, chuẩn Mobile và SEO.')}
              </p>
              <div class="flex flex-wrap gap-1.5 pt-1">${tags}</div>
            </div>

            <!-- Action Buttons: "Xem trước" & "Chọn mẫu" / "Đã chọn" -->
            <div class="pt-3 border-t border-slate-100 flex items-center gap-2.5">
              <button 
                type="button"
                onclick="openPreviewModal(${item.id})" 
                class="flex-1 px-3 py-2.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5"
              >
                <i class="fa-regular fa-eye"></i>
                <span>Xem trước</span>
              </button>
              
              <button 
                type="button"
                onclick="selectTemplate(${item.id})" 
                class="flex-1 px-3 py-2.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${isSelected ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20' : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-600/20'}"
              >
                ${isSelected ? `
                  <i class="fa-solid fa-check"></i>
                  <span>Đã chọn</span>
                ` : `
                  <i class="fa-solid fa-arrow-right"></i>
                  <span>Chọn mẫu</span>
                `}
              </button>
            </div>
          </div>

        </article>
      `;
    }).join('');
  }

  function filterTemplates() {
    const input = document.getElementById('template-search-input');
    currentSearchQuery = input.value;
    const clearBtn = document.getElementById('clear-search-btn');
    if (clearBtn) clearBtn.classList.toggle('hidden', !currentSearchQuery);
    renderTemplates();
  }

  function clearSearch() {
    const input = document.getElementById('template-search-input');
    if (input) input.value = '';
    currentSearchQuery = '';
    const clearBtn = document.getElementById('clear-search-btn');
    if (clearBtn) clearBtn.classList.add('hidden');
    renderTemplates();
  }

  function sortTemplates() {
    const sel = document.getElementById('sort-select');
    if (sel) currentSort = sel.value;
    renderTemplates();
  }

  /**
   * Mở Modal xem trước HTML thực tế
   * Cô lập an toàn qua iframe sandbox
   */
  function openPreviewModal(templateId) {
    const item = rawTemplates.find(function (template) { return template.id === Number(templateId); });
    if (!item) return;

    activePreviewTemplate = item;
    const isSelected = (selectedTemplateId === item.id);

    const titleEl = document.getElementById('modal-template-title');
    const badgeEl = document.getElementById('modal-category-badge');
    const croEl = document.getElementById('modal-template-cro');
    const useBtn = document.getElementById('modal-use-btn');

    if (titleEl) titleEl.textContent = item.name;
    if (badgeEl) badgeEl.textContent = `Mẫu #${item.id}`;
    if (croEl) croEl.innerHTML = '<i class="fa-solid fa-code"></i> Render trực tiếp từ FastAPI Database';

    if (useBtn) {
      useBtn.innerHTML = isSelected
        ? '<i class="fa-solid fa-check"></i><span>Đã chọn mẫu này</span>'
        : '<i class="fa-solid fa-wand-magic-sparkles"></i><span>Chọn mẫu này</span>';
      useBtn.className = isSelected
        ? 'px-3.5 py-1.5 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow-sm transition flex items-center gap-1.5'
        : 'px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition flex items-center gap-1.5';

      useBtn.onclick = function () {
        selectTemplate(item.id);
        closePreviewModal();
      };
    }

    const iframe = document.getElementById('preview-iframe');
    const loader = document.getElementById('modal-iframe-loading');
    if (loader) loader.classList.remove('hidden');
    if (iframe) {
      iframe.classList.add('opacity-0');
      iframe.onload = function () {
        if (loader) loader.classList.add('hidden');
        iframe.classList.remove('opacity-0');
      };
      // Gọi endpoint preview HTML an toàn từ backend
      iframe.src = `${apiBaseUrl}/templates/${item.id}/preview`;
    }

    switchPreviewDevice('desktop');
    const modal = document.getElementById('preview-modal');
    if (modal) {
      modal.classList.remove('hidden');
      document.body.classList.add('overflow-hidden');
    }
  }

  function closePreviewModal() {
    const modal = document.getElementById('preview-modal');
    if (modal) modal.classList.add('hidden');
    const iframe = document.getElementById('preview-iframe');
    if (iframe) iframe.src = 'about:blank';
    activePreviewTemplate = null;
    document.body.classList.remove('overflow-hidden');
  }

  function switchPreviewDevice(device) {
    const wrapper = document.getElementById('preview-canvas-wrapper');
    const desktopButton = document.getElementById('device-btn-desktop');
    const mobileButton = document.getElementById('device-btn-mobile');
    const isMobile = (device === 'mobile');

    if (!wrapper) return;

    if (isMobile) {
      wrapper.classList.remove('max-w-5xl');
      wrapper.classList.add('max-w-sm', 'border-slate-400');
    } else {
      wrapper.classList.remove('max-w-sm', 'border-slate-400');
      wrapper.classList.add('max-w-5xl');
    }

    if (desktopButton) {
      desktopButton.className = isMobile
        ? 'px-2.5 py-1 rounded-lg font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1.5 transition'
        : 'px-2.5 py-1 rounded-lg font-bold bg-white text-indigo-700 shadow-xs flex items-center gap-1.5 transition';
    }
    if (mobileButton) {
      mobileButton.className = isMobile
        ? 'px-2.5 py-1 rounded-lg font-bold bg-white text-indigo-700 shadow-xs flex items-center gap-1.5 transition'
        : 'px-2.5 py-1 rounded-lg font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1.5 transition';
    }
  }

  function useTemplate(templateId) {
    selectTemplate(templateId);
    proceedToCreate();
  }

  async function testSyncApi() {
    if (window.showToast) window.showToast('Đang đồng bộ danh sách template...', 'info', 'Đồng bộ API');
    const succeeded = await loadTemplatesFromApi();
    if (window.showToast) {
      window.showToast(
        succeeded ? `Đã tải ${rawTemplates.length} mẫu từ API.` : 'Không thể đồng bộ template. Vui lòng kiểm tra API.',
        succeeded ? 'success' : 'error',
        'Đồng bộ API'
      );
    }
  }

  // Export các hàm ra window scope
  window.loadTemplatesFromApi = loadTemplatesFromApi;
  window.setCategory = function (category) {
    if (category !== 'all') return;
    renderTemplates();
  };
  window.filterTemplates = filterTemplates;
  window.clearSearch = clearSearch;
  window.sortTemplates = sortTemplates;
  window.openPreviewModal = openPreviewModal;
  window.closePreviewModal = closePreviewModal;
  window.switchPreviewDevice = switchPreviewDevice;
  window.selectTemplate = selectTemplate;
  window.useTemplate = useTemplate;
  window.clearSelection = clearSelection;
  window.proceedToCreate = proceedToCreate;
  window.testSyncApi = testSyncApi;

  document.addEventListener('DOMContentLoaded', function () {
    loadTemplatesFromApi();
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closePreviewModal();
    });
    const modal = document.getElementById('preview-modal');
    if (modal) {
      modal.addEventListener('click', function (event) {
        if (event.target === modal) closePreviewModal();
      });
    }
  });
})();
