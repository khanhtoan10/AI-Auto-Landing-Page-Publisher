# Frontend - AI Auto-Landing Page Publisher

Giao diện web quản lý hệ thống tạo và xuất bản Landing Page tự động bằng AI.

## Triển Khai Nhanh Lên Vercel

Dự án đã được cấu hình sẵn file `vercel.json` hỗ trợ triển khai trực tiếp:
1. Kết nối repository GitHub này vào [Vercel](https://vercel.com).
2. Chọn **Root Directory** là `./` hoặc `frontend`.
3. Nhấn **Deploy**.

## Cấu Hình Backend Demo

- **Cách 1 (Giao diện)**: Mở trang Dashboard -> Thẻ *Trạng thái kết nối* -> Bấm **Cấu hình** -> Nhập URL Backend -> Lưu.
- **Cách 2 (URL Query)**: Truy cập `https://<ten-project>.vercel.app/?api=https://<your-backend-url>`.
- **Cách 3 (File cấu hình)**: Điền URL vào file `js/config.js`.

Chi tiết xem tại [docs/huong_dan_deploy_vercel.md](../docs/huong_dan_deploy_vercel.md).
