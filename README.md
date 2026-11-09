# Dự Án Thuyết Minh Tự Động

Ứng dụng web du lịch ẩm thực đường phố (TP.HCM): bản đồ tương tác, thuyết minh âm thanh đa ngôn ngữ tự động khi đi vào vùng quán (geofence).

- Backend: FastAPI + MySQL 8 + Redis, Edge-TTS, dịch miễn phí (Google gtx → MyMemory → deep-translator)
- Frontend: React 19 + Vite 7, MapLibre, Turf
- Cổng quản trị (RBAC), cổng chủ quán, AI Advisor (Gemini), analytics có consent
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

## Test

```bash
# backend (36 test, chạy trong container, cần stack đang chạy)
MSYS_NO_PATHCONV=1 docker compose exec -T -e PYTHONPATH=/srv backend \
  pytest tests -o asyncio_mode=auto -o asyncio_default_fixture_loop_scope=function -p no:cacheprovider -q
# frontend (6 test)
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

`.env` chứa khoá bí mật và đã được đưa vào `.gitignore`; không commit file này.

## Ghi chú về chức năng offline đã bỏ

Bản trước có service worker, IndexedDB, Offline Pack và map pack PMTiles. Các phần này đã được xoá. Để dọn trình duyệt từng cài bản cũ, `frontend/public/sw.js` là một "kill-switch" tự gỡ service worker và xoá cache cũ; có thể xoá file này sau khi không còn người dùng bản cũ.

## Cấu trúc

```
backend/app/{content,audio,localization,admin,owner,ai_advisor,analytics,ui_i18n,runtime_observability}/
backend/tests/            # pytest tích hợp + đơn vị
frontend/src/{pages,components,services,stores}/
docker-compose.yml
```
"# thuyet-minh-tu-dong" 
