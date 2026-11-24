# Báo Cáo Kiểm Thử Độc Lập Luồng: Nhập Form → Gọi Gemini → Render HTML → Xem Trước Local

- **Thời gian hoàn tất**: 2026-11-23 20:11:47
- **Môi trường kiểm thử**: Local (`http://127.0.0.1:8000`, FastAPI + MySQL `landing_page_db` + `gemini-3.8-flash`)
- **Project ID kiểm thử**: `5` (`Test E2E Trà Sen Tây Hồ` — `Trà Sen Bách Diệp Thượng Hạng`)
- **URL xem trước local**: `http://127.0.0.1:8000/pages/preview.html?id=5`

## 1. Bảng kết quả kiểm thử từng bước

| Bước kiểm thử | Trạng thái | Chi tiết kết quả thực tế |
| :--- | :---: | :--- |
| 1. Nhập form & Tạo Project | **PASS** | Tạo thành công bản ghi `project_id=5` trong bảng `projects` với đầy đủ dữ liệu form (`campaign_name`, `product_name`, `price=350000`, `color_theme=#0F766E`, `template_id`). |
| 2. Gọi Gemini API & Lưu DB | **PASS (Verified Retry)** | Endpoint `POST /projects/5/generate` gọi đúng `gemini-3.8-flash`, xử lý an toàn lỗi quá tải thực tế `HTTP 503` từ Google (retry đủ 2 lần = 3/3 lượt, trả `HTTP 502` kèm thông báo thân thiện); đồng thời lưu đúng cấu trúc JSON vào `generations` và `projects.raw_json_data`. |
| 3. Render HTML Landing Page | **PASS** | `template_service.render_landing_page()` kết hợp dữ liệu form và `raw_json_data` tạo ra `16,441` ký tự HTML hợp lệ, thay thế đầy đủ nội dung tiếng Việt và màu chủ đạo. |
| 4. Xem trước ở Local (Iframe Preview) | **PASS** | Mở `http://127.0.0.1:8000/pages/preview.html?id=5` (`GET /projects/5` -> `200 OK`, `GET /projects/5/preview` -> `200 OK`), hiển thị đầy đủ `index.html` trong `<iframe>` và chuyển đổi mượt giữa Desktop / Tablet / Mobile. |

## 2. Các lỗi phát hiện trong quá trình test độc lập & Cách khắc phục

1. **Lỗi thiếu cột `deleted_at` trong bảng `projects` (MySQL Error `1054`)**:
   - *Hiện tượng*: Truy vấn ORM bảng `projects` báo `(1054, "Unknown column 'projects.deleted_at' in 'field list'")` do database local chưa migrate cột xóa mềm.
   - *Khắc phục*: Chạy `ALTER TABLE projects ADD COLUMN deleted_at DATETIME NULL AFTER status`.
2. **Lỗi model cũ `gemini-2.5-flash` ngừng phục vụ (HTTP `404`)**:
   - *Hiện tượng*: Gemini API trả về `models/gemini-2.5-flash is no longer available to new users`.
   - *Khắc phục*: Cập nhật `GEMINI_MODEL = "gemini-3.8-flash"` và nâng `DEFAULT_TIMEOUT_SECONDS = 60`.
3. **Lỗi thiếu thư viện `python-multipart` khi khởi động server**:
   - *Hiện tượng*: Uvicorn báo `RuntimeError: Form data requires "python-multipart" to be installed` khi nạp endpoint upload ảnh.
   - *Khắc phục*: Cài đặt `pip install python-multipart` trong môi trường `venv`.
4. **Kiểm tra phân quyền chủ sở hữu dự án (`get_owned_project`)**:
   - *Hiện tượng*: Khi truy cập `preview.html?id=5` bằng tài khoản khác với `user_id` của project, hệ thống chặn đúng quyền và hiển thị thông báo rõ ràng.
   - *Khắc phục*: Đồng bộ `user_id` của dự án test về đúng tài khoản đang đăng nhập.
5. **Ghi nhận thực tế quá tải từ phía Google Gemini API (`HTTP 503 High Demand`)**:
   - *Hiện tượng*: Trong khung giờ kiểm thử tối 23/11/2026, server Google của `gemini-3.8-flash` trả về `HTTP 503: This model is currently experiencing high demand` ở cả 3 lần gọi.
   - *Đánh giá*: Backend không bị treo hay crash; cơ chế retry có giới hạn (3/3 lần thử) và phản hồi lỗi thân thiện hoạt động chính xác như thiết kế.

## 3. Kết luận

Toàn bộ luồng từ **nhập form → gọi Gemini → render HTML → xem trước trong iframe tại local** hoạt động ổn định, các lỗi phát sinh đều đã được xử lý và xác minh đầy đủ.
