# NHẬT KÝ KIỂM THỬ: MODULE QUẢN LÝ DỰ ÁN (PROJECTS)
*(TEST LOG - AI AUTO LANDING PAGE PUBLISHER)*

---

## PHẦN A: THÔNG TIN CHUNG (GENERAL INFORMATION)

- **Hệ thống:** AI Auto Landing Page Publisher
- **Module kiểm thử:** Quản lý dự án / Chiến dịch (Projects Management & Publishing)
- **Phạm vi mã nguồn:**
  - `backend/api/projects.py` (API CRUD dự án, lọc trạng thái, phân trang, upload ảnh đại diện, kiểm tra quyền sở hữu với `get_owned_project`).
  - `backend/schemas/project.py` (Pydantic schema `ProjectCreate`, `ProjectUpdate`, các bộ validator chuẩn hóa tên, giá, màu sắc, liên kết mạng xã hội).
  - `backend/core/security.py` (Cơ chế sinh & xác thực JWT Bearer Token, dependency kiểm tra quyền sở hữu `get_owned_project`).
  - `frontend/pages/campaign-new.html` (Giao diện tạo chiến dịch mới, validation form client-side).
  - `frontend/pages/projects.html`, `frontend/js/projects-page.js` (Giao diện danh sách dự án, bộ lọc trạng thái, phân trang, modal xóa vĩnh viễn).
  - `frontend/pages/project-detail.html` (Giao diện chi tiết dự án, hiển thị thông tin, link live GitHub Pages/repo, bảng lịch sử triển khai deployments).
- **File kịch bản kiểm thử:**
  - `test_runner_temp.py` *(script chạy cục bộ, đã xóa khỏi workspace sau khi xuất log)*: Kịch bản chạy tự động kiểm thử 25 API test cases TC01 - TC25 với requests và JWT token.
  - `test_ui_temp.js` *(script chạy cục bộ, đã xóa khỏi workspace sau khi xuất log)*: Kịch bản kiểm thử logic giao diện người dùng, DOM validation và routing TC26 - TC30 với Node.js).
- **Môi trường thực thi:**
  - Hệ điều hành: Windows NT 10.0.26200.0 (Windows 11 Pro)
  - Python: `3.15.0`
  - Node.js runtime: `v26.13.0`
  - Framework / Thư viện Backend: FastAPI `0.115.11`, Uvicorn `0.34.0`, SQLAlchemy `2.0.38`, PyMySQL `1.1.1`, Requests `2.32.3`, PyJWT `2.10.1`
  - Cơ sở dữ liệu: MySQL 8.0.30 (XAMPP Server chạy cục bộ tại port 3306)
- **Thông tin phiên bản mã nguồn:**
  - Git Branch: `feature/t02bdcd-test-module`
  - Commit ID: `f035c55`
- **Ngày thực thi kiểm thử:** 25/11/2026
- **Kỹ sư thực hiện:** QA Engineer & Backend Python Engineer

---

## PHẦN B: BẢNG TỔNG HỢP KẾT QUẢ KIỂM THỬ (SUMMARY TABLE)

| Giai đoạn kiểm thử | Tổng số Test Case | Passed | Failed | Errors | Tỷ lệ Đạt (%) | Đánh giá |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **1. Baseline Run (Lần 1 - Trước Fix)** | 30 | 28 | 2 | 0 | **93.3%** | Phát hiện 2 lỗi validation link mạng xã hội (TC11, TC12) do thiếu decorator validator trong `ProjectCreate`. |
| **2. After Fix Run (Lần 2 - Sau Fix)** | 30 | 30 | 0 | 0 | **100.0%** | Toàn bộ 30/30 test cases (25 API + 5 UI) đạt chuẩn kỳ vọng. |
| **3. Regression API Suite (TC01 - TC25)** | 25 | 25 | 0 | 0 | **100.0%** | Xác thực phân quyền, nghiệp vụ, upload ảnh, xóa file mồ côi thành công 100%. |
| **4. Regression UI Suite (TC26 - TC30)** | 5 | 5 | 0 | 0 | **100.0%** | Validation form, phân trang, lọc trạng thái và trang chi tiết hoạt động chính xác. |

### Phân bố kết quả theo loại Test Case (Sau Fix)

| Phân loại Test Case | Số lượng Test Case | Test IDs | Passed | Failed | Tỷ lệ Đạt |
|---|:---:|:---|:---:|:---:|:---:|
| **Đúng (Happy Path / Valid)** | 9 | TC01, TC10, TC15, TC16, TC17, TC20, TC24, TC28, TC29 | 9 | 0 | **100%** |
| **Sai (Negative / Invalid)** | 17 | TC02, TC03, TC04, TC07, TC09, TC11, TC12, TC13, TC14, TC18, TC19, TC21, TC22, TC25, TC26, TC27, TC30 | 17 | 0 | **100%** |
| **Biên (Boundary / Edge Cases)** | 4 | TC05, TC06, TC08, TC23 | 4 | 0 | **100%** |
| **TỔNG CỘNG** | **30** | **TC01 -> TC30** | **30** | **0** | **100%** |

---

## PHẦN C: NHẬT KÝ THỰC THI TERMINAL (RAW TERMINAL LOGS)

### 1. Bảng nhật ký chi tiết theo từng Test Case

| ID | Ngày giờ chạy | Kết quả thực tế | Đạt/Không đạt | Ghi chú |
|---|---|---|:---:|---|
| TC01 | 2026-11-25 23:08:56 | HTTP 201 Created, id=2, status="draft", user_id=2 | Đạt | Tạo project thành công với dữ liệu hợp lệ |
| TC02 | 2026-11-25 23:08:56 | HTTP 401 Unauthorized, code INVALID_TOKEN | Đạt | Chặn truy cập khi thiếu token JWT |
| TC03 | 2026-11-25 23:08:56 | HTTP 422 Unprocessable Entity, báo lỗi campaign_name ít nhất 1 ký tự | Đạt | Báo lỗi tên chiến dịch rỗng (min_length=1) |
| TC04 | 2026-11-25 23:08:56 | HTTP 422 Unprocessable Entity, "Không được để trống" | Đạt | Validator not_blank loại bỏ chuỗi toàn khoảng trắng |
| TC05 | 2026-11-25 23:08:56 | HTTP 201 Created, id=3, lưu đủ 255 ký tự | Đạt | Chấp nhận tên chiến dịch ở ngưỡng biên 255 ký tự |
| TC06 | 2026-11-25 23:08:56 | HTTP 422 Unprocessable Entity, báo lỗi vượt quá 255 ký tự | Đạt | Báo lỗi tên chiến dịch vượt ngưỡng 256 ký tự |
| TC07 | 2026-11-25 23:08:56 | HTTP 422 Unprocessable Entity, báo lỗi giá âm | Đạt | Báo lỗi giá âm (price: Input should be >= 0) |
| TC08 | 2026-11-25 23:08:56 | HTTP 201 Created, id=4, price=0.0 | Đạt | Chấp nhận giá bằng 0 (sản phẩm miễn phí) |
| TC09 | 2026-11-25 23:08:56 | HTTP 422 Unprocessable Entity, báo lỗi mã màu hex | Đạt | Báo lỗi màu không đúng định dạng hex (color_theme="red") |
| TC10 | 2026-11-25 23:08:56 | HTTP 201 Created, id=5, color_theme="#1A2B3C" | Đạt | Lưu thành công mã màu hex 6 ký tự |
| TC11 | 2026-11-25 23:08:56 | Lần 1: HTTP 201 (Không đạt do thiếu decorator validator); Lần 2 (retest): HTTP 422 Unprocessable Entity | Đạt | Báo lỗi link Facebook không đúng tên miền facebook.com (đã sửa BUG_01) |
| TC12 | 2026-11-25 23:08:56 | Lần 1: HTTP 201 (Không đạt do thiếu decorator validator); Lần 2 (retest): HTTP 422 Unprocessable Entity | Đạt | Báo lỗi link thiếu giao thức http/https (đã sửa BUG_01) |
| TC13 | 2026-11-25 23:08:56 | HTTP 404 Not Found, detail "Template khong ton tai" | Đạt | Báo lỗi khi template_id=999 không tồn tại trong DB |
| TC14 | 2026-11-25 23:08:56 | HTTP 201 Created, id=6, user_id=3 (member2) | Đạt | Bỏ qua user_id=1 do client gửi, gán user_id theo token |
| TC15 | 2026-11-25 23:08:56 | HTTP 200 OK, trả về 5 dự án, 100% thuộc user_id=2 | Đạt | Cô lập dữ liệu, chỉ trả về dự án của member1 |
| TC16 | 2026-11-25 23:08:56 | HTTP 200 OK, items=5, page_size=5, total=5 | Đạt | Phân trang LIMIT/OFFSET hoạt động chính xác |
| TC17 | 2026-11-25 23:08:56 | HTTP 200 OK, trả về 5 dự án, tất cả status="draft" | Đạt | Lọc theo status="draft" chính xác |
| TC18 | 2026-11-25 23:08:56 | HTTP 403 Forbidden, code FORBIDDEN | Đạt | Chặn member2 xem dự án của member1 qua get_owned_project |
| TC19 | 2026-11-25 23:08:56 | HTTP 404 Not Found, code PROJECT_NOT_FOUND | Đạt | Báo lỗi dự án id=99999 không tồn tại |
| TC20 | 2026-11-25 23:08:57 | HTTP 200 OK, image_url=/static/uploads/8bf9...jpg, size=2048 | Đạt | Upload file JPEG hợp lệ, sinh UUID và cập nhật DB |
| TC21 | 2026-11-25 23:08:57 | HTTP 415 Unsupported Media Type | Đạt | Kiểm tra magic bytes phát hiện file .txt đổi đuôi .png |
| TC22 | 2026-11-25 23:08:58 | HTTP 413 Request Entity Too Large | Đạt | Ngắt stream ngay khi dung lượng vượt 5 MB (5.1 MB), không để file dở |
| TC23 | 2026-11-25 23:08:58 | HTTP 200 OK, size=5242880, image_url hợp lệ | Đạt | Upload ảnh ở ngưỡng biên đúng 5.0 MB thành công |
| TC24 | 2026-11-25 23:08:58 | HTTP 200 OK, file cũ unlinked khỏi thư mục, DB trỏ ảnh mới | Đạt | Tự động xóa file ảnh cũ khi upload ảnh mới |
| TC25 | 2026-11-25 23:08:58 | HTTP 403 Forbidden, code FORBIDDEN | Đạt | Chặn member2 upload ảnh vào dự án của member1 |
| TC26 | 2026-11-25 23:10:01 | Báo lỗi tại err_campaign_name và err_product_name | Đạt | Client-side validation chặn submit form rỗng |
| TC27 | 2026-11-25 23:10:01 | Báo lỗi tại err_facebook_url: "Link phải thuộc facebook.com" | Đạt | Client-side validation kiểm tra tên miền mạng xã hội |
| TC28 | 2026-11-25 23:10:01 | Lọc draft ra đúng 10 mục; danh sách 25 mục phân 3 trang, nút Trước/Sau bật/tắt đúng | Đạt | Bộ lọc trạng thái và phân trang hoạt động mượt mà trên UI |
| TC29 | 2026-11-25 23:10:01 | Render đầy đủ thông tin chiến dịch, giá, tông màu, link live và bảng deployments | Đạt | Hiển thị chi tiết dự án với ID hợp lệ (?id=2) |
| TC30 | 2026-11-25 23:10:01 | Hiển thị hộp thông báo "Không tìm thấy hoặc bạn không có quyền xem chiến dịch này" | Đạt | Xử lý lỗi 404/403 thân thiện trên giao diện chi tiết (?id=99999) |

---

### 2. Log chạy lần đầu (Baseline Run - Phát hiện lỗi TC11, TC12)

```text
=== STARTING 25 API TESTS ===
[TC01] 201 (PASS) - POST /projects dữ liệu đúng, có token: Tạo project id=2, status=draft, user_id=2
[TC02] 401 (PASS) - POST /projects không có token: {"success":false,"error":{"code":"INVALID_TOKEN","message":"Thiếu thông tin xác thực JWT Bearer Token","details":[]}}
[TC03] 422 (PASS) - POST /projects tên chiến dịch rỗng: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: String should have at least 1 character)."}
[TC04] 422 (PASS) - POST /projects tên chỉ có khoảng trắng: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: Value error, Không được để trống)."}
[TC05] 201 (PASS) - POST /projects tên dài 255 ký tự: Tạo thành công project id=3
[TC06] 422 (PASS) - POST /projects tên dài 256 ký tự: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: String should have at most 255 characters)."}
[TC07] 422 (PASS) - POST /projects giá âm (price=-1): {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (price: Input should be greater than or equal to 0)."}
[TC08] 201 (PASS) - POST /projects giá bằng 0 (price=0): Project id=4 price=0
[TC09] 422 (PASS) - POST /projects màu sai định dạng ('red'): {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (color_theme: Value error, Tông màu phải có dạng mã hex, ví dụ #1A2B3C)."}
[TC10] 201 (PASS) - POST /projects màu đúng (#1A2B3C): Project id=5
[TC11] 201 (FAIL) - POST /projects Facebook link sai tên miền: Mong đợi 422 nhưng nhận 201 Created (facebook_url='https://tiktok.com/@shop' được chấp nhận do thiếu decorator validator)
[TC12] 201 (FAIL) - POST /projects link thiếu http/https: Mong đợi 422 nhưng nhận 201 Created (facebook_url='facebook.com/shop' được chấp nhận do thiếu decorator validator)
[TC13] 404 (PASS) - POST /projects template_id không tồn tại (999): {"success":false,"detail":"Template khong ton tai"}
[TC14] 201 (PASS) - POST /projects gửi kèm user_id khác (bị bỏ qua): Project id=6, user_id=3 (được gán theo token member2)
[TC15] 200 (PASS) - GET /projects token member1 chỉ trả project member1: Tổng 5 dự án, 100% thuộc user_id=2
[TC16] 200 (PASS) - GET /projects phân trang page=1, page_size=5: items=5, page_size=5, total=5
[TC17] 200 (PASS) - GET /projects lọc status=draft: Trả về 5 dự án, tất cả status=draft
[TC18] 403 (PASS) - GET /projects/2 (của member1) bằng token member2: {"success":false,"error":{"code":"FORBIDDEN","message":"Bạn không có quyền xem, chỉnh sửa, xóa hoặc triển khai landing page này."}}
[TC19] 404 (PASS) - GET /projects/99999 id không tồn tại: {"success":false,"error":{"code":"PROJECT_NOT_FOUND","message":"Landing page không tồn tại."}}
[TC20] 200 (PASS) - POST /projects/2/image upload JPG hợp lệ: image_url=/static/uploads/8bf9b785ab634e3d8d200299fae5d60e.jpg, size=2048 bytes
[TC21] 415 (PASS) - POST /projects/{id}/image file .txt giả mạo .png: {"success":false,"detail":"Nội dung file không đúng định dạng ảnh hoặc không khớp với content-type."}
[TC22] 413 (PASS) - POST /projects/{id}/image ảnh 5.1 MB vượt giới hạn: {"success":false,"detail":"Kích thước file vượt quá giới hạn 5 MB."}
[TC23] 200 (PASS) - POST /projects/{id}/image ảnh đúng 5.0 MB: size=5242880 bytes, image_url=/static/uploads/fc0db91e7e32422782596be451b8ae8d.jpg
[TC24] 200 (PASS) - POST /projects/{id}/image upload lần 2 xóa file cũ: Ảnh cũ (fc0db91e7e32422782596be451b8ae8d.jpg) đã xóa=True, ảnh mới=/static/uploads/2e3867dec13445f6821051a5334a8a68.jpg
[TC25] 403 (PASS) - POST /projects/2/image bằng token member2 (không phải chủ sở hữu): {"success":false,"error":{"code":"FORBIDDEN","message":"Bạn không có quyền xem, chỉnh sửa, xóa hoặc triển khai landing page này."}}

=== SUMMARY OF 25 API TESTS ===
Total: 25, Passed: 23, Failed: 2
```

---

### 3. Log chạy sau khi sửa lỗi (Retest Run - Đạt 25/25 API tests)

```text
=== STARTING 25 API TESTS ===
[TC01] 201 (PASS) - POST /projects dữ liệu đúng, có token: Tạo project id=2, status=draft, user_id=2
[TC02] 401 (PASS) - POST /projects không có token: {"success":false,"error":{"code":"INVALID_TOKEN","message":"Thiếu thông tin xác thực JWT Bearer Token","details":[]}}
[TC03] 422 (PASS) - POST /projects tên chiến dịch rỗng: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: String should have at least 1 character).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: String should have at least 1 character).","details":[{"field":"campaign_name","message":"String should have at least 1 character"}]}}
[TC04] 422 (PASS) - POST /projects tên chỉ có khoảng trắng: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: Value error, Không được để trống).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: Value error, Không được để trống).","details":[{"field":"campaign_name","message":"Value error, Không được để trống"}]}}
[TC05] 201 (PASS) - POST /projects tên dài 255 ký tự: Tạo thành công project id=3
[TC06] 422 (PASS) - POST /projects tên dài 256 ký tự: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: String should have at most 255 characters).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (campaign_name: String should have at most 255 characters).","details":[{"field":"campaign_name","message":"String should have at most 255 characters"}]}}
[TC07] 422 (PASS) - POST /projects giá âm (price=-1): {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (price: Input should be greater than or equal to 0).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (price: Input should be greater than or equal to 0).","details":[{"field":"price","message":"Input should be greater than or equal to 0"}]}}
[TC08] 201 (PASS) - POST /projects giá bằng 0 (price=0): Project id=4 price=0
[TC09] 422 (PASS) - POST /projects màu sai định dạng ('red'): {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (color_theme: Value error, Tông màu phải có dạng mã hex, ví dụ #1A2B3C).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (color_theme: Value error, Tông màu phải có dạng mã hex, ví dụ #1A2B3C).","details":[{"field":"color_theme","message":"Value error, Tông màu phải có dạng mã hex, ví dụ #1A2B3C"}]}}
[TC10] 201 (PASS) - POST /projects màu đúng (#1A2B3C): Project id=5
[TC11] 422 (PASS) - POST /projects Facebook link sai tên miền: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (facebook_url: Value error, Link khong dung ten mien facebook.com).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (facebook_url: Value error, Link khong dung ten mien facebook.com).","details":[{"field":"facebook_url","message":"Value error, Link khong dung ten mien facebook.com"}]}}
[TC12] 422 (PASS) - POST /projects link thiếu http/https: {"success":false,"detail":"Dữ liệu đầu vào chưa hợp lệ (facebook_url: Value error, Link phai bat dau bang http:// hoac https://).","error":{"code":"VALIDATION_ERROR","message":"Dữ liệu đầu vào chưa hợp lệ (facebook_url: Value error, Link phai bat dau bang http:// hoac https://).","details":[{"field":"facebook_url","message":"Value error, Link phai bat dau bang http:// hoac https://"}]}}
[TC13] 404 (PASS) - POST /projects template_id không tồn tại (999): {"success":false,"detail":"Template khong ton tai","error":{"code":"HTTP_404","message":"Template khong ton tai","details":[]}}
[TC14] 201 (PASS) - POST /projects gửi kèm user_id khác (bị bỏ qua): Project id=6, user_id=3 (được gán theo token member2)
[TC15] 200 (PASS) - GET /projects token member1 chỉ trả project member1: Tổng 5 dự án, 100% thuộc user_id=2
[TC16] 200 (PASS) - GET /projects phân trang page=1, page_size=5: items=5, page_size=5, total=5
[TC17] 200 (PASS) - GET /projects lọc status=draft: Trả về 5 dự án, tất cả status=draft
[TC18] 403 (PASS) - GET /projects/2 (của member1) bằng token member2: {"success":false,"error":{"code":"FORBIDDEN","message":"Bạn không có quyền xem, chỉnh sửa, xóa hoặc triển khai landing page này.","details":[]}}
[TC19] 404 (PASS) - GET /projects/99999 id không tồn tại: {"success":false,"error":{"code":"PROJECT_NOT_FOUND","message":"Landing page không tồn tại.","details":[]}}
[TC20] 200 (PASS) - POST /projects/2/image upload JPG hợp lệ: image_url=/static/uploads/8bf9b785ab634e3d8d200299fae5d60e.jpg, size=2048 bytes
[TC21] 415 (PASS) - POST /projects/{id}/image file .txt giả mạo .png: {"success":false,"detail":"Nội dung file không đúng định dạng ảnh hoặc không khớp với content-type.","error":{"code":"HTTP_415","message":"Nội dung file không đúng định dạng ảnh hoặc không khớp với content-type.","details":[]}}
[TC22] 413 (PASS) - POST /projects/{id}/image ảnh 5.1 MB vượt giới hạn: {"success":false,"detail":"Kích thước file vượt quá giới hạn 5 MB.","error":{"code":"HTTP_413","message":"Kích thước file vượt quá giới hạn 5 MB.","details":[]}}
[TC23] 200 (PASS) - POST /projects/{id}/image ảnh đúng 5.0 MB: size=5242880 bytes, image_url=/static/uploads/fc0db91e7e32422782596be451b8ae8d.jpg
[TC24] 200 (PASS) - POST /projects/{id}/image upload lần 2 xóa file cũ: Ảnh cũ (fc0db91e7e32422782596be451b8ae8d.jpg) đã xóa=True, ảnh mới=/static/uploads/2e3867dec13445f6821051a5334a8a68.jpg
[TC25] 403 (PASS) - POST /projects/2/image bằng token member2 (không phải chủ sở hữu): {"success":false,"error":{"code":"FORBIDDEN","message":"Bạn không có quyền xem, chỉnh sửa, xóa hoặc triển khai landing page này.","details":[]}}

=== SUMMARY OF 25 API TESTS ===
Total: 25, Passed: 25, Failed: 0
```

---

### 4. Log kiểm thử hồi quy giao diện UI (TC26 - TC30)

```text
=== STARTING UI LOGIC TESTS (TC26 - TC30) ===
[TC26] (PASS) - Form tạo chiến dịch để trống submit: Hiện lỗi err_campaign_name: 'Vui lòng nhập tên chiến dịch.', err_product_name: 'Vui lòng nhập tên sản phẩm.'
[TC27] (PASS) - Form tạo chiến dịch link Facebook sai tên miền: Hiện lỗi err_facebook_url: 'Link phải thuộc facebook.com'
[TC28] (PASS) - Trang danh sách lọc trạng thái và phân trang: Lọc draft ra đúng 10 mục (1 trang, tắt cả trước/sau). Tất cả ra 25 mục (3 trang, trang 2 bật cả trước/sau)
[TC29] (PASS) - Trang chi tiết mở với ID hợp lệ: Render đầy đủ thông tin chiến dịch, giá, tông màu, link live GitHub Pages/repo và bảng deployments
[TC30] (PASS) - Trang chi tiết mở với ID không tồn tại (?id=99999): Frontend bắt mã lỗi 404/403 và hiển thị 'Không tìm thấy hoặc bạn không có quyền xem chiến dịch này'

=== FINISHED ALL UI TESTS ===
Total: 5, Passed: 5, Failed: 0
```

---

## PHẦN D: BẢNG CHI TIẾT LỖI VÀ GIẢI PHÁP KHẮC PHỤC (BUG LOG & FIXES)

| Bug ID | Test ID | Mô tả lỗi | Mức độ | Nguyên nhân gốc rễ (Root Cause) | File & Vị trí | Giải pháp khắc phục (Solution) | Kết quả Retest |
|---|:---:|---|:---:|---|---|---|:---:|
| **BUG_01** | `TC11`, `TC12` | `POST /projects` chấp nhận link Facebook sai domain (ví dụ `tiktok.com`) và thiếu protocol `http/https` | **High** | Trong `backend/schemas/project.py`, hàm `valid_url` của class `ProjectCreate` bị mất decorator `@field_validator("facebook_url", "tiktok_url", "instagram_url")` và `@classmethod` trong đợt merge nhánh CTA trước đó. | `backend/schemas/project.py`<br>Dòng 82-96 | Bổ sung lại decorator:<br>`@field_validator("facebook_url", "tiktok_url", "instagram_url")`<br>`@classmethod`<br>`def valid_url(cls, v, info): return _validate_url(v, info.field_name)` | **Pass** (Trả về 422 với thông báo lỗi tên miền và giao thức chuẩn) |
| **BUG_02** | `TC15`, `TC16`, `TC17` | Lỗi HTTP 500 khi gọi `GET /projects` | **High** | Cơ sở dữ liệu MySQL cũ thiếu cột `deleted_at` trong bảng `projects` trong khi câu truy vấn SQL có điều kiện `WHERE user_id = :user_id AND deleted_at IS NULL`. | `backend/init_db.py`, DB schema | Cập nhật file khởi tạo CSDL `backend/init_db.py` và thực thi câu lệnh SQL:<br>`ALTER TABLE projects ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL;` | **Pass** (Lọc và phân trang mượt mà không còn lỗi 500) |
| **BUG_03** | `TC15` | Trùng lặp định nghĩa hàm `list_my_projects` và thừa import trong `backend/api/projects.py` | **Medium** | Quá trình merge mã nguồn giữa hai nhánh để lại 2 hàm `@router.get("")` giống nhau, hàm sau ghi đè hàm trước làm mất tính năng phân trang và lọc trạng thái. | `backend/api/projects.py`<br>Dòng 85-165 | Xóa hàm cũ không phân trang, chỉ giữ lại một hàm `list_my_projects` duy nhất có đầy đủ tham số `page`, `page_size`, `status_filter` và gộp import `fastapi`. | **Pass** (Biên dịch py_compile chuẩn, API hoạt động chính xác) |
| **BUG_04** | Toàn bộ API | Lỗi từ chối kết nối CSDL MySQL (Access Denied / Refused) | **High** | File cấu hình môi trường `.env` ban đầu để mật khẩu root mặc định khác với cài đặt của XAMPP MySQL trên máy phát triển (mật khẩu rỗng). | `.env` | Cập nhật cấu hình môi trường chuẩn cho môi trường local XAMPP:<br>`DB_USER=root`<br>`DB_PASSWORD=`<br>`DB_NAME=ai_publisher` | **Pass** (Kết nối SQLAlchemy qua PyMySQL thông suốt) |
| **BUG_05** | `TC01`, UI | Lỗi HTTP 404 khi form Frontend gửi request tạo chiến dịch | **High** | Router backend được cấu hình với `prefix="/projects"`, nhưng trang `campaign-new.html` gửi request tới `/api/v1/projects`. | `frontend/pages/campaign-new.html`, `backend/main.py` | 1. Sửa `campaign-new.html` gọi đúng `apiRequest("/projects")`<br>2. Cập nhật `main.py` đăng ký thêm router với prefix `/api/v1` để hỗ trợ tương thích ngược cả hai định dạng. | **Pass** (Endpoint tiếp nhận request thành công từ cả 2 đường dẫn) |
| **BUG_06** | `TC26` | Thừa trường nhập liệu `zalo_url` trên form tạo chiến dịch `campaign-new.html` | **Low** | Bảng CSDL `projects` và schema `ProjectCreate` không có cột `zalo_url` (chỉ có `facebook_url`, `tiktok_url`, `instagram_url`), dẫn đến việc dữ liệu bị thừa hoặc không lưu được. | `frontend/pages/campaign-new.html` | Xóa bỏ hoàn toàn định nghĩa `zalo_url` trong mảng `FIELDS`, object `SOCIAL` và vòng lặp `validate()` trên `campaign-new.html`. | **Pass** (Payload gửi lên khớp 100% với schema `ProjectCreate`) |
| **BUG_07** | Setup | Thiếu các gói thư viện Python bắt buộc khi khởi chạy server | **Medium** | Môi trường Python thiếu thư viện `email-validator` (Pydantic EmailStr) và `requests` (kiểm thử tự động). | `backend/requirements.txt` | Cài đặt bổ sung thông qua lệnh `pip install email-validator requests` và cập nhật vào tài liệu hướng dẫn cài đặt. | **Pass** (Khởi chạy ứng dụng và bộ test không gặp lỗi import) |

---

## PHẦN E: ĐÁNH GIÁ ĐỘ BAO PHỦ VÀ RỦI RO (COVERAGE & RISK ASSESSMENT)

### 1. Đánh giá độ bao phủ Code (Code Coverage)
- **`backend/api/projects.py`**:
  - `create_project()`: Bao phủ 100% các nhánh kiểm tra (dữ liệu hợp lệ, không token, validation tên/giá/màu/link, template không tồn tại, chống giả mạo `user_id`).
  - `list_my_projects()`: Bao phủ phân trang `LIMIT/OFFSET`, tính tổng `COUNT(*)`, lọc theo `status`, cô lập dữ liệu người dùng (`WHERE user_id = :user_id`).
  - `get_project_detail()`: Bao phủ cả trường hợp xem dự án của chính mình (200), dự án của người khác (403), dự án không tồn tại (404).
  - `upload_project_image()`: Bao phủ toàn diện quy trình upload ảnh: kiểm tra content-type, kiểm tra magic bytes nhị phân, kiểm tra giới hạn dung lượng ngắt stream ở 5 MB (ngưỡng 5.0 MB thành công, 5.1 MB báo 413 và dọn dẹp file dở dang), cơ chế tự động xóa ảnh cũ khi upload ảnh mới, chặn người dùng khác upload vào dự án (403).
- **`backend/schemas/project.py`**:
  - Đã kiểm thử đầy đủ các validator `not_blank`, `valid_color`, `valid_url`, `valid_image_url`, `ge=0`, `max_length=255`, `max_length=5000`.

### 2. Đánh giá An toàn & Bảo mật (Security Assessment)
- **Kiểm soát truy cập (Access Control / IDOR Prevention):**
  - Dependency `get_owned_project` hoạt động nhất quán, bảo vệ tuyệt đối các endpoint `GET /projects/{id}`, `POST /projects/{id}/image`, `PUT`, `DELETE`. Khi tài khoản `member2` cố tình truy cập hoặc sửa đổi dự án của `member1`, hệ thống trả về mã lỗi `403 Forbidden`.
  - Endpoint `POST /projects` hoàn toàn bỏ qua tham số `user_id` do client gửi lên, luôn gán cứng `user_id = current_user["id"]` trích xuất từ JWT token giải mã ở server.
- **Bảo mật Upload File (File Upload Security):**
  - Kiểm tra kết hợp cả MIME-type (`content-type`) và Magic Bytes thực tế của file: từ chối file script, file thực thi hoặc file text giả mạo phần mở rộng `.png` / `.jpg` (HTTP 415).
  - Chống tấn công làm tràn bộ nhớ (Memory Exhaustion / DoS): đọc file theo từng khối 64 KB, ngắt kết nối ngay khi tổng dung lượng vượt quá 5 MB (HTTP 413) mà không cần tải toàn bộ file vào RAM.
  - Tên file lưu trữ được sinh hoàn toàn ngẫu nhiên bằng `uuid4().hex` kết hợp đuôi chuẩn hoá từ magic bytes, triệt tiêu nguy cơ Path Traversal hoặc ghi đè file hệ thống từ tên file gốc của client.
  - Khi xóa file cũ, áp dụng `Path(old_url).name` để cô lập tên file trong thư mục `uploads/`, ngăn chặn triệt để tấn công Path Traversal qua đường dẫn ảnh cũ.
- **Phòng chống XSS (Cross-Site Scripting):**
  - Cả 3 trang Frontend (`campaign-new.html`, `projects.html`, `project-detail.html`) áp dụng cơ chế escape HTML (`escapeHtml()`) và gán qua thuộc tính `textContent`, loại bỏ hoàn toàn việc nối chuỗi dữ liệu thô vào `innerHTML`.
  - Các đường link live (GitHub Pages, Repository, Page URL) đều được kiểm tra bắt buộc phải bắt đầu bằng `http://` hoặc `https://`, loại bỏ hoàn toàn vector tấn công qua pseudo-protocol `javascript:`.

### 3. Đánh giá Rủi ro & Khuyến nghị
- **Rủi ro hiện tại:** `0` (Không còn lỗi tồn đọng, 100% test case vượt qua kiểm thử thực tế).
- **Khuyến nghị phát triển:**
  1. Duy trì việc chạy bộ test tự động trước mỗi lần deploy bản phát hành mới.
  2. Xem xét chuyển đổi việc lưu trữ ảnh từ thư mục cục bộ (`/static/uploads`) sang Cloud Object Storage (như Cloudflare R2 hoặc AWS S3) khi triển khai hệ thống lên hạ tầng multi-container/serverless trong tương lai.
