# Hướng Dẫn Triển Khai Web Quản Lý Lên Vercel & Kết Nối Backend Demo

Tài liệu này hướng dẫn chi tiết cách đưa giao diện Web quản lý (**Frontend**) của dự án **AI Auto-Landing Page Publisher** lên nền tảng **Vercel** để chạy bản demo trực tuyến, cấu hình trỏ tới máy chủ **FastAPI Backend**, và tài liệu kiểm thử cho người chấm/đánh giá.

---

## 1. Kiến Trúc & Cơ Chế Kết Nối

Dự án đã được tích hợp sẵn các cơ chế tối ưu cho việc chạy demo trên Vercel:

| Tính năng | Mô tả chi tiết |
| :--- | :--- |
| **Cấu hình Vercel (`vercel.json`)** | Định tuyến toàn bộ static pages, assets (`/`, `/pages/*`, `/css/*`, `/js/*`) và thiết lập Reverse Proxy chuyển tiếp an toàn các API call (`/api/*`, `/auth/*`, `/projects/*`, `/deployments/*`, `/templates/*`, `/versions/*`) sang máy chủ backend. |
| **Hỗ trợ Monorepo / Subfolder** | Cung cấp sẵn cả `vercel.json` ở thư mục gốc (Root) và `frontend/vercel.json` (nếu chọn Root Directory là `frontend` trên Vercel). |
| **Mở rộng CORS Backend** | `backend/main.py` đã cấu hình `allow_origin_regex=r"https://.*\.vercel\.app"`, cho phép bất kỳ domain hoặc preview branch nào trên Vercel gọi API trực tiếp mà không bị lỗi CORS. |
| **Cơ chế đổi Backend động (Zero-code)** | Người đánh giá có thể trỏ giao diện tới bất kỳ Backend nào mà không cần sửa code thông qua: <br>1. Truy cập qua URL param: `?api=https://your-backend.com`<br>2. Bấm nút **"Cấu hình"** ngay tại thẻ *Trạng thái kết nối* trên Dashboard<br>3. Khai báo cố định tại `frontend/js/config.js` |

---

## 2. Hướng Dẫn Triển Khai Lên Vercel

### Cách 1: Triển khai trực tiếp từ GitHub (Khuyến nghị)

1. **Đẩy mã nguồn lên GitHub**:
   ```bash
   git add .
   git commit -m "feat: config vercel deployment and demo backend connection"
   git push origin main
   ```
2. **Đăng nhập Vercel**:
   - Truy cập [https://vercel.com](https://vercel.com) và đăng nhập bằng tài khoản GitHub.
3. **Tạo Project mới**:
   - Bấm **Add New...** -> **Project**.
   - Tìm và chọn repository `AI-Auto-Landing-Page-Publisher` -> Bấm **Import**.
4. **Cấu hình Project Settings**:
   - **Framework Preset**: Chọn `Other`.
   - **Root Directory**:
     - *Lựa chọn A (Mặc định)*: Giữ nguyên `./` (Vercel sẽ tự dùng file `vercel.json` ở thư mục gốc).
     - *Lựa chọn B*: Bấm **Edit** và chọn thư mục `frontend` (Vercel sẽ dùng `frontend/vercel.json`).
   - **Build & Output Settings**: Không cần điền (đây là Static Web thuần HTML/CSS/JS).
5. **Bấm Deploy**:
   - Chờ Vercel build trong khoảng 15–30 giây.
   - Vercel sẽ cấp một liên kết demo dạng: `https://ai-auto-landing-page-publisher.vercel.app` (hoặc tương tự).

---

### Cách 2: Triển khai nhanh bằng Vercel CLI

Nếu đã cài Node.js, bạn có thể triển khai trực tiếp từ máy tính:

```bash
# Cài đặt hoặc chạy Vercel CLI
npx vercel

# Khi được hỏi các thông tin:
# ? Set up and deploy “~/AI-Auto-Landing-Page-Publisher”? [Y/n] -> Y
# ? Which scope do you want to deploy to? -> Chọn tài khoản của bạn
# ? Link to existing project? [y/N] -> N
# ? What’s your project’s name? -> ai-landing-page-publisher
# ? In which directory is your code located? -> ./ (hoặc ./frontend)

# Triển khai bản Production chính thức:
npx vercel --prod
```

Sau khi hoàn tất, terminal sẽ in ra **Production URL** của Vercel.

---

## 3. Cấu Hình Trỏ Tới Backend Chạy Demo

Bạn có thể trỏ giao diện Vercel tới Backend Demo theo một trong các cách sau:

### Lựa chọn A: Cấu hình nhanh qua giao diện Web (Khuyên dùng khi chấm demo)
1. Mở trang Vercel của bạn (ví dụ: `https://your-app.vercel.app`).
2. Tại màn hình **Tổng quan (Dashboard)**, nhìn xuống góc phải tại thẻ **Trạng thái kết nối**.
3. Bấm vào nút **"Cấu hình"** (biểu tượng thanh gạt).
4. Nhập URL của Backend Demo (ví dụ: `https://ai-landing-page-backend.onrender.com` hoặc link ngrok).
5. Bấm **Lưu & Áp dụng** — Web sẽ tự động tải lại và kiểm tra kết nối (hiển thị `● Online` màu xanh lá).

### Lựa chọn B: Truy cập trực tiếp bằng URL Parameter
Người chấm/kiểm thử chỉ cần mở link kèm tham số `?api=`:
```
https://your-app.vercel.app/?api=https://your-backend-demo-url.com
```
Hệ thống sẽ tự động lưu địa chỉ này vào `localStorage` của trình duyệt và sử dụng cho tất cả các trang tiếp theo.

### Lựa chọn C: Cấu hình trong mã nguồn (`frontend/js/config.js` & `vercel.json`)
Mở file `frontend/js/config.js` và điền URL backend demo:
```javascript
window.__DEFAULT_BACKEND_URL__ = "https://your-backend-demo-url.com";
```
Đồng thời cập nhật trường `destination` trong `vercel.json` nếu muốn dùng Vercel Reverse Proxy.

---

## 4. Hướng Dẫn Chạy Backend Demo

Backend FastAPI cần kết nối CSDL MySQL và API Gemini. Bạn có 2 phương án chạy backend demo:

### Phương án 1: Dùng Cloud Server (Render / Railway / Koyeb)
1. Tạo một Database MySQL miễn phí trên [Aiven.io](https://aiven.io), [Clever Cloud](https://clever-cloud.com) hoặc [TiDB Cloud](https://tidbcloud.com).
2. Tạo Web Service trên [Render.com](https://render.com) trỏ tới thư mục `backend/`:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 10000`
   - **Environment Variables**:
     - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
     - `GEMINI_API_KEY` (Key lấy từ Google AI Studio)
     - `GITHUB_TOKEN` (Personal Access Token GitHub có quyền `repo`)
     - `CORS_ORIGINS`: `https://your-app.vercel.app`

### Phương án 2: Chạy Backend Local kết hợp Tunnel (Ngrok / Cloudflare Tunnel)
Để phục vụ chấm demo tức thì từ máy tính cá nhân:
1. Chạy Backend local:
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```
2. Mở tunnel HTTPS ra ngoài internet bằng `ngrok`:
   ```bash
   ngrok http 8000
   ```
3. Copy link HTTPS từ ngrok (ví dụ: `https://a1b2-xxx.ngrok-free.app`) và dán vào mục Cấu hình trên web Vercel.

---

## 5. Hướng Dẫn Truy Cập & Dữ Liệu Kiểm Thử

### Tài khoản Demo có sẵn (Đã seed trong hệ thống):

| Vai trò | Email đăng nhập | Mật khẩu | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Admin** | `tiendat.admin@example.com` | `Admin123@` | Toàn quyền quản trị, xem danh sách dự án |
| **Thành viên 1** | `member1@example.com` | `Password123!` | Tài khoản thành viên kiểm thử |
| **Thành viên 2** | `member2@example.com` | `Password123!` | Tài khoản thành viên kiểm thử |

*Lưu ý*: Người dùng cũng có thể bấm sang tab **Đăng ký** tại màn hình `login.html` để tạo một tài khoản mới bất kỳ lúc nào.

### Quy trình kiểm thử đề xuất (Test Flow):
1. **Đăng nhập**: Mở trang web Vercel -> tự chuyển về `/login.html` -> Nhập email/mật khẩu demo -> Bấm Đăng nhập.
2. **Kiểm tra trạng thái hệ thống**: Tại Dashboard, kiểm tra thẻ *Trạng thái kết nối* hiển thị `Host: ... ● Online`.
3. **Tạo Landing Page mới bằng AI**:
   - Menu trái -> chọn **Tạo Landing Page AI**.
   - Chọn một mẫu giao diện trong kho mẫu (ví dụ: Mỹ phẩm, Công nghệ, Bất động sản...).
   - Nhập thông tin sản phẩm và chiến dịch -> Bấm **Tạo với AI (Gemini)**.
4. **Xem trước (Iframe Preview)**:
   - Hệ thống tự mở trang xem trước.
   - Thử chuyển đổi giữa 3 chế độ xem: **Desktop**, **Tablet**, **Mobile**.
5. **Chỉnh sửa & Xem lịch sử**:
   - Bấm sang trang **Chỉnh sửa** để cập nhật tiêu đề, mô tả, nút CTA.
   - Bấm xem **Lịch sử phiên bản** để kiểm tra các bản lưu (snapshots) và khôi phục khi cần.
6. **Xuất bản (Publish to GitHub Pages)**:
   - Bấm **Xuất bản** -> Hệ thống gọi GitHub API tạo repository và cấu hình GitHub Pages.
   - Theo dõi trạng thái triển khai hiển thị theo thời gian thực (Queued -> Building -> Active).
   - Bấm **Truy cập Website** để mở landing page thực tế chạy trên GitHub Pages (`https://<username>.github.io/<repo>/`).

---

## 6. Mẫu Báo Cáo Nộp Bài (Submission Format)

Khi nộp bài cho task `[FE] Đưa web quản lý lên Vercel để demo`, bạn có thể sử dụng mẫu sau:

```markdown
### NỘP BÀI TASK: [FE] Đưa web quản lý lên Vercel để demo

- **Link Web Quản lý (Vercel Demo)**: https://ai-auto-landing-page-publisher.vercel.app
- **Link Backend API Demo**: https://ai-landing-page-backend-demo.onrender.com (hoặc link server demo)
- **Tài khoản đăng nhập kiểm thử**:
  + Email: tiendat.admin@example.com
  + Mật khẩu: Admin123@
- **Cách thức kết nối**:
  + Mặc định web tự động kết nối qua Vercel Reverse Proxy và cấu hình backend demo.
  + Nếu cần trỏ tới Backend riêng, có thể mở link dạng:
    https://ai-auto-landing-page-publisher.vercel.app/?api=<BACKEND_URL>
    hoặc bấm nút "Cấu hình" tại thẻ Trạng thái kết nối ở trang chủ.
- **Tài liệu hướng dẫn chi tiết**: docs/huong_dan_deploy_vercel.md
```
