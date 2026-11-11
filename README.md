# Dự Án Thuyết Minh Tự Động

Ứng dụng web du lịch ẩm thực đường phố (TP.HCM): bản đồ tương tác, thuyết minh âm thanh đa ngôn ngữ tự động khi đi vào vùng quán (geofence).

- Backend: FastAPI + MySQL 8 + Redis, Edge-TTS, dịch miễn phí (Google gtx → MyMemory → deep-translator)
- Frontend: React 19 + Vite 7, MapLibre, Turf
- Cổng quản trị (RBAC), cổng chủ quán, AI Advisor (Gemini), analytics có consent
- Popup quán cho du khách: ảnh, mô tả, nút Nghe, thực đơn (tên món dịch theo ngôn ngữ đã chọn)
- Quản lý ảnh quán (admin + chủ quán), quên mật khẩu qua email, xuất thống kê CSV
- Khách đã đăng nhập có thể lưu/bỏ lưu quán yêu thích, xem danh sách và nhận gợi ý dựa trên tên, mô tả và món ăn từ quán đã lưu
- Không có chế độ offline (đã bỏ theo yêu cầu): ứng dụng cần kết nối tới máy chủ

## Chạy nhanh

```bash
cp .env.example .env            # dev: không cần sửa gì
docker compose up -d --build    # mysql + redis + backend (http://localhost:8000)
cd frontend && npm install
npm run dev                     # http://localhost:5173
# hoặc bản build:
npm run build && npm run preview   # http://127.0.0.1:4173
```

Tài khoản super admin dev: `admin` / `admin12345` (đặt `SUPERADMIN_PASSWORD` ở môi trường khác dev; khi `APP_ENV` ≠ `dev`, backend từ chối khởi động nếu còn secret mặc định).

Môi trường dev cũng tự tạo 15 tài khoản chủ quán mẫu (đã xác minh), mỗi tài khoản quản lý một quán ở một khu vực khác nhau tại TP.HCM. Dùng tên đăng nhập `owner_q1`, `owner_q3`, `owner_q4`, `owner_q5`, `owner_q6`, `owner_q7`, `owner_q8`, `owner_q10`, `owner_q11`, `owner_binhthanh`, `owner_govap`, `owner_tanbinh`, `owner_phunhuan`, `owner_thuduc` hoặc `owner_nhabe`; mật khẩu chung trong demo: `Demo@12345`. Các tài khoản và quán được seed idempotent khi backend khởi động, không được tạo ở môi trường khác dev.

Các quán mẫu có thực đơn demo riêng. Khi backend khởi động, hệ thống kiểm tra audio dịch/TTS theo các ngôn ngữ hỗ trợ và xếp hàng tạo phần còn thiếu cho mọi quán đang hoạt động; tác vụ chạy nền và cần kết nối tới dịch vụ dịch cùng Edge-TTS.

## Test

```bash
# backend (48 test, chạy trong container, cần stack đang chạy)
MSYS_NO_PATHCONV=1 docker compose exec -T -e PYTHONPATH=/srv backend \
  pytest tests -o asyncio_mode=auto -o asyncio_default_fixture_loop_scope=function -p no:cacheprovider -q
# frontend (10 test)
cd frontend && npm test
```

## Dữ liệu demo

Có sẵn 8 quán mẫu khi DB trống. Để có đủ bộ demo (80 quán đường phố rải ra 16 khu vực của TP.HCM, mỗi quán có thực đơn kèm giá, giọng đọc 5 ngôn ngữ tạo sẵn), chạy một lần:

```bash
docker compose exec -T backend python -m app.content.seed_demo
```

Lệnh này an toàn khi chạy lại (quán/món đã có được bỏ qua, quán từng bị lỗi tạo giọng đọc sẽ được thử lại) và mất vài phút ở lần đầu vì phải dịch và tạo giọng đọc. Nếu cuối lệnh báo có quán lỗi (thường do dịch vụ dịch miễn phí bị giới hạn tạm thời), chỉ cần chạy lại.

Đây là dữ liệu minh hoạ: tên quán là tên chung, mô tả và giá do nhóm soạn, toạ độ chỉ xấp xỉ quanh tâm mỗi khu vực — không phải thông tin xác thực của từng quán ngoài đời. Trên bản đồ, dùng ô **Khu vực** để nhảy nhanh tới từng khu, bấm vào một quán để xem mô tả và thực đơn.

## Demo geofence

Mở bản đồ → bật **Mock GPS** → bấm lên bản đồ ngay dưới chân marker của một quán. Sau ~3 giây app phát thuyết minh (toast cho biết đang ở Tier nào).

## Cấu hình tuỳ chọn

| Biến | Tác dụng |
|---|---|
| `GEMINI_API_KEY` | Bật AI Advisor (nâng cấp mô tả). Không có key → API trả 503 `provider_unconfigured`, không tốn quota |
| `SUPERADMIN_PASSWORD`, `JWT_SECRET`, `REFRESH_TOKEN_SECRET`, `SECRET_KEY` | Bắt buộc khi `APP_ENV` ≠ `dev` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Gửi email đặt lại mật khẩu. Ở dev chưa cấu hình SMTP thì trang "Quên mật khẩu" hiện link đặt lại trực tiếp (và ghi ra log backend) |
| `PUBLIC_BASE_URL` | Địa chỉ frontend dùng trong link đặt lại mật khẩu (mặc định `http://localhost:5173`) |

`.env` chứa khoá bí mật và đã được đưa vào `.gitignore`; không commit file này.

## Các chức năng bổ sung

| Chức năng | Ghi chú |
|---|---|
| Thực đơn + ảnh cho du khách | Bấm marker → popup có ảnh, nút **Nghe** (phát lại thủ công), thực đơn. `GET /api/v1/poi/{id}/menu?lang=en` trả kèm `name_translated` (dịch best-effort, quá 6 s thì trả tên gốc và dịch tiếp dưới nền). Quán đang ẩn → 404. 8 quán mẫu có sẵn thực đơn demo |
| Quản lý ảnh quán | `POST /api/v1/media/images` với body là file ảnh (không cần multipart). Chỉ JPEG/PNG/WebP ≤ 2 MB, nhận diện bằng magic bytes; tối đa 8 ảnh/quán, ảnh đầu là ảnh đại diện. POI chỉ nhận URL `/static/images/…` do hệ thống cấp. Đổi ảnh không làm sinh lại audio. Ảnh chủ quán gửi đi qua kiểm duyệt như nội dung khác |
| Quên mật khẩu | `/forgot-password` → link `/reset-password?token=…` hết hạn sau 30 phút, dùng một lần; DB chỉ lưu SHA-256 của token. Trả cùng một thông điệp dù tài khoản có tồn tại hay không. Sau khi đặt lại/đổi mật khẩu, refresh token cũ bị từ chối (access token cũ còn hiệu lực tối đa 30 phút) |
| Xuất thống kê | Tab Thống kê → **Tải CSV** (quyền `analytics:export`): theo ngày × sự kiện × quán × ngôn ngữ, UTF-8 BOM để Excel đọc đúng tiếng Việt, có chặn CSV formula injection |
| Quán yêu thích | Khách đăng nhập bấm **Lưu yêu thích** trong popup quán; nút **Yêu thích** trên bản đồ hiển thị danh sách, cho phép bỏ lưu và xem quán gợi ý theo nội dung/thực đơn đã chọn |
| Admin | Sửa món + mô tả món, lọc thực đơn theo quán, đặt mật khẩu mới cho người dùng, xem ảnh trong bài chờ duyệt, bảng ngôn ngữ được chọn. Xoá tài khoản thì xoá luôn đơn đăng ký (CCCD) và thông báo của tài khoản đó |

## Ghi chú về chức năng offline đã bỏ

Bản trước có service worker, IndexedDB, Offline Pack và map pack PMTiles. Các phần này đã được xoá. Để dọn trình duyệt từng cài bản cũ, `frontend/public/sw.js` là một "kill-switch" tự gỡ service worker và xoá cache cũ; có thể xoá file này sau khi không còn người dùng bản cũ.

## Cấu trúc

```
backend/app/{content,audio,localization,admin,owner,ai_advisor,analytics,ui_i18n,runtime_observability,media}/
backend/tests/            # pytest tích hợp + đơn vị
frontend/src/{pages,components,services,stores}/
docker-compose.yml
```
"# thuyet-minh-tu-dong" 
