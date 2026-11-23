/**
 * Shared App Shell & Global Toast System - Nhóm 6
 * Giữ nguyên bố cục Sidebar tối (w-72) & Top Header chuẩn của dự án
 */

const isInPagesDir = window.location.pathname.includes('/pages/');
const ROOT_PREFIX = isInPagesDir ? '../' : '';
const PAGES_PREFIX = isInPagesDir ? '' : 'pages/';

const MENU_ITEMS = [
  {
    href: `${ROOT_PREFIX}index.html`,
    file: 'index.html',
    icon: 'fa-chart-pie',
    label: 'Tổng quan',
    title: 'Bảng điều khiển',
    breadcrumb: 'Tổng quan Workspace',
  },
  {
    href: `${PAGES_PREFIX}create.html`,
    file: 'create.html',
    icon: 'fa-wand-magic-sparkles',
    label: 'Tạo Landing Page AI',
    badge: 'AI Pro',
    title: 'Tạo Landing Page AI Mới',
    breadcrumb: 'Tạo Landing Page AI',
  },
  {
    href: `${PAGES_PREFIX}projects.html`,
    file: 'projects.html',
    icon: 'fa-folder-open',
    label: 'Dự án của tôi',
    title: 'Danh sách dự án của tôi',
    breadcrumb: 'Dự án của tôi',
  },
  {
    href: `${PAGES_PREFIX}templates.html`,
    file: 'templates.html',
    icon: 'fa-layer-group',
    label: 'Kho giao diện mẫu',
    title: 'Kho giao diện mẫu',
    breadcrumb: 'Kho giao diện mẫu',
  },
  {
    href: `${PAGES_PREFIX}deployments.html`,
    file: 'deployments.html',
    icon: 'fa-cloud-arrow-up',
    label: 'Lịch sử xuất bản',
    title: 'Lịch sử xuất bản & Triển khai',
    breadcrumb: 'Lịch sử xuất bản',
  },
];

// ==========================================
// 1. HỆ THỐNG TOAST THÔNG BÁO DÙNG CHUNG
// ==========================================
window.showToast = function (message, type = 'info', title = '') {
  let container = document.getElementById('global-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'global-toast-container';
    container.className = 'fixed bottom-5 right-5 z-[100] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0';
    document.body.appendChild(container);
  }

  const styles = {
    success: { bg: 'bg-white border-emerald-200', iconBg: 'bg-emerald-100 text-emerald-600', icon: 'fa-circle-check', defaultTitle: 'Thành công' },
    error:   { bg: 'bg-white border-rose-200',    iconBg: 'bg-rose-100 text-rose-600',       icon: 'fa-circle-xmark', defaultTitle: 'Đã xảy ra lỗi' },
    warning: { bg: 'bg-white border-amber-200',   iconBg: 'bg-amber-100 text-amber-600',     icon: 'fa-triangle-exclamation', defaultTitle: 'Cảnh báo' },
    info:    { bg: 'bg-white border-indigo-200',  iconBg: 'bg-indigo-100 text-indigo-600',   icon: 'fa-circle-info', defaultTitle: 'Thông báo' },
  };

  const cfg = styles[type] || styles.info;
  const toastEl = document.createElement('div');
  toastEl.className = `pointer-events-auto flex items-start gap-3 p-3.5 rounded-2xl border shadow-xl ${cfg.bg} transition-all duration-300 translate-y-2 opacity-0`;
  toastEl.innerHTML = `
    <div class="w-8 h-8 rounded-xl ${cfg.iconBg} flex items-center justify-center shrink-0 mt-0.5">
      <i class="fa-solid ${cfg.icon} text-sm"></i>
    </div>
    <div class="flex-1 min-w-0">
      <p class="text-xs font-bold text-slate-900">${title || cfg.defaultTitle}</p>
      <p class="text-xs text-slate-600 mt-0.5 leading-relaxed">${message}</p>
    </div>
    <button class="text-slate-400 hover:text-slate-600 p-1" onclick="this.parentElement.remove()">
      <i class="fa-solid fa-xmark text-xs"></i>
    </button>
  `;

  container.appendChild(toastEl);
  requestAnimationFrame(() => toastEl.classList.remove('translate-y-2', 'opacity-0'));

  setTimeout(() => {
    toastEl.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toastEl.remove(), 300);
  }, 3800);
};

// ==========================================
// 2. RENDER SIDEBAR ĐIỀU HƯỚNG (BỐ CỤC GỐC)
// ==========================================
function renderSidebar() {
  const sidebarEl = document.getElementById('app-sidebar');
  if (!sidebarEl) return;

  sidebarEl.className =
    'fixed lg:static inset-y-0 left-0 z-50 w-72 h-full transform -translate-x-full lg:translate-x-0 transition-transform duration-300 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col justify-between select-none';

  const currentFile = window.location.pathname.split('/').pop() || 'index.html';

  const navItemsHtml = MENU_ITEMS.map((item) => {
    const isActive =
      currentFile === item.file ||
      ((currentFile === 'edit-project.html' || currentFile === 'version-history.html') &&
        item.file === 'projects.html');
    if (isActive) {
      return `
        <a href="${item.href}" class="flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-semibold bg-indigo-600 text-white shadow-md shadow-indigo-600/30 transition group">
          <div class="flex items-center gap-3">
            <i class="fa-solid ${item.icon} w-5 text-center text-base text-white"></i>
            <span>${item.label}</span>
          </div>
          ${item.badge ? `<span class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/20 text-white">${item.badge}</span>` : ''}
        </a>
      `;
    }
    return `
      <a href="${item.href}" class="flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition group">
        <div class="flex items-center gap-3">
          <i class="fa-solid ${item.icon} w-5 text-center text-base text-slate-400 group-hover:text-indigo-400"></i>
          <span>${item.label}</span>
        </div>
        ${item.badge ? `<span class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">${item.badge}</span>` : ''}
      </a>
    `;
  }).join('');

  sidebarEl.innerHTML = `
    <!-- Brand Header -->
    <div class="p-5 flex items-center justify-between border-b border-slate-800/80">
      <a href="${ROOT_PREFIX}index.html" class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">
          <i class="fa-solid fa-sparkles text-lg"></i>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="font-extrabold text-white text-base tracking-tight">AI Publisher</span>
            <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">Nhóm 6</span>
          </div>
          <p class="text-[11px] text-slate-400 font-medium">Landing Page Generator</p>
        </div>
      </a>
      <button id="sidebar-close-btn" class="lg:hidden text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800 transition">
        <i class="fa-solid fa-xmark text-lg"></i>
      </button>
    </div>

    <!-- Navigation Links -->
    <div class="flex-1 overflow-y-auto px-3 py-5 space-y-1.5 custom-scrollbar">
      <div class="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Menu Quản trị</div>
      ${navItemsHtml}

      <div class="pt-6 px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Hệ thống</div>
      <a href="https://github.com" target="_blank" class="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <i class="fa-brands fa-github w-5 text-center text-base"></i>
        <span>Kho mã nguồn</span>
      </a>
      <a href="http://127.0.0.1:8000/docs" target="_blank" class="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <i class="fa-solid fa-code w-5 text-center text-base text-emerald-400"></i>
        <span>Swagger FastAPI Docs</span>
      </a>
    </div>

    <!-- FastAPI Backend Status Footer (Đã xóa đoạn Sprint 2 theo yêu cầu) -->
    <div class="p-4 border-t border-slate-800/80 bg-slate-900/80">
      <div class="bg-slate-950/60 border border-slate-800 rounded-xl p-3 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <span class="relative flex h-2.5 w-2.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span class="text-xs font-medium text-slate-300">FastAPI Backend</span>
        </div>
        <span class="text-[11px] font-mono text-emerald-400 font-semibold">Active:8000</span>
      </div>
    </div>
  `;
}

// ==========================================
// 3. RENDER TOP HEADER (BỐ CỤC GỐC)
// ==========================================
function renderHeader(user) {
  const headerEl = document.getElementById('app-header');
  if (!headerEl) return;
  const welcomeNameEl = document.getElementById('welcome-user-name');
    if (welcomeNameEl && user?.full_name) {
    welcomeNameEl.textContent = user.full_name;
    }

  const currentFile = window.location.pathname.split('/').pop() || 'index.html';
  const activeMenu =
    MENU_ITEMS.find((m) => m.file === currentFile) ||
    (currentFile === 'edit-project.html'
      ? { title: 'Chỉnh sửa Landing Page', breadcrumb: 'Chỉnh sửa Landing Page' }
      : currentFile === 'version-history.html'
        ? { title: 'Lịch sử phiên bản', breadcrumb: 'Lịch sử phiên bản' }
        : MENU_ITEMS[0]);

  const displayName = user?.full_name || 'Thành Viên Nhóm 6';
  const displayEmail = user?.email || 'team6@landingai.vn';
  const initials = displayName
    .split(' ')
    .map((w) => w[0])
    .slice(-2)
    .join('')
    .toUpperCase();

  headerEl.innerHTML = `
    <header class="h-16 bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      <!-- Breadcrumb & Mobile Toggle -->
      <div class="flex items-center gap-3 sm:gap-4">
        <button id="sidebar-toggle-btn" class="lg:hidden w-10 h-10 rounded-xl border border-slate-200 bg-white text-slate-600 hover:text-indigo-600 flex items-center justify-center transition shadow-sm">
          <i class="fa-solid fa-bars-staggered"></i>
        </button>
        <div>
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <a href="${ROOT_PREFIX}index.html" class="hover:text-indigo-600 transition">Bảng điều khiển</a>
            <span>/</span>
            <span class="text-slate-600 font-medium">${activeMenu.breadcrumb}</span>
          </div>
          <h1 class="text-base sm:text-lg font-bold text-slate-900 leading-tight">${activeMenu.title}</h1>
        </div>
      </div>

      <!-- Right Header Items -->
      <div class="flex items-center gap-3 sm:gap-4">
        <div class="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-medium">
          <i class="fa-solid fa-bolt text-indigo-500"></i>
          <span>Gemini Pro &amp; Claude 3.5 Engine</span>
        </div>

        <button onclick="window.showToast('Hệ thống đang hoạt động bình thường', 'info')" class="w-9 h-9 rounded-xl border border-slate-200 text-slate-600 hover:text-indigo-600 hover:border-indigo-200 flex items-center justify-center relative transition bg-white shadow-sm" title="Thông báo">
          <i class="fa-regular fa-bell"></i>
        </button>

        <!-- User Info -->
        <div class="flex items-center gap-2.5 p-1 sm:p-1.5 rounded-xl border border-slate-200 bg-white shadow-sm">
          <div id="user-avatar-initials" class="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center border border-indigo-200">
            ${initials || 'N6'}
          </div>
          <div class="text-left hidden md:block pr-1">
            <div id="user-full-name" class="text-xs font-bold text-slate-800 leading-tight">${displayName}</div>
            <div id="user-email" class="text-[10px] text-slate-500 font-medium">${displayEmail}</div>
          </div>
        </div>

        <!-- Nút Đăng xuất -->
        <button id="logout-btn" class="px-3 py-2 rounded-xl bg-rose-50 hover:bg-rose-600 text-rose-600 hover:text-white border border-rose-200 text-xs font-bold transition flex items-center gap-1.5">
          <i class="fa-solid fa-right-from-bracket"></i>
          <span class="hidden sm:inline">Đăng xuất</span>
        </button>
      </div>
    </header>
  `;
}

// ==========================================
// 4. GẮN SỰ KIỆN & XÁC THỰC NGƯỜI DÙNG
// ==========================================
function bindShellEvents() {
  const sidebar = document.getElementById('app-sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  document.getElementById('sidebar-toggle-btn')?.addEventListener('click', () => {
    sidebar?.classList.remove('-translate-x-full');
    overlay?.classList.remove('hidden');
  });

  const closeMenu = () => {
    sidebar?.classList.add('-translate-x-full');
    overlay?.classList.add('hidden');
  };

  document.getElementById('sidebar-close-btn')?.addEventListener('click', closeMenu);
  overlay?.addEventListener('click', closeMenu);

  document.getElementById('logout-btn')?.addEventListener('click', () => {
    window.showToast('Đang đăng xuất...', 'info', 'Thông báo');
    setTimeout(() => {
      if (typeof handleLogout === 'function') {
        handleLogout();
      } else {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_info');
        window.location.href = `${ROOT_PREFIX}login.html`;
      }
    }, 500);
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  renderSidebar();
  renderHeader(null);
  bindShellEvents();

  if (typeof requireAuth === 'function') {
    const user = await requireAuth();
    if (user) {
      renderHeader(user);
      bindShellEvents();
    }
  }
});