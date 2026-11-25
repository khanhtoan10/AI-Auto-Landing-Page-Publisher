/**
 * API client dùng chung cho toàn bộ Frontend.
 *
 * - Tự chọn API Base URL phù hợp: cùng origin khi frontend được FastAPI phục vụ,
 *   hoặc http://127.0.0.1:8000 khi mở bằng Live Server / file://.
 * - Tự gắn Authorization: Bearer <token>.
 * - Hỗ trợ JSON và multipart/form-data (upload ảnh).
 * - Chuẩn hoá lỗi trả về từ FastAPI (detail dạng string, object hoặc mảng validation).
 */
(function () {
  "use strict";

  const TOKEN_KEY = "lp_access_token";
  const LEGACY_TOKEN_KEY = "access_token";
  const STORAGE_API_BASE_KEY = "lp_api_base_url";

  function normalizeBaseUrl(value) {
    return String(value || "").trim().replace(/\/+$/, "");
  }

  function resolveApiBaseUrl() {
    // 1. Kiểm tra query parameter: ?api=... hoặc ?backend=... (tiện lợi khi chấm demo hoặc đổi môi trường)
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const queryApi = urlParams.get("api") || urlParams.get("backend");
      if (queryApi) {
        const clean = normalizeBaseUrl(queryApi);
        localStorage.setItem(STORAGE_API_BASE_KEY, clean);
        return clean;
      }
    } catch (_) {}

    // 2. Kiểm tra cấu hình tùy chỉnh đã lưu trong localStorage
    try {
      const stored = normalizeBaseUrl(localStorage.getItem(STORAGE_API_BASE_KEY));
      if (stored) return stored;
    } catch (_) {}

    // 3. Biến toàn cục từ config.js hoặc inline script
    const explicit = normalizeBaseUrl(window.API_BASE_URL || window.__API_BASE_URL__ || window.__DEFAULT_BACKEND_URL__);
    if (explicit && explicit !== "auto") return explicit;

    const { protocol, hostname, port } = window.location;

    // Mở trực tiếp file HTML -> luôn trỏ về backend local.
    if (protocol === "file:") return "http://127.0.0.1:8000";

    // Frontend được FastAPI (port 8000) phục vụ -> dùng đúng origin hiện tại.
    if (port === "8000") return "";

    // Chạy Live Server / Vite / Python http.server ở máy local.
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "http://127.0.0.1:8000";
    }

    // Production: frontend và backend cùng domain (hoặc reverse proxy vercel.json).
    return "";
  }

  const API_BASE_URL = resolveApiBaseUrl();
  window.API_BASE_URL = API_BASE_URL;

  function getToken() {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) return token;

    // Tương thích ngược với token cũ do các trang trước đây lưu dưới key access_token.
    const legacy = localStorage.getItem(LEGACY_TOKEN_KEY);
    if (legacy) {
      localStorage.setItem(TOKEN_KEY, legacy);
      return legacy;
    }
    return null;
  }

  function setToken(token) {
    if (!token) return;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(LEGACY_TOKEN_KEY, token);
  }

  function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  }

  function isFormData(body) {
    return typeof FormData !== "undefined" && body instanceof FormData;
  }

  function buildUrl(endpoint) {
    if (/^https?:\/\//i.test(endpoint)) return endpoint;
    const path = String(endpoint || "").startsWith("/") ? endpoint : `/${endpoint}`;
    return `${API_BASE_URL}${path}`;
  }

  function truncate(value, maxLength = 300) {
    const text = String(value || "").trim();
    return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
  }

  function extractErrorMessage(data, fallback) {
    if (!data) return fallback;

    const detail = data.detail;

    if (typeof detail === "string" && detail.trim()) {
      return truncate(detail);
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (!item || typeof item !== "object") return "";
          const location = Array.isArray(item.loc)
            ? item.loc.filter((part) => part !== "body" && part !== "query").join(".")
            : "";
          const message = item.msg || item.message || "";
          return location ? `${location}: ${message}` : message;
        })
        .filter(Boolean);

      if (messages.length) return truncate(messages.join("; "));
    }

    if (detail && typeof detail === "object") {
      if (detail.error && typeof detail.error.message === "string") {
        return truncate(detail.error.message);
      }
      if (typeof detail.message === "string" && detail.message.trim()) {
        return truncate(detail.message);
      }
    }

    if (data.error && typeof data.error.message === "string") {
      return truncate(data.error.message);
    }

    if (typeof data.message === "string" && data.message.trim()) {
      return truncate(data.message);
    }

    return fallback;
  }

  function redirectToLogin() {
    const path = window.location.pathname;
    if (path.endsWith("login.html") || path.endsWith("/login")) return;
    const prefix = path.includes("/pages/") ? "../" : "";
    window.location.href = `${prefix}login.html`;
  }

  async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    const headers = new Headers(options.headers || {});

    if (options.body != null && !isFormData(options.body) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let response;
    try {
      response = await fetch(buildUrl(endpoint), {
        ...options,
        headers,
      });
    } catch (error) {
      throw new Error(
        "Không thể kết nối tới máy chủ FastAPI. Vui lòng kiểm tra backend đang chạy tại " +
          (API_BASE_URL || window.location.origin) +
          "."
      );
    }

    let data = null;
    if (response.status !== 204) {
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        data = await response.json().catch(() => null);
      } else {
        const text = await response.text().catch(() => "");
        data = text ? { detail: text } : null;
      }
    }

    const isAuthEndpoint =
      endpoint.includes("/auth/login") || endpoint.includes("/auth/register");

    if (response.status === 401 && !isAuthEndpoint) {
      removeToken();
      redirectToLogin();
      throw new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    }

    if (!response.ok) {
      // 503 với header X-GitHub-Error=auth → lỗi GitHub token, không phải JWT
      if (response.status === 503 && response.headers.get("X-GitHub-Error") === "auth") {
        const msg = extractErrorMessage(data, "Token GitHub không hợp lệ hoặc đã hết hạn.");
        throw new Error(msg);
      }
      // 429 → rate limit GitHub
      if (response.status === 429) {
        const retryAfter = response.headers.get("Retry-After");
        const baseMsg = extractErrorMessage(data, "GitHub API đang bị giới hạn tốc độ.");
        const hint = retryAfter ? ` Vui lòng thử lại sau ${retryAfter} giây.` : "";
        throw new Error(baseMsg + hint);
      }
      // 409 → trùng tên repo
      if (response.status === 409) {
        throw new Error(extractErrorMessage(data, "Tên repository đã tồn tại trên GitHub. Vui lòng đổi tên chiến dịch."));
      }
      const fallback =
        response.status >= 500
          ? "Máy chủ gặp lỗi khi xử lý yêu cầu. Vui lòng thử lại sau."
          : `Yêu cầu thất bại (HTTP ${response.status}).`;
      throw new Error(extractErrorMessage(data, fallback));
    }

    return data || {};
  }

  window.API_BASE_URL = API_BASE_URL;
  window.apiRequest = apiRequest;
  window.apiUrl = buildUrl;
  window.getToken = getToken;
  window.setToken = setToken;
  window.removeToken = removeToken;
  window.getApiBaseUrl = function () {
    return API_BASE_URL;
  };
  window.setApiBaseUrl = function (newUrl) {
    if (!newUrl) {
      localStorage.removeItem(STORAGE_API_BASE_KEY);
    } else {
      localStorage.setItem(STORAGE_API_BASE_KEY, normalizeBaseUrl(newUrl));
    }
    window.location.reload();
  };
  window.resetApiBaseUrl = function () {
    localStorage.removeItem(STORAGE_API_BASE_KEY);
    window.location.reload();
  };
})();
