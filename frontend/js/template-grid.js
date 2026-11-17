/**
 * Template Grid & Preview Manager
 * AI Auto Landing Page Publisher
 * 
 * Chức năng:
 * - Gọi API GET /templates lấy danh sách Template từ database
 * - Hiển thị lưới thẻ Template (Grid Card) chuẩn Tailwind CSS, responsive
 * - Hỗ trợ đầy đủ trạng thái: Loading (Skeleton), Error (Retry), Empty, Image Error (Fallback), Selected
 * - Xem trước nội dung HTML thực tế qua Modal + iframe sandbox (GET /templates/{id}/preview)
 * - Quản lý trạng thái template_id được chọn và tích hợp luồng tạo chiến dịch
 */

(function (window) {
  'use strict';

  const API_URL = (typeof window.API_BASE_URL !== 'undefined') ? window.API_BASE_URL : 'http://127.0.0.1:8000';

  /**
   * Tạo ảnh fallback SVG gradient theo ID và tên template khi thumbnail bị lỗi hoặc không tồn tại
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
    const cleanName = (name || 'Landing Page Template').replace(/[<>&"]/g, '');

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
        <text x="60" y="175" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="26" font-weight="800" fill="#ffffff">${cleanName}</text>
        <text x="60" y="215" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="14" font-weight="600" fill="#ffffff" opacity="0.9">Mẫu Chuẩn CRO • Tối Ưu Mobile & SEO</text>
        <rect x="60" y="245" width="130" height="32" rx="8" fill="#ffffff" opacity="0.25"/>
        <text x="80" y="266" font-family="'Plus Jakarta Sans', system-ui, sans-serif" font-size="12" font-weight="700" fill="#ffffff">Preview HTML</text>
      </svg>
    `;
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg.trim());
  }

  /**
   * Chuẩn hóa URL thumbnail (nếu đường dẫn tương đối từ backend thì nối thêm API_URL)
   */
  function resolveThumbnail(rawUrl, name, id) {
    if (!rawUrl || typeof rawUrl !== 'string' || rawUrl.trim() === '') {
      return createFallbackSvg(name, id);
    }
    const trimmed = rawUrl.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('data:')) {
      return trimmed;
    }
    if (trimmed.startsWith('/')) {
      return `${API_URL}${trimmed}`;
    }
    return `${API_URL}/${trimmed}`;
  }

  /**
   * Component Lưới Template Grid
   */
  class TemplateGrid {
    constructor(options = {}) {
      this.containerId = options.containerId || 'templates-grid';
      this.modalId = options.modalId || 'template-preview-modal';
      this.selectedTemplateId = options.selectedTemplateId ? parseInt(options.selectedTemplateId, 10) : null;
      this.onSelect = typeof options.onSelect === 'function' ? options.onSelect : null;
      this.onLoaded = typeof options.onLoaded === 'function' ? options.onLoaded : null;
      this.actionType = options.actionType || 'select'; // 'select' (chọn mẫu trong wizard) hoặc 'navigate' (chuyển sang create.html)
      this.templates = [];
      this.isLoading = false;
      this.error = null;
      this.activePreviewId = null;

      this.init();
    }

    init() {
      this.ensureModalExists();
      this.fetchTemplates();
    }

    /**
     * Lấy danh sách Template từ API GET /templates
     */
    async fetchTemplates() {
      this.isLoading = true;
      this.error = null;
      this.render();

      try {
        let result = null;
        if (typeof window.apiRequest === 'function') {
          result = await window.apiRequest('/templates');
        } else {
          const res = await fetch(`${API_URL}/templates`);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          result = await res.json();
        }

        if (result && Array.isArray(result.data)) {
          this.templates = result.data;
        } else if (Array.isArray(result)) {
          this.templates = result;
        } else {
          this.templates = [];
        }

        this.isLoading = false;
        this.render();

        if (this.onLoaded) {
          this.onLoaded(this.templates);
        }

        // Tự động kích hoạt chọn template nếu ID đã được xác định trước
        if (this.selectedTemplateId) {
          const found = this.templates.find(t => t.id === this.selectedTemplateId);
          if (found && this.onSelect) {
            this.onSelect(this.selectedTemplateId, found);
          }
        }
      } catch (err) {
        console.error('Lỗi khi tải danh sách templates:', err);
        this.isLoading = false;
        this.error = err.message || 'Không thể kết nối đến máy chủ API.';
        this.render();
      }
    }

    /**
     * Chọn một template theo ID
     */
    selectTemplate(templateId) {
      const id = parseInt(templateId, 10);
      if (isNaN(id)) return;

      this.selectedTemplateId = id;
      const selectedTemplate = this.templates.find(t => t.id === id);

      // Re-render để cập nhật trạng thái trực quan các Card
      this.render();

      if (this.actionType === 'navigate') {
        window.location.href = `create.html?template_id=${id}`;
        return;
      }

      if (this.onSelect && selectedTemplate) {
        this.onSelect(id, selectedTemplate);
      }

      // Thông báo toast
      if (window.showToast && selectedTemplate) {
        window.showToast(`Đã chọn mẫu: "${selectedTemplate.name}"`, 'success', 'Chọn Template');
      }

      // Phát Custom Event cho các component khác lắng nghe
      window.dispatchEvent(new CustomEvent('template:selected', {
        detail: { templateId: id, template: selectedTemplate }
      }));
    }

    /**
     * Mở Modal xem trước HTML thực tế
     */
    openPreview(templateId) {
      const id = parseInt(templateId, 10);
      const template = this.templates.find(t => t.id === id);
      if (!template) return;

      this.activePreviewId = id;
      const modal = document.getElementById(this.modalId);
      if (!modal) return;

      const titleEl = modal.querySelector('.preview-modal-title');
      const descEl = modal.querySelector('.preview-modal-desc');
      const frameEl = modal.querySelector('.preview-modal-iframe');
      const selectBtn = modal.querySelector('.preview-modal-select-btn');
      const skeletonEl = modal.querySelector('.preview-modal-skeleton');

      if (titleEl) titleEl.textContent = template.name;
      if (descEl) descEl.textContent = template.description || 'Mẫu giao diện Landing Page chuyển đổi cao';

      // Nạp iframe an toàn từ endpoint preview
      if (frameEl) {
        if (skeletonEl) skeletonEl.classList.remove('hidden');
        frameEl.classList.add('opacity-0');
        frameEl.src = `${API_URL}/templates/${id}/preview`;

        frameEl.onload = () => {
          if (skeletonEl) skeletonEl.classList.add('hidden');
          frameEl.classList.remove('opacity-0');
        };
      }

      // Nút "Chọn mẫu này" trong Modal
      if (selectBtn) {
        const isSelected = this.selectedTemplateId === id;
        selectBtn.innerHTML = isSelected
          ? '<i class="fa-solid fa-check"></i><span>Đã chọn mẫu này</span>'
          : '<i class="fa-solid fa-wand-magic-sparkles"></i><span>Chọn mẫu này</span>';
        selectBtn.className = isSelected
          ? 'px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow-sm transition flex items-center gap-1.5'
          : 'px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition flex items-center gap-1.5';

        selectBtn.onclick = () => {
          this.selectTemplate(id);
          this.closePreview();
        };
      }

      modal.classList.remove('hidden');
      document.body.classList.add('overflow-hidden');
    }

    /**
     * Đóng Modal xem trước
     */
    closePreview() {
      const modal = document.getElementById(this.modalId);
      if (modal) {
        modal.classList.add('hidden');
        const frameEl = modal.querySelector('.preview-modal-iframe');
        if (frameEl) frameEl.src = 'about:blank';
      }
      this.activePreviewId = null;
      document.body.classList.remove('overflow-hidden');
    }

    /**
     * Chuyển đổi kích thước thiết bị (Desktop / Mobile) trong Modal
     */
    switchDevice(device) {
      const modal = document.getElementById(this.modalId);
      if (!modal) return;

      const wrapper = modal.querySelector('.preview-canvas-wrapper');
      const btnDesktop = modal.querySelector('.btn-device-desktop');
      const btnMobile = modal.querySelector('.btn-device-mobile');

      if (!wrapper) return;

      if (device === 'mobile') {
        wrapper.style.maxWidth = '390px';
        wrapper.style.height = '780px';
        wrapper.classList.add('border-slate-800', 'border-[10px]', 'rounded-[40px]', 'shadow-2xl');
        if (btnMobile) {
          btnMobile.className = 'btn-device-mobile px-3 py-1.5 rounded-lg font-bold bg-white text-indigo-700 shadow-xs flex items-center gap-1.5 transition text-xs';
        }
        if (btnDesktop) {
          btnDesktop.className = 'btn-device-desktop px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1.5 transition text-xs';
        }
      } else {
        wrapper.style.maxWidth = '100%';
        wrapper.style.height = '100%';
        wrapper.classList.remove('border-slate-800', 'border-[10px]', 'rounded-[40px]');
        if (btnDesktop) {
          btnDesktop.className = 'btn-device-desktop px-3 py-1.5 rounded-lg font-bold bg-white text-indigo-700 shadow-xs flex items-center gap-1.5 transition text-xs';
        }
        if (btnMobile) {
          btnMobile.className = 'btn-device-mobile px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1.5 transition text-xs';
        }
      }
    }

    /**
     * Tạo Modal DOM nếu trang chưa có sẵn
     */
    ensureModalExists() {
      if (document.getElementById(this.modalId)) return;

      const modalHtml = `
        <div id="${this.modalId}" class="fixed inset-0 z-[100] hidden flex items-center justify-center bg-slate-950/75 backdrop-blur-sm p-3 sm:p-6 transition-all duration-300">
          <div class="bg-white w-full max-w-6xl h-[90vh] rounded-3xl shadow-2xl flex flex-col overflow-hidden border border-slate-200 animate-fadeIn">
            <!-- Modal Header -->
            <div class="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/90 shrink-0">
              <div class="flex items-center gap-3 min-w-0">
                <span class="w-8 h-8 rounded-xl bg-indigo-100 text-indigo-600 font-bold flex items-center justify-center shrink-0 text-sm">
                  <i class="fa-solid fa-eye"></i>
                </span>
                <div class="truncate">
                  <h3 class="preview-modal-title text-sm sm:text-base font-extrabold text-slate-900 truncate">Xem trước Template</h3>
                  <p class="preview-modal-desc text-xs text-slate-500 truncate max-w-xl">Mẫu giao diện chuẩn chuyển đổi cao</p>
                </div>
              </div>

              <!-- Device Switcher & Action Buttons -->
              <div class="flex items-center gap-2 sm:gap-3 shrink-0">
                <div class="hidden sm:flex bg-slate-200/80 p-0.5 rounded-xl">
                  <button type="button" class="btn-device-desktop px-3 py-1.5 rounded-lg font-bold bg-white text-indigo-700 shadow-xs flex items-center gap-1.5 transition text-xs">
                    <i class="fa-solid fa-desktop"></i>
                    <span>Desktop</span>
                  </button>
                  <button type="button" class="btn-device-mobile px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1.5 transition text-xs">
                    <i class="fa-solid fa-mobile-screen"></i>
                    <span>Mobile</span>
                  </button>
                </div>

                <button type="button" class="preview-modal-select-btn px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition flex items-center gap-1.5">
                  <i class="fa-solid fa-wand-magic-sparkles"></i>
                  <span>Chọn mẫu này</span>
                </button>

                <button type="button" class="btn-modal-close w-8 h-8 rounded-xl bg-slate-200/70 hover:bg-slate-300 text-slate-600 flex items-center justify-center transition">
                  <i class="fa-solid fa-xmark text-sm"></i>
                </button>
              </div>
            </div>

            <!-- Modal Body (Preview Canvas Container) -->
            <div class="flex-1 bg-slate-100 overflow-y-auto p-3 sm:p-5 flex justify-center items-center custom-scrollbar relative">
              <div class="preview-canvas-wrapper w-full h-full bg-white rounded-2xl shadow-md border border-slate-200 overflow-hidden transition-all duration-300 flex flex-col relative">
                
                <!-- Skeleton Loading for iframe -->
                <div class="preview-modal-skeleton absolute inset-0 bg-slate-50 flex flex-col items-center justify-center gap-3 z-10 transition-opacity">
                  <div class="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                  <span class="text-xs font-semibold text-slate-500">Đang nạp mã HTML Template thực tế...</span>
                </div>

                <!-- Iframe Sandbox Cô lập HTML Preview an toàn -->
                <iframe class="preview-modal-iframe w-full h-full border-0 rounded-2xl bg-white transition-opacity duration-300" sandbox="allow-same-origin allow-scripts" src="about:blank"></iframe>
              </div>
            </div>

            <!-- Modal Footer -->
            <div class="px-5 py-2.5 border-t border-slate-200 bg-white flex items-center justify-between text-xs text-slate-500 shrink-0">
              <div class="flex items-center gap-4">
                <span class="flex items-center gap-1 text-emerald-600 font-semibold"><i class="fa-solid fa-shield-halved"></i> Iframe Sandbox An Toàn</span>
                <span class="hidden sm:inline-flex items-center gap-1"><i class="fa-solid fa-bolt text-amber-500"></i> Render Trực Tiếp Từ FastAPI</span>
              </div>
              <button type="button" class="btn-modal-close text-slate-500 hover:text-slate-800 font-semibold text-xs">Đóng xem trước</button>
            </div>
          </div>
        </div>
      `;

      document.body.insertAdjacentHTML('beforeend', modalHtml);

      const modalEl = document.getElementById(this.modalId);
      if (modalEl) {
        modalEl.querySelectorAll('.btn-modal-close').forEach(btn => {
          btn.addEventListener('click', () => this.closePreview());
        });
        modalEl.addEventListener('click', (e) => {
          if (e.target === modalEl) this.closePreview();
        });
        const btnDesktop = modalEl.querySelector('.btn-device-desktop');
        if (btnDesktop) btnDesktop.addEventListener('click', () => this.switchDevice('desktop'));
        const btnMobile = modalEl.querySelector('.btn-device-mobile');
        if (btnMobile) btnMobile.addEventListener('click', () => this.switchDevice('mobile'));
      }

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modalEl.classList.contains('hidden')) {
          this.closePreview();
        }
      });
    }

    /**
     * Render toàn bộ giao diện Template Grid
     */
    render() {
      const container = document.getElementById(this.containerId);
      if (!container) return;

      // 1. TRẠNG THÁI LOADING (Skeleton Cards)
      if (this.isLoading) {
        container.innerHTML = `
          <div class="col-span-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            ${[1, 2, 3].map(() => `
              <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-4 space-y-4 animate-pulse">
                <div class="h-48 bg-slate-200 rounded-2xl w-full"></div>
                <div class="space-y-2">
                  <div class="h-5 bg-slate-200 rounded-lg w-3/4"></div>
                  <div class="h-3.5 bg-slate-200 rounded-lg w-full"></div>
                  <div class="h-3.5 bg-slate-200 rounded-lg w-2/3"></div>
                </div>
                <div class="flex gap-2 pt-2">
                  <div class="h-9 bg-slate-200 rounded-xl flex-1"></div>
                  <div class="h-9 bg-slate-200 rounded-xl flex-1"></div>
                </div>
              </div>
            `).join('')}
          </div>
        `;
        return;
      }

      // 2. TRẠNG THÁI ERROR (Có nút Thử tải lại)
      if (this.error) {
        container.innerHTML = `
          <div class="col-span-full text-center py-12 px-6 bg-white rounded-3xl border border-rose-200 shadow-sm">
            <div class="w-14 h-14 mx-auto rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center text-2xl mb-3">
              <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
            <h4 class="text-base font-bold text-slate-800">Không thể tải danh sách Template</h4>
            <p class="text-xs text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">${this.error}</p>
            <button type="button" class="btn-retry mt-4 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-md shadow-indigo-600/20 transition flex items-center gap-2 mx-auto">
              <i class="fa-solid fa-rotate-right"></i>
              <span>Thử tải lại</span>
            </button>
          </div>
        `;
        const retryBtn = container.querySelector('.btn-retry');
        if (retryBtn) retryBtn.onclick = () => this.fetchTemplates();
        return;
      }

      // 3. TRẠNG THÁI EMPTY
      if (!this.templates || this.templates.length === 0) {
        container.innerHTML = `
          <div class="col-span-full text-center py-14 px-6 bg-white rounded-3xl border border-slate-200 shadow-sm">
            <div class="w-16 h-16 mx-auto rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center text-3xl mb-3">
              <i class="fa-solid fa-layer-group"></i>
            </div>
            <h4 class="text-base font-bold text-slate-800">Chưa có mẫu giao diện nào</h4>
            <p class="text-xs text-slate-500 mt-1 max-w-md mx-auto">Cơ sở dữ liệu templates hiện đang trống. Hãy kiểm tra lại migration hoặc seed dữ liệu.</p>
          </div>
        `;
        return;
      }

      // 4. DANH SÁCH TEMPLATE GRID CARDS
      const cardsHtml = this.templates.map(item => {
        const isSelected = (this.selectedTemplateId === item.id);
        const thumbUrl = resolveThumbnail(item.thumbnail_url || item.thumbnail, item.name, item.id);
        const fallbackSvg = createFallbackSvg(item.name, item.id);
        const placeholders = Array.isArray(item.placeholders) ? item.placeholders : [];

        return `
          <div data-template-id="${item.id}" class="template-card group bg-white rounded-3xl border ${isSelected ? 'border-indigo-600 ring-4 ring-indigo-500/20 shadow-xl bg-indigo-50/10' : 'border-slate-200/90 shadow-sm hover:shadow-xl hover:border-indigo-300'} transition-all duration-300 flex flex-col overflow-hidden relative">
            
            <!-- Selected Badge Indicator -->
            ${isSelected ? `
              <div class="absolute top-3 left-3 z-20 bg-indigo-600 text-white font-extrabold text-[11px] px-3 py-1 rounded-full shadow-lg flex items-center gap-1.5 animate-fadeIn">
                <i class="fa-solid fa-circle-check"></i>
                <span>Đang chọn</span>
              </div>
            ` : ''}

            <!-- Card Thumbnail with Image Fallback -->
            <div class="relative h-48 sm:h-52 bg-slate-900 overflow-hidden">
              <img 
                src="${thumbUrl}" 
                alt="${item.name}" 
                class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                loading="lazy"
                onerror="this.onerror=null; this.src='${fallbackSvg}';"
              />
              <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent"></div>

              <!-- Top Right Template ID Badge -->
              <div class="absolute top-3 right-3 z-10">
                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-slate-900/70 backdrop-blur-md text-indigo-300 border border-white/10 shadow-xs">
                  ID: #${item.id}
                </span>
              </div>

              <!-- Placeholders Chips Preview (Bottom of Thumbnail) -->
              <div class="absolute bottom-3 left-3 right-3 z-10 flex flex-wrap gap-1.5">
                ${placeholders.slice(0, 3).map(p => `
                  <span class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-white/20 backdrop-blur-md text-white border border-white/20">
                    ${p}
                  </span>
                `).join('')}
                ${placeholders.length > 3 ? `
                  <span class="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-white/30 backdrop-blur-md text-white">
                    +${placeholders.length - 3}
                  </span>
                ` : ''}
              </div>
            </div>

            <!-- Card Body -->
            <div class="p-5 flex-1 flex flex-col justify-between space-y-4">
              <div class="space-y-1.5">
                <h4 class="text-base font-extrabold text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-1">
                  ${item.name}
                </h4>
                <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                  ${item.description || 'Giao diện Landing Page tối ưu chuyển đổi chuẩn CRO & Mobile.'}
                </p>
              </div>

              <!-- Action Buttons -->
              <div class="pt-3 border-t border-slate-100 flex items-center gap-2.5">
                <button 
                  type="button" 
                  class="btn-preview-template flex-1 px-3 py-2.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5"
                  data-id="${item.id}"
                >
                  <i class="fa-regular fa-eye"></i>
                  <span>Xem trước</span>
                </button>

                <button 
                  type="button" 
                  class="btn-select-template flex-1 px-3 py-2.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${isSelected ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20' : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-600/20'}"
                  data-id="${item.id}"
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

          </div>
        `;
      }).join('');

      container.innerHTML = cardsHtml;

      // Gắn sự kiện click cho các nút
      container.querySelectorAll('.btn-preview-template').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const id = btn.getAttribute('data-id');
          this.openPreview(id);
        });
      });

      container.querySelectorAll('.btn-select-template').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const id = btn.getAttribute('data-id');
          this.selectTemplate(id);
        });
      });

      // Click vào cả card cũng chọn template
      container.querySelectorAll('.template-card').forEach(card => {
        card.addEventListener('click', () => {
          const id = card.getAttribute('data-template-id');
          this.selectTemplate(id);
        });
      });
    }
  }

  // Export module ra window scope
  window.TemplateGrid = TemplateGrid;
  window.createFallbackSvg = createFallbackSvg;
  window.resolveThumbnail = resolveThumbnail;

})(window);
