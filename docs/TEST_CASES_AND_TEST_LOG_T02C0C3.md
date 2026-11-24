# BÁO CÁO KIỂM THỬ: TEST CASE VÀ TEST LOG MODULE DEPLOY LANDING PAGE
**Học viện Công nghệ Bưu chính Viễn thông - Thực tập doanh nghiệp**  
**Dự án:** AI Auto Landing Page Publisher (Nhóm 6 - Thiết kế và quản lý landing page)  
**Mã Task:** `T02C0C3` | **Tên Task:** [Kiểm thử] Test case và test log module của mình  
**Sinh viên thực hiện:** Đinh Nguyễn Khánh Toàn (Mã SV: **B25DTCN210**)  
**Sprint:** Sprint 3 (24/11 - 30/11) | **Hạn nộp:** 25/11/2026  

---

## I. TỔNG QUAN PHẠM VI KIỂM THỬ (SCOPE OF TESTING)

Module được phân công thực hiện và kiểm thử bao gồm toàn bộ luồng **Triển khai Landing Page & Đồng bộ trạng thái GitHub Pages (Deploy & GitHub Pages Module)**:

1. **`backend/services/github_service.py`**:
   - `_resolve_token`: Phân giải GitHub Personal Access Token (từ tham số hoặc biến môi trường).
   - `_get_headers`: Sinh request headers chuẩn GitHub REST API (v2022-11-28, Bearer Auth).
   - `create_github_repo`: Khởi tạo GitHub repository mới cho chiến dịch.
   - `upload_file_to_repo`: Đẩy 1 file (dạng text HTML hoặc nhị phân base64) lên repo, hỗ trợ ghi đè tự động qua SHA.
   - `push_landing_page_assets`: Đẩy file `index.html` và tập hợp hình ảnh assets.
   - `enable_github_pages`: Kích hoạt tính năng GitHub Pages trên nhánh `main`, thư mục root `/`.
   - `get_github_pages_build_status`: Truy vấn trạng thái build trang Pages (`built`, `building`, `errored`, `queued`).
   - `wait_for_github_pages_built`: Cơ chế polling đợi GitHub Pages build hoàn tất trước khi phát hành URL.

2. **`backend/api/projects.py`**:
   - `_render_project_html(db, project)`: Render mã nguồn HTML (ưu tiên `project_versions.html_snapshot` $\rightarrow$ nạp `templates.file_path` và replace placeholders $\rightarrow$ fallback TailwindCSS HTML chuẩn).
   - `POST /projects/{project_id}/deploy`: Luồng xuất bản đầy đủ với tracking từng bước vào bảng `deployments` (`Rendering` $\rightarrow$ `Creating Repo` $\rightarrow$ `Pushing Code` $\rightarrow$ `Enabling Pages` $\rightarrow$ `Building` $\rightarrow$ `Success`).
   - `GET /projects/{project_id}/deploy-status`: Kiểm tra trạng thái deploy thực tế và tự động cập nhật database khi trang đã build xong.

---

## II. BẢNG ĐẶC TẢ TEST CASES (32 TEST CASES: ĐÚNG - SAI - BIÊN)

| Mã TC | Phân hệ / Hàm | Phân loại | Mô tả kịch bản kiểm thử | Dữ liệu đầu vào (Input) | Kết quả kỳ vọng (Expected Output) | Trạng thái |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| **TC01** | `_resolve_token` | **Đúng** | Truyền token tùy biến hợp lệ | `token = "custom_token_123"` | Trả về đúng `"custom_token_123"` | **PASSED** |
| **TC02** | `_get_headers` | **Sai** | Không cấu hình token hoặc token mặc định | `GITHUB_TOKEN = None` hoặc `"your_github_..."` | Ném `ValueError` báo lỗi thiếu cấu hình | **PASSED** |
| **TC03** | `create_github_repo` | **Đúng** | Tạo repo mới thành công | `repo_name = "lp-test-campaign"`, API trả về 201 | Trả về dict chứa `name`, `full_name`, `html_url`, `default_branch` | **PASSED** |
| **TC04** | `create_github_repo` | **Sai** | Tên repo đã tồn tại trên tài khoản | API trả về 422 Unprocessable Entity | Ném `RuntimeError` chứa mã lỗi 422 | **PASSED** |
| **TC05** | `upload_file_to_repo` | **Đúng** | Upload file mới lần đầu (chưa có SHA) | `file_path = "index.html"`, GET check 404, PUT 201 | File được tạo thành công, trả về `commit_sha` mới | **PASSED** |
| **TC06** | `upload_file_to_repo` | **Đúng** | Ghi đè file đã tồn tại trên repo | File cũ có `sha = "old_sha_456"`, GET check 200 | Request PUT bắt buộc đính kèm `sha` cũ, cập nhật thành công 200 | **PASSED** |
| **TC07** | `upload_file_to_repo` | **Biên** | Upload file ảnh nhị phân (dạng bytes) | `content = b"\x89PNG\r\n..."` | Dữ liệu nhị phân được encode Base64 chuẩn xác | **PASSED** |
| **TC08** | `upload_file_to_repo` | **Sai** | Lỗi quyền hạn hoặc repo không tồn tại | API trả về HTTP 403 Forbidden | Ném `RuntimeError` kèm mã 403 | **PASSED** |
| **TC09** | `push_landing_page_assets`| **Đúng** | Đẩy file `index.html` kèm danh sách ảnh | `images = [{"path": "hero.jpg", "content": b"..."}]` | Upload đủ 2 files, trả về `commit_sha` của commit cuối | **PASSED** |
| **TC10** | `push_landing_page_assets`| **Biên** | Đẩy trang không có ảnh phụ trợ | `images = None` | Chỉ upload duy nhất file `index.html`, không phát sinh lỗi | **PASSED** |
| **TC11** | `enable_github_pages` | **Đúng** | Kích hoạt GitHub Pages lần đầu | API POST `/pages` trả về HTTP 201 Created | Trả về URL chuẩn: `https://{owner}.github.io/{repo}` | **PASSED** |
| **TC12** | `enable_github_pages` | **Đúng** | Kích hoạt Pages khi đã bật từ trước | API POST `/pages` trả về HTTP 409 Conflict | Xử lý an toàn, không báo lỗi, trả về URL chuẩn | **PASSED** |
| **TC13** | `enable_github_pages` | **Sai** | Repo private mà tài khoản chưa nâng cấp Pro | API POST `/pages` trả về HTTP 403 | Ném `RuntimeError` thông báo chi tiết lỗi | **PASSED** |
| **TC14** | `get_github_pages_build_status` | **Đúng** | GitHub Pages build hoàn tất | API trả về status `"built"` | Trả về dict: `status='built'`, `error=None`, `html_url` chuẩn | **PASSED** |
| **TC15** | `get_github_pages_build_status` | **Đúng** | Build đang trong hàng đợi hoặc chưa sẵn sàng | API trả về status `"building"` hoặc 404 | Trả về dict: `status='building'`, `error=None` | **PASSED** |
| **TC16** | `get_github_pages_build_status` | **Sai** | GitHub Pages build bị lỗi nội dung/cấu hình | API trả về status `"errored"` kèm error object | Trả về dict: `status='errored'`, `error` chứa thông báo lỗi | **PASSED** |
| **TC17** | `get_github_pages_build_status` | **Biên** | Chế độ Mock an toàn khi chưa có GITHUB_TOKEN | `token = None`, `GITHUB_TOKEN = None` | Trả về trạng thái `built` mock để hệ thống không crash | **PASSED** |
| **TC18** | `wait_for_github_pages_built` | **Đúng** | Polling chuyển từ `building` sang `built` | Lần 1: building, Lần 2: built | Thoát vòng lặp thành công ngay khi build hoàn tất | **PASSED** |
| **TC19** | `wait_for_github_pages_built` | **Sai** | Trạng thái build chuyển sang `errored` | Status trả về `"errored"` | Dừng polling ngay lập tức và ném `RuntimeError` | **PASSED** |
| **TC20** | `wait_for_github_pages_built` | **Biên** | Quá thời gian timeout mà trang vẫn building | `timeout_seconds = 0.01` | Ném `TimeoutError` với thông điệp rõ ràng | **PASSED** |
| **TC21** | `_render_project_html` | **Đúng** | Render từ snapshot phiên bản trước đó | Dự án có bản ghi trong `project_versions` | Trả về nguyên văn `html_snapshot` mới nhất | **PASSED** |
| **TC22** | `_render_project_html` | **Đúng** | Render fallback chuẩn TailwindCSS khi chưa có template | `project_versions` rỗng, `template_id = None` | Sinh HTML chứa đầy đủ thông tin: tên, mô tả, giá và CDN Tailwind | **PASSED** |
| **TC23** | `_render_project_html` | **Biên** | Dữ liệu `raw_json_data` lỗi cú pháp JSON | `raw_json_data = "{bad_json: 123"` | Bắt lỗi JSONDecodeError an toàn, tiếp tục render HTML không crash | **PASSED** |
| **TC24** | `POST /deploy` | **Đúng** | Luồng deploy đầy đủ cho project mới | Project chưa có `repo_url`, các bước GitHub API thành công | Tạo repo, push code, cập nhật log các bước, lưu `github_pages_url` vào cả `projects` và `deployments`, `status='Success'` | **PASSED** |
| **TC25** | `POST /deploy` | **Đúng** | Xuất bản lại cho project đã có repo | Project đã có sẵn `repo_url` hợp lệ | Bỏ qua bước tạo repo (không tạo trùng), push đè code và build lại | **PASSED** |
| **TC26** | `POST /deploy` | **Sai** | Lỗi bất ngờ trong quá trình deploy (mạng, đĩa) | Ném ngoại lệ `RuntimeError` khi đang push | Rollback DB transaction, cập nhật `deployments.status = 'Failed'`, lưu `error_message`, trả về HTTP 500 | **PASSED** |
| **TC27** | `GET /deploy-status` | **Biên** | Dự án chưa từng được deploy | `repo_url = None`, không có bản ghi trong `deployments` | Trả về HTTP 200: `deploy_status='NotDeployed'`, `pages_build_status='not_configured'`, `is_built=False` | **PASSED** |
| **TC28** | `GET /deploy-status` | **Đúng** | Kiểm tra khi trang đang trong quá trình build | GitHub Pages trả về `"building"` | Trả về `deploy_status='Building'`, `is_built=False`, `github_pages_url=None` | **PASSED** |
| **TC29** | `GET /deploy-status` | **Đúng** | Kiểm tra khi trang vừa build xong | GitHub Pages chuyển sang `"built"` | Tự động đồng bộ DB: cập nhật `deployments.status='Success'`, `projects.status='published'`, `github_pages_url` | **PASSED** |
| **TC30** | `GET /deploy-status` | **Sai** | Kiểm tra khi GitHub Pages build bị lỗi | GitHub Pages trả về `"errored"` | Tự động cập nhật DB: `deployments.status='Failed'`, lưu chi tiết lỗi `error_message` | **PASSED** |
| **TC31** | Toàn bộ file `projects.py` | **Biên** | Kiểm tra tĩnh chống trùng lặp route | Quét code toàn file `backend/api/projects.py` | Endpoint `POST /{project_id}/deploy` xuất hiện đúng 1 lần; Endpoint `GET /{project_id}/deploy-status` xuất hiện đúng 1 lần | **PASSED** |
| **TC32** | Toàn bộ file `projects.py` | **Biên** | Kiểm tra chuẩn hóa tên cột database | Quét từ khóa `published_url` trong `projects.py` | Từ khóa `published_url` hoàn toàn không tồn tại (0 lần), 100% sử dụng cột chuẩn `github_pages_url` | **PASSED** |

---

## III. NHẬT KÝ THỰC THI KIỂM THỬ (TEST EXECUTION LOG)

- **Môi trường thử nghiệm:**
  - Hệ điều hành: Windows 11 64-bit
  - Python Version: Python 3.14 / 3.15
  - Framework kiểm thử: `unittest` (Standard Library)
  - Thư viện hỗ trợ: `unittest.mock` (Patching requests, session DB, asyncio)
- **Lệnh thực thi:**
  ```powershell
  python -m unittest backend/tests/test_deploy_module.py -v
  ```
- **Kết quả thực thi chi tiết:**
  ```text
  test_tc01_resolve_token_custom ... ok
  test_tc02_get_headers_missing_token_raises_value_error ... ok
  test_tc03_create_github_repo_success ... ok
  test_tc04_create_github_repo_api_error_raises_runtime_error ... ok
  test_tc05_upload_new_file_success ... ok
  test_tc06_upload_existing_file_overwrites_with_sha ... ok
  test_tc07_upload_binary_image_content ... ok
  test_tc08_upload_file_api_failure_raises_runtime_error ... ok
  test_tc09_push_landing_page_assets_with_images ... ok
  test_tc10_push_landing_page_assets_no_images ... ok
  test_tc11_enable_github_pages_created_201 ... ok
  test_tc12_enable_github_pages_already_enabled_409 ... ok
  test_tc13_enable_github_pages_error_raises_runtime_error ... ok
  test_tc14_get_pages_status_built ... ok
  test_tc15_get_pages_status_building_on_404 ... ok
  test_tc16_get_pages_status_errored ... ok
  test_tc17_get_pages_status_mock_mode_without_token ... ok
  test_tc18_wait_pages_built_success_after_polling ... ok
  test_tc19_wait_pages_built_errored_aborts ... ok
  test_tc20_wait_pages_built_timeout_raises_timeout_error ... ok
  test_tc21_render_html_from_project_version_snapshot ... ok
  test_tc22_render_html_fallback_standard_tailwind ... ok
  test_tc23_render_html_with_malformed_raw_json ... ok
  test_tc24_deploy_project_full_flow_success ... ok
  test_tc25_deploy_project_existing_repo_no_duplicate_create ... ok
  test_tc26_deploy_project_failure_updates_status_failed ... ok
  test_tc27_deploy_status_not_deployed_yet ... ok
  test_tc28_deploy_status_building_in_progress ... ok
  test_tc29_deploy_status_built_syncs_database ... ok
  test_tc30_deploy_status_errored_syncs_failed_in_db ... ok
  test_tc31_no_duplicate_routes_in_projects_py ... ok
  test_tc32_no_published_url_column_in_projects_py ... ok

  ----------------------------------------------------------------------
  Ran 32 tests in 0.027s

  OK
  ```
- **Thống kê:**
  - Tổng số test case: **32**
  - Số test case thành công (**Passed**): **32 / 32 (100%)**
  - Số test case thất bại (**Failed**): **0**
  - Thời gian chạy toàn bộ: **0.027 giây**

---

## IV. BẢNG THEO DÕI VÀ SỬA LỖI (DEFECT / BUG LOG & RESOLUTION)

Trong quá trình phát triển sprint và kiểm thử module, các lỗi nghiêm trọng sau đã được phát hiện, phân tích nguyên nhân và xử lý triệt để:

| Mã Bug | Tên lỗi phát hiện | Mức độ | Nguyên nhân | Giải pháp đã khắc phục | Trạng thái sau sửa |
| :---: | :--- | :---: | :--- | :--- | :---: |
| **BUG-01** | Trùng lặp endpoint `@router.post("/{project_id}/deploy")` 2 lần liên tiếp | **Nghiêm trọng (Blocker)** | Quá trình merge code giữa nhánh deploy cũ và nhánh mới bị đúp hàm; lần 1 gọi hàm render cũ, lần 2 định nghĩa lại đè lên | Xóa bỏ đoạn code thừa, chỉ giữ duy nhất 1 endpoint `@router.post("/{project_id}/deploy")` hoàn chỉnh với đầy đủ các bước | **Đã sửa (Verified TC31)** |
| **BUG-02** | Trùng lặp endpoint `@router.get("/{project_id}/deploy-status")` và lỗi cú pháp | **Nghiêm trọng (Blocker)** | Route `deploy-status` bị paste nhầm vào giữa phần thân hàm `_render_project_html` làm hỏng cú pháp Python | Tách riêng hàm render lên đầu file, chuyển duy nhất 1 route `deploy-status` xuống cuối file | **Đã sửa (Verified TC31)** |
| **BUG-03** | Sai tên cột cơ sở dữ liệu: dùng `published_url` thay vì `github_pages_url` | **Nghiêm trọng (Major)** | Code cũ sử dụng tên cột `published_url` không tồn tại trong schema bảng `projects` (schema chỉ có `github_pages_url`) | Thay thế toàn bộ các câu lệnh SQL UPDATE trong `deploy_project` và `deploy-status` sang đúng cột `github_pages_url` | **Đã sửa (Verified TC32)** |
| **BUG-04** | Sai chữ ký hàm `_render_project_html(project)` | **Nghiêm trọng (Major)** | Hàm cũ thiếu tham số `db: Session`, truy vấn cột `html_content` không có trong bảng `templates` | Cập nhật chữ ký hàm chuẩn `_render_project_html(db: Session, project: dict)`, đọc file template từ đĩa qua `templates.file_path` và `project_versions` | **Đã sửa (Verified TC21, TC22)** |
| **BUG-05** | Thiếu hàm `_resolve_token` và lỗi import trong `github_service.py` | **Nghiêm trọng (Major)** | Hàm `get_github_pages_build_status` gọi `_resolve_token` nhưng chưa định nghĩa; dòng `import time` bị thụt lề sai; thiếu import `Optional` | Bổ sung hàm `_resolve_token`, import `Optional` từ `typing`, import `time` ở đầu file | **Đã sửa (Verified TC01, TC14)** |
| **BUG-06** | Thiếu các hàm API cốt lõi trong `github_service.py` (`push_landing_page_assets`, `enable_github_pages`) | **Nghiêm trọng (Blocker)** | Nhánh tách từ commit `main` chưa merge module deploy trước đó dẫn đến `ImportError` khi khởi động ứng dụng | Bổ sung đầy đủ các hàm `upload_file_to_repo`, `push_landing_page_assets`, `enable_github_pages` vào `github_service.py` | **Đã sửa (Verified TC05-TC13)** |

---

## V. KẾT LUẬN VÀ BÀN GIAO

1. **Chất lượng module:** Toàn bộ các chức năng thuộc module Deploy & GitHub Pages đã được bao phủ toàn diện với **32 test cases** (Đúng, Sai, Biên) và đạt tỷ lệ kiểm thử thành công **100%**.
2. **Tính tương thích:** Không còn bất kỳ xung đột cú pháp, trùng lặp route hay sai lệch tên cột cơ sở dữ liệu nào.
3. **Các tệp minh chứng đi kèm:**
   - Mã nguồn kiểm thử: [`backend/tests/test_deploy_module.py`](file:///c:/Users/ASUS/OneDrive/Máy tính/codeduan/AI-Auto-Landing-Page-Publisher/backend/tests/test_deploy_module.py)
   - Bảng ma trận Test Case (CSV/Excel): [`docs/TEST_CASE_T02C0C3.csv`](file:///c:/Users/ASUS/OneDrive/Máy tính/codeduan/AI-Auto-Landing-Page-Publisher/docs/TEST_CASE_T02C0C3.csv)
   - Bảng nhật ký Test Log & Bug Log (CSV/Excel): [`docs/TEST_LOG_T02C0C3.csv`](file:///c:/Users/ASUS/OneDrive/Máy tính/codeduan/AI-Auto-Landing-Page-Publisher/docs/TEST_LOG_T02C0C3.csv)
