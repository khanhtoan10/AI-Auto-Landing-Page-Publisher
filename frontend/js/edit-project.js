/**
 * [FE] Form chỉnh sửa landing page + Live Preview Studio.
 *
 * Luồng nghiệp vụ:
 *   1. GET  /projects/{id}          -> điền dữ liệu cũ vào form.
 *   2. POST /projects/{id}/preview  -> render iframe (debounce 300ms).
 *   3. PUT  /projects/{id}          -> lưu DB + push GitHub + tạo version mới.
 */
(function () {
  'use strict';

  const API_PREFIX = '';
  const DEFAULT_COLOR = '#4F46E5';
  const DEFAULT_CHANGE_SUMMARY = 'Cập nhật landing page: text, giá, link social';
  const THEME_COLORS = {
    indigo: '#4F46E5',
    emerald: '#059669',
    amber: '#D97706',
    dark: '#0F172A',
    blue: '#2563EB',
    violet: '#7C3AED',
    rose: '#E11D48',
    teal: '#0D9488',
    slate: '#334155',
  };

  const state = {
    projectId: null,
    original: null,
    previewTimer: null,
    previewSeq: 0,
    saving: false,
    lastCommitSha: '',
    lastPagesUrl: '',
    device: 'desktop',
  };

  const $ = (id) => document.getElementById(id);

  document.addEventListener('DOMContentLoaded', init);

  // ── Khởi tạo ──────────────────────────────────────────────────────
  function init() {
    bindEvents();

    const params = new URLSearchParams(window.location.search);
    const id = params.get('id') || params.get('project_id');

    if (!id) {
      showLoadError('Đường dẫn thiếu tham số ?id=<project_id>. Hãy mở trang từ danh sách dự án.');
      return;
    }
    if (!/^\d+$/.test(String(id))) {
      showLoadError(`ID dự án "${id}" không hợp lệ.`);
      return;
    }

    state.projectId = String(id);
    loadProjectData(state.projectId);
  }

  function bindEvents() {
    $('edit-project-form')?.addEventListener('submit', handleSave);
    $('btn-reset-form')?.addEventListener('click', resetForm);
    $('btn-refresh-preview')?.addEventListener('click', () => updateLivePreview(true));

    document.querySelectorAll('.device-btn').forEach((btn) => {
      btn.addEventListener('click', () => applyDevice(btn.dataset.device));
    });

    document.querySelectorAll('.color-preset').forEach((btn) => {
      btn.addEventListener('click', () => setColor(btn.dataset.color));
    });

    $('color-theme-picker')?.addEventListener('input', (event) => {
      setColor(event.target.value);
    });

    $('color-theme-hex')?.addEventListener('input', (event) => {
      const raw = event.target.value.replace(/[^0-9a-fA-F]/g, '').slice(0, 6).toUpperCase();
      event.target.value = '#' + raw;
      if (raw.length === 6) {
        const color = '#' + raw;
        $('color-theme-picker').value = color.toLowerCase();
        markActivePreset(color);
        schedulePreview();
      }
    });

    $('price')?.addEventListener('input', updatePriceDisplay);
    $('change-summary')?.addEventListener('input', updateChangeSummaryCounter);

    $('edit-project-form')?.addEventListener('input', (event) => {
      if (event.target.id === 'change-summary') return;
      schedulePreview();
    });

    document.querySelectorAll('[data-close-modal]').forEach((el) => {
      el.addEventListener('click', closeSuccessModal);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeSuccessModal();
    });

    $('btn-copy-sha')?.addEventListener('click', copyCommitSha);
  }

  // ── Tải dữ liệu dự án ─────────────────────────────────────────────
  async function loadProjectData(projectId) {
    setFormLoading(true);
    hideLoadError();

    try {
      const response = await apiRequest(`${API_PREFIX}/projects/${projectId}`);
      const project = response?.data || response?.project || {};
      state.original = normalizeProject(project);
      populateForm(state.original);
      renderProjectMeta(state.original);
      setFormLoading(false);
      updateLivePreview(true);
      loadVersionBadge(projectId);
    } catch (error) {
      setFormLoading(false);
      showLoadError(error.message || 'Không thể tải dữ liệu dự án.');
    }
  }

  async function loadVersionBadge(projectId) {
    try {
      const versions = await apiRequest(`/api/v1/projects/${projectId}/versions`);
      const list = Array.isArray(versions) ? versions : versions?.data || [];
      if (list.length && list[0].version_number) {
        setVersionBadge(list[0].version_number);
      }
    } catch (error) {
      // Không bắt buộc: chỉ là badge hiển thị phiên bản mới nhất.
      console.debug('Không tải được danh sách phiên bản:', error.message);
    }
  }

  function normalizeProject(project) {
    const color = resolveColor(project.color_theme);
    const price = project.price === null || project.price === undefined ? '' : String(project.price);

    return {
      campaign_name: project.campaign_name || '',
      product_name: project.product_name || '',
      product_description: project.product_description || '',
      price,
      color_theme: color,
      image_url: project.image_url || '',
      facebook_url: project.facebook_url || '',
      tiktok_url: project.tiktok_url || '',
      instagram_url: project.instagram_url || '',
      github_pages_url: project.github_pages_url || '',
      repo_url: project.repo_url || '',
      change_summary: '',
    };
  }

  function populateForm(data) {
    setValue('campaign-name', data.campaign_name);
    setValue('product-name', data.product_name);
    setValue('product-description', data.product_description);
    setValue('image-url', data.image_url);
    setValue('facebook-url', data.facebook_url);
    setValue('tiktok-url', data.tiktok_url);
    setValue('instagram-url', data.instagram_url);
    setValue('change-summary', '');

    const priceValue = data.price === '' ? '' : String(Number(data.price) || 0);
    setValue('price', priceValue);

    setColor(data.color_theme || DEFAULT_COLOR, true);
    updatePriceDisplay();
    updateChangeSummaryCounter();
  }

  function renderProjectMeta(project) {
    $('page-project-title').textContent = project.product_name || project.campaign_name || 'Landing Page';

    const pagesUrl = project.github_pages_url || '';
    const btnOpen = $('btn-open-page');
    if (btnOpen) {
      if (pagesUrl) {
        btnOpen.href = pagesUrl;
        btnOpen.classList.remove('hidden');
        btnOpen.classList.add('inline-flex');
        state.lastPagesUrl = pagesUrl;
      } else {
        btnOpen.classList.add('hidden');
        btnOpen.classList.remove('inline-flex');
      }
    }
  }

  function setVersionBadge(versionNumber) {
    const text = $('current-version-text');
    if (text) text.textContent = `v${versionNumber}`;
  }

  // ── Live preview ──────────────────────────────────────────────────
  function schedulePreview() {
    setPreviewStatus('loading');
    clearTimeout(state.previewTimer);
    state.previewTimer = setTimeout(() => updateLivePreview(), 300);
  }

  async function updateLivePreview(force = false) {
    if (!state.projectId || state.saving) return;
    clearTimeout(state.previewTimer);

    const seq = ++state.previewSeq;
    setPreviewStatus('loading');

    try {
      const response = await apiRequest(`${API_PREFIX}/projects/${state.projectId}/preview`, {
        method: 'POST',
        body: JSON.stringify(collectPreviewPayload()),
      });

      if (seq !== state.previewSeq) return; // bỏ qua response cũ (race condition)
      if (!response || !response.rendered_html) {
        throw new Error('Backend không trả về rendered_html.');
      }
      renderPreview(response.rendered_html);
      setPreviewStatus('live');
    } catch (error) {
      if (seq !== state.previewSeq) return;
      console.error('Lỗi xem trước:', error);
      setPreviewStatus('error');
      if (force) {
        window.showToast?.(error.message || 'Không render được bản xem trước.', 'warning', 'Live Preview');
      }
      const empty = $('preview-empty');
      const frame = $('preview-frame');
      if (empty && frame && frame.classList.contains('hidden')) {
        empty.innerHTML = `
          <div class="w-12 h-12 rounded-2xl bg-rose-50 text-rose-500 flex items-center justify-center text-xl">
            <i class="fa-solid fa-triangle-exclamation"></i>
          </div>
          <span class="text-xs font-semibold text-rose-600">Không tải được bản xem trước</span>
          <button type="button" onclick="document.getElementById('btn-refresh-preview').click()" class="text-[11px] font-bold text-indigo-600 hover:text-indigo-800">Thử lại</button>
        `;
        empty.classList.remove('hidden');
        frame.classList.add('hidden');
      }
    }
  }

  function renderPreview(html) {
    const frame = $('preview-frame');
    const empty = $('preview-empty');
    if (!frame) return;

    frame.srcdoc = html;
    frame.classList.remove('hidden');
    empty?.classList.add('hidden');

    const stamp = $('preview-updated-at');
    if (stamp) {
      stamp.textContent = 'Cập nhật ' + new Date().toLocaleTimeString('vi-VN');
    }
  }

  function setPreviewStatus(status) {
    const box = $('preview-status');
    const dot = $('preview-status-dot');
    const text = $('preview-status-text');
    if (!box || !dot || !text) return;

    const configs = {
      live: {
        box: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dot: 'bg-emerald-500',
        text: 'Live',
      },
      loading: {
        box: 'bg-amber-50 text-amber-700 border-amber-200',
        dot: 'bg-amber-500 animate-pulse',
        text: 'Đang cập nhật...',
      },
      error: {
        box: 'bg-rose-50 text-rose-700 border-rose-200',
        dot: 'bg-rose-500',
        text: 'Lỗi xem trước',
      },
    };

    const config = configs[status] || configs.live;
    box.className = `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-bold ${config.box}`;
    dot.className = `w-1.5 h-1.5 rounded-full ${config.dot}`;
    text.textContent = config.text;
  }

  function applyDevice(device) {
    const wrap = $('preview-frame-wrap');
    if (!wrap) return;

    state.device = device;
    const widths = { desktop: '100%', tablet: '768px', mobile: '375px' };
    wrap.style.width = widths[device] || '100%';
    wrap.style.maxWidth = '100%';

    $('device-label').textContent = device === 'desktop' ? '100%' : widths[device];

    document.querySelectorAll('.device-btn').forEach((btn) => {
      const active = btn.dataset.device === device;
      btn.className = active
        ? 'device-btn inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold transition bg-white text-indigo-700 shadow-sm'
        : 'device-btn inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold transition text-slate-500 hover:text-slate-800';
    });
  }

  // ── Lưu & cập nhật website ────────────────────────────────────────
  async function handleSave(event) {
    event.preventDefault();
    if (state.saving) return;

    const payload = collectFormPayload();
    const error = validatePayload(payload);
    if (error) {
      window.showToast?.(error.message, 'warning', 'Kiểm tra lại thông tin');
      $(error.field)?.focus();
      return;
    }

    payload.change_summary = ($('change-summary')?.value || '').trim() || DEFAULT_CHANGE_SUMMARY;

    setSaving(true);
    try {
      const response = await apiRequest(`${API_PREFIX}/projects/${state.projectId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });

      if (response.rendered_html) renderPreview(response.rendered_html);
      if (response.data) {
        state.original = { ...state.original, ...normalizeProject(response.data) };
        renderProjectMeta(state.original);
      }

      state.lastCommitSha = response.commit_sha || '';
      state.lastPagesUrl =
        response.github_pages_url ||
        response.data?.github_pages_url ||
        response.repo_url ||
        state.lastPagesUrl;

      if (response.version_number) setVersionBadge(response.version_number);

      (response.warnings || []).forEach((warning) => {
        console.warn(warning);
        window.showToast?.(warning, 'warning', 'Cảnh báo');
      });

      window.showToast?.(
        response.message || 'Landing page đã được cập nhật thành công!',
        'success',
        'Lưu thành công'
      );
      showSuccessModal(response);
    } catch (error) {
      console.error('Lỗi cập nhật landing page:', error);
      window.showToast?.(error.message || 'Không thể cập nhật landing page.', 'error', 'Cập nhật thất bại');
    } finally {
      setSaving(false);
    }
  }

  function setSaving(saving) {
    state.saving = saving;
    const button = $('btn-save');
    const spinner = $('save-spinner');
    const icon = $('save-icon');
    const label = $('save-btn-text');
    if (!button) return;

    button.disabled = saving;
    spinner?.classList.toggle('hidden', !saving);
    icon?.classList.toggle('hidden', saving);
    if (label) {
      label.textContent = saving ? 'Đang render HTML & push GitHub...' : 'Lưu & Cập nhật Website';
    }
  }

  function resetForm() {
    if (!state.original) return;
    populateForm(state.original);
    updateLivePreview(true);
    window.showToast?.('Đã khôi phục dữ liệu ban đầu của dự án.', 'info', 'Khôi phục gốc');
  }

  // ── Success modal ─────────────────────────────────────────────────
  function showSuccessModal(response) {
    const modal = $('success-modal');
    if (!modal) return;

    const version = response.version_number ? `v${response.version_number}` : '—';
    const sha = response.commit_sha || '';
    const shortSha = sha ? sha.slice(0, 7) : '—';

    $('modal-message').textContent =
      response.message || 'Dữ liệu đã được lưu và website đã nhận bản cập nhật mới nhất.';
    $('modal-version').textContent = version;
    $('modal-commit').textContent = shortSha;
    $('modal-commit').title = sha || '';

    const pagesLink = $('modal-pages-link');
    const targetUrl =
      response.github_pages_url ||
      response.data?.github_pages_url ||
      response.repo_url ||
      state.lastPagesUrl;

    if (targetUrl) {
      pagesLink.href = targetUrl;
      pagesLink.classList.remove('hidden');
      pagesLink.classList.add('inline-flex');
    } else {
      pagesLink.classList.add('hidden');
      pagesLink.classList.remove('inline-flex');
    }

    modal.classList.remove('hidden');
  }

  function closeSuccessModal() {
    $('success-modal')?.classList.add('hidden');
  }

  async function copyCommitSha() {
    if (!state.lastCommitSha) return;
    try {
      await navigator.clipboard.writeText(state.lastCommitSha);
      window.showToast?.('Đã sao chép commit SHA vào clipboard.', 'success', 'Sao chép');
    } catch (error) {
      window.showToast?.('Trình duyệt không cho phép sao chép tự động.', 'warning', 'Sao chép');
    }
  }

  // ── Thu thập & kiểm tra dữ liệu ───────────────────────────────────
  function collectFormPayload() {
    const priceRaw = ($('price')?.value || '').trim();
    return {
      campaign_name: ($('campaign-name')?.value || '').trim(),
      product_name: ($('product-name')?.value || '').trim(),
      product_description: ($('product-description')?.value || '').trim() || null,
      price: priceRaw === '' ? null : Number(priceRaw),
      color_theme: normalizeHex($('color-theme-hex')?.value) || DEFAULT_COLOR,
      image_url: ($('image-url')?.value || '').trim() || null,
      facebook_url: ($('facebook-url')?.value || '').trim() || null,
      tiktok_url: ($('tiktok-url')?.value || '').trim() || null,
      instagram_url: ($('instagram-url')?.value || '').trim() || null,
    };
  }

  function collectPreviewPayload() {
    return collectFormPayload();
  }

  function validatePayload(payload) {
    if (!payload.campaign_name) {
      return { field: 'campaign-name', message: 'Vui lòng nhập tên chiến dịch.' };
    }
    if (!payload.product_name) {
      return { field: 'product-name', message: 'Vui lòng nhập tên sản phẩm / thương hiệu.' };
    }
    if (!normalizeHex($('color-theme-hex')?.value)) {
      return { field: 'color-theme-hex', message: 'Màu chủ đạo phải là mã HEX 6 ký tự, ví dụ #4F46E5.' };
    }
    if (payload.price !== null && (Number.isNaN(payload.price) || payload.price < 0)) {
      return { field: 'price', message: 'Giá niêm yết phải là số không âm.' };
    }
    return null;
  }

  // ── Helpers ───────────────────────────────────────────────────────
  function setValue(id, value) {
    const el = $(id);
    if (el) el.value = value ?? '';
  }

  function resolveColor(value) {
    if (!value) return DEFAULT_COLOR;
    const text = String(value).trim();
    if (/^#[0-9a-fA-F]{6}$/.test(text)) return text.toUpperCase();
    return THEME_COLORS[text.toLowerCase()] || DEFAULT_COLOR;
  }

  function normalizeHex(value) {
    const text = String(value || '').trim();
    if (/^#[0-9a-fA-F]{6}$/.test(text)) return text.toUpperCase();
    return null;
  }

  function setColor(color, silent = false) {
    const hex = resolveColor(color).toUpperCase();
    const picker = $('color-theme-picker');
    const input = $('color-theme-hex');
    if (picker) picker.value = hex.toLowerCase();
    if (input) input.value = hex;
    markActivePreset(hex);
    if (!silent) schedulePreview();
  }

  function markActivePreset(color) {
    document.querySelectorAll('.color-preset').forEach((btn) => {
      const isActive = (btn.dataset.color || '').toUpperCase() === color.toUpperCase();
      btn.classList.toggle('ring-slate-900', isActive);
      btn.classList.toggle('ring-transparent', !isActive);
    });
  }

  function updatePriceDisplay() {
    const holder = $('price-formatted');
    if (!holder) return;

    const raw = ($('price')?.value || '').trim();
    const amount = Number(raw);
    const formatted =
      raw === '' || Number.isNaN(amount)
        ? 'Liên hệ'
        : new Intl.NumberFormat('vi-VN').format(amount) + ' ₫';

    holder.innerHTML = `Hiển thị trên trang: <span class="text-indigo-600 font-bold">${formatted}</span>`;
  }

  function updateChangeSummaryCounter() {
    const counter = $('change-summary-counter');
    if (!counter) return;
    const length = ($('change-summary')?.value || '').length;
    counter.textContent = `${length}/255`;
  }

  function setFormLoading(loading) {
    const overlay = $('form-loading');
    if (!overlay) return;
    overlay.classList.toggle('hidden', !loading);
    overlay.classList.toggle('flex', loading);
    $('btn-save').disabled = loading;
  }

  function showLoadError(message) {
    const box = $('load-error');
    const text = $('load-error-message');
    if (text) text.textContent = message;
    box?.classList.remove('hidden');
    setFormLoading(false);
    setPreviewStatus('error');
  }

  function hideLoadError() {
    $('load-error')?.classList.add('hidden');
  }
})();
