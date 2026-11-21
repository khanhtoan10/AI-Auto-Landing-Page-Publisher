/**
 * Trang Preview index.html được AI sinh ra
 * - Hiển thị HTML thực tế trong iframe (srcdoc)
 * - Nút Generate Again gọi POST /projects/{id}/generate và cập nhật iframe
 * - Nút Deploy kết nối POST /projects/{id}/deploy và chuyển sang deployments.html
 */
(function () {
  'use strict';

  const state = {
    projectId: null,
    project: null,
    currentHtml: '',
    isGenerating: false,
    isDeploying: false,
    viewport: 'desktop',
  };

  const $ = (id) => document.getElementById(id);

  document.addEventListener('DOMContentLoaded', init);

  function init() {
    bindEvents();

    const params = new URLSearchParams(window.location.search);
    const rawId =
      params.get('id') ||
      params.get('project_id') ||
      sessionStorage.getItem('last_generated_project_id');

    if (!rawId || !/^\d+$/.test(String(rawId).trim())) {
      setLoadingOverlay(false);
      showError(
        'Thiếu hoặc sai mã dự án (?id=...). Vui lòng chọn một dự án từ danh sách dự án hoặc tạo mới.'
      );
      setStatusBadge('error', 'Thiếu ID dự án');
      setButtonsDisabled(true);
      return;
    }

    state.projectId = String(rawId).trim();
    try {
      sessionStorage.setItem('last_generated_project_id', state.projectId);
    } catch (e) {}

    const editLink = $('btn-edit-project');
    if (editLink) {
      editLink.href = `edit-project.html?id=${encodeURIComponent(state.projectId)}`;
    }

    const autoGenerate = params.get('autogenerate') === '1';
    loadInitialPreview(autoGenerate);
  }

  function bindEvents() {
    $('btn-generate-again')?.addEventListener('click', () => handleGenerateAgain());
    $('btn-empty-generate')?.addEventListener('click', () => handleGenerateAgain());
    $('btn-deploy')?.addEventListener('click', handleDeploy);
    $('btn-retry-load')?.addEventListener('click', () => loadInitialPreview(false));

    document.querySelectorAll('.viewport-btn').forEach((btn) => {
      btn.addEventListener('click', () => switchViewport(btn.dataset.viewport));
    });
  }

  /**
   * Tải thông tin dự án và hiển thị HTML đã sinh trong iframe.
   */
  async function loadInitialPreview(autoGenerate = false) {
    if (!state.projectId) return;

    hideError();
    setLoadingOverlay(
      true,
      autoGenerate ? 'AI đang sinh nội dung landing page...' : 'Đang tải bản xem trước index.html...',
      autoGenerate
        ? 'Gemini đang phân tích dữ liệu dự án và lắp ráp giao diện HTML hoàn chỉnh.'
        : 'Đang lấy dữ liệu dự án và render trang HTML thực tế từ máy chủ.'
    );
    setStatusBadge('loading', 'Đang tải...');

    try {
      const projectRes = await apiRequest(`/projects/${state.projectId}`);
      const project = projectRes?.data || projectRes?.project || projectRes;
      if (!project || !project.id) {
        throw new Error('Không tìm thấy thông tin dự án.');
      }

      state.project = project;
      updateProjectHeader(project);

      const hasGeneratedJson =
        project.raw_json_data &&
        typeof project.raw_json_data === 'object' &&
        Object.keys(project.raw_json_data).length > 0;

      if (autoGenerate || !hasGeneratedJson) {
        setLoadingOverlay(false);
        await handleGenerateAgain(true);
        return;
      }

      // Render HTML thực tế từ dữ liệu project + raw_json_data đã sinh
      const previewRes = await apiRequest(`/projects/${state.projectId}/preview`, {
        method: 'POST',
        body: JSON.stringify({}),
      });

      const html = extractHtmlFromResponse(previewRes);
      if (!html) {
        setLoadingOverlay(false);
        showEmptyState(true);
        setStatusBadge('idle', 'Chưa có HTML');
        return;
      }

      renderHtmlInIframe(html);
      setLoadingOverlay(false);
      setStatusBadge('ready', 'Sẵn sàng Deploy');
    } catch (error) {
      console.error('Lỗi tải Preview:', error);
      setLoadingOverlay(false);
      showError(error.message || 'Không thể tải dữ liệu xem trước từ máy chủ.');
      setStatusBadge('error', 'Lỗi tải dữ liệu');
    }
  }

  /**
   * Nút Generate Again: gọi lại API POST /projects/{id}/generate đã có
   * và cập nhật nội dung mới lên iframe.
   */
  async function handleGenerateAgain(isInitialAuto = false) {
    if (!state.projectId || state.isGenerating || state.isDeploying) return;

    state.isGenerating = true;
    hideError();
    showEmptyState(false);
    setGenerateLoadingState(true);
    setStatusBadge('loading', 'AI đang sinh lại...');
    setLoadingOverlay(
      true,
      isInitialAuto ? 'AI đang khởi tạo trang index.html...' : 'AI đang sinh lại nội dung mới...',
      'Vui lòng chờ trong giây lát, không đóng hoặc tải lại trang.'
    );

    try {
      const genRes = await apiRequest(`/projects/${state.projectId}/generate`, {
        method: 'POST',
      });

      let html = extractHtmlFromResponse(genRes);

      // Fallback: nếu backend chỉ trả về JSON Gemini mà chưa kèm rendered_html,
      // gọi tiếp endpoint /projects/{id}/preview đã có để render HTML thực tế từ dữ liệu mới.
      if (!html) {
        const previewRes = await apiRequest(`/projects/${state.projectId}/preview`, {
          method: 'POST',
          body: JSON.stringify({}),
        });
        html = extractHtmlFromResponse(previewRes);
      }

      if (!html) {
        throw new Error('API không trả về nội dung HTML hợp lệ để hiển thị.');
      }

      renderHtmlInIframe(html);
      setStatusBadge('ready', 'Đã cập nhật bản mới');
      if (!isInitialAuto) {
        window.showToast?.(
          'Đã sinh lại nội dung landing page thành công!',
          'success',
          'Generate Again'
        );
      }
    } catch (error) {
      console.error('Lỗi Generate Again:', error);
      const errMsg = error.message || 'Không thể sinh lại nội dung từ AI. Vui lòng thử lại.';
      showError(errMsg);
      setStatusBadge('error', 'Sinh nội dung thất bại');
      window.showToast?.(errMsg, 'error', 'Lỗi Generate AI');

      if (!state.currentHtml) {
        showEmptyState(true);
      }
    } finally {
      state.isGenerating = false;
      setGenerateLoadingState(false);
      setLoadingOverlay(false);
    }
  }

  /**
   * Nút Deploy: tích hợp với luồng deploy hiện có của dự án.
   */
  async function handleDeploy() {
    if (!state.projectId || state.isGenerating || state.isDeploying) return;

    if (!state.currentHtml) {
      window.showToast?.(
        'Vui lòng sinh nội dung HTML trước khi chuyển sang bước Deploy.',
        'warning',
        'Chưa có nội dung'
      );
      return;
    }

    state.isDeploying = true;
    hideError();
    setDeployLoadingState(true);

    try {
      const deployRes = await apiRequest(`/projects/${state.projectId}/deploy`, {
        method: 'POST',
      });

      window.showToast?.(
        deployRes?.message || 'Đang chuyển sang trang triển khai & xuất bản...',
        'success',
        'Sẵn sàng Deploy'
      );

      setTimeout(() => {
        window.location.href = `deployments.html?project_id=${encodeURIComponent(state.projectId)}`;
      }, 450);
    } catch (error) {
      console.error('Lỗi điều hướng Deploy:', error);
      const errMsg = error.message || 'Không thể kết nối tới luồng Deploy.';
      showError(errMsg);
      window.showToast?.(errMsg, 'error', 'Lỗi Deploy');
      state.isDeploying = false;
      setDeployLoadingState(false);
    }
  }

  // ── Render & UI Helpers ───────────────────────────────────────────

  function extractHtmlFromResponse(response) {
    if (!response || typeof response !== 'object') return '';
    const html =
      response.rendered_html ||
      response.html ||
      response.data?.rendered_html ||
      response.data?.html ||
      '';
    return typeof html === 'string' && html.trim().length > 0 ? html : '';
  }

  function renderHtmlInIframe(html) {
    const iframe = $('preview-iframe');
    if (!iframe) return;

    state.currentHtml = html;
    showEmptyState(false);

    // Gán trực tiếp HTML vào srcdoc để trình duyệt render đầy đủ trang web
    iframe.srcdoc = html;
    iframe.classList.remove('hidden');

    const updatedEl = $('preview-last-updated');
    if (updatedEl) {
      updatedEl.textContent = 'Cập nhật lúc ' + new Date().toLocaleTimeString('vi-VN');
    }
  }

  function updateProjectHeader(project) {
    const title = project.product_name || project.campaign_name || `Dự án #${project.id}`;
    const titleEl = $('preview-project-title');
    const subEl = $('preview-project-subtitle');
    const urlBarEl = $('preview-url-bar');

    if (titleEl) titleEl.textContent = title;
    if (subEl) {
      const campaign = project.campaign_name ? `Chiến dịch: ${project.campaign_name}` : '';
      subEl.textContent = `${campaign}${campaign ? ' • ' : ''}ID #${project.id} • index.html`;
    }
    if (urlBarEl) {
      urlBarEl.textContent =
        project.github_pages_url || `preview://project-${project.id}/index.html`;
    }
  }

  function switchViewport(viewport) {
    const shell = $('preview-browser-shell');
    const label = $('preview-viewport-label');
    if (!shell) return;

    state.viewport = viewport;
    const widths = {
      desktop: '100%',
      tablet: '768px',
      mobile: '390px',
    };

    shell.style.width = widths[viewport] || '100%';
    shell.style.maxWidth = '100%';
    if (label) {
      label.textContent = viewport === 'desktop' ? '100%' : widths[viewport];
    }

    document.querySelectorAll('.viewport-btn').forEach((btn) => {
      const active = btn.dataset.viewport === viewport;
      btn.className = active
        ? 'viewport-btn inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-white text-indigo-700 shadow-xs transition'
        : 'viewport-btn inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-800 transition';
    });
  }

  function setGenerateLoadingState(loading) {
    const btn = $('btn-generate-again');
    const icon = $('generate-again-icon');
    const spinner = $('generate-again-spinner');
    const text = $('generate-again-text');
    const deployBtn = $('btn-deploy');

    if (btn) btn.disabled = loading;
    if (deployBtn) deployBtn.disabled = loading;
    icon?.classList.toggle('hidden', loading);
    spinner?.classList.toggle('hidden', !loading);
    if (text) text.textContent = loading ? 'Đang sinh lại...' : 'Generate Again';
  }

  function setDeployLoadingState(loading) {
    const btn = $('btn-deploy');
    const icon = $('deploy-icon');
    const spinner = $('deploy-spinner');
    const text = $('deploy-text');
    const genBtn = $('btn-generate-again');

    if (btn) btn.disabled = loading;
    if (genBtn) genBtn.disabled = loading;
    icon?.classList.toggle('hidden', loading);
    spinner?.classList.toggle('hidden', !loading);
    if (text) text.textContent = loading ? 'Đang chuyển...' : 'Deploy';
  }

  function setButtonsDisabled(disabled) {
    const genBtn = $('btn-generate-again');
    const deployBtn = $('btn-deploy');
    if (genBtn) genBtn.disabled = disabled;
    if (deployBtn) deployBtn.disabled = disabled;
  }

  function setLoadingOverlay(visible, title = '', desc = '') {
    const overlay = $('preview-loading-overlay');
    if (!overlay) return;
    if (title && $('preview-loading-title')) $('preview-loading-title').textContent = title;
    if (desc && $('preview-loading-desc')) $('preview-loading-desc').textContent = desc;
    overlay.classList.toggle('hidden', !visible);
  }

  function showEmptyState(visible) {
    const empty = $('preview-empty-state');
    const iframe = $('preview-iframe');
    if (!empty) return;
    empty.classList.toggle('hidden', !visible);
    if (visible && iframe) {
      iframe.classList.add('hidden');
    }
  }

  function showError(message) {
    const banner = $('preview-error-banner');
    const msgEl = $('preview-error-message');
    if (msgEl) msgEl.textContent = message;
    banner?.classList.remove('hidden');
  }

  function hideError() {
    $('preview-error-banner')?.classList.add('hidden');
  }

  function setStatusBadge(type, label) {
    const badge = $('preview-status-badge');
    const dot = $('preview-status-dot');
    const text = $('preview-status-text');
    if (!badge || !dot || !text) return;

    const styles = {
      ready: {
        badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dot: 'bg-emerald-500',
      },
      loading: {
        badge: 'bg-indigo-50 text-indigo-700 border-indigo-200',
        dot: 'bg-indigo-500 animate-ping',
      },
      error: {
        badge: 'bg-rose-50 text-rose-700 border-rose-200',
        dot: 'bg-rose-500',
      },
      idle: {
        badge: 'bg-slate-100 text-slate-600 border-slate-200',
        dot: 'bg-slate-400',
      },
    };

    const cfg = styles[type] || styles.idle;
    badge.className = `inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${cfg.badge}`;
    dot.className = `w-1.5 h-1.5 rounded-full ${cfg.dot}`;
    text.textContent = label;
  }
})();