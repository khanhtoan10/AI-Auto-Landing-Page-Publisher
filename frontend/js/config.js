/**
 * Cấu hình hệ thống Frontend kết nối Backend Demo
 *
 * - Mặc định khi chạy local (127.0.0.1 / localhost): tự động trỏ về http://127.0.0.1:8000
 * - Khi deploy lên Vercel:
 *   1. Trỏ trực tiếp tới backend demo qua __DEFAULT_BACKEND_URL__ bên dưới
 *   2. Hoặc mở web với query param: ?api=https://your-backend.com (tự lưu vào trình duyệt)
 *   3. Hoặc bấm nút "Cấu hình" tại thẻ Trạng thái kết nối ở trang Dashboard
 */
window.__DEFAULT_BACKEND_URL__ = "https://ai-landing-page-backend-demo.onrender.com";
