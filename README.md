# ViralShorts

ViralShorts là dịch vụ web trả phí tự động cắt video dài thành các clip dọc 9:16 cho TikTok,
Instagram Reels và YouTube Shorts. Bạn tải lên một video (MP4, MOV, tối đa 2GB) hoặc dán một
liên kết; hệ thống phiên âm, chọn những khoảnh khắc có tiềm năng nhất, cắt sang khung dọc và
chấm điểm viral kèm lý do để bạn biết nên đăng clip nào.

Đây là đồ án tốt nghiệp. Kho mã này gồm dịch vụ (backend FastAPI), giao diện (React/Vite), lớp
tài khoản, thanh toán và tài liệu vận hành.

> **Trạng thái:** mọi văn bản pháp lý (điều khoản, bảo mật, hoàn tiền, thông tin pháp lý) đang là
> **bản nháp có chỗ giữ chỗ**, chưa được luật sư rà soát. Đừng mở bán trước khi điền xong và rà
> soát: xem [`docs/compliance/placeholders.md`](docs/compliance/placeholders.md).

## Tính năng

- **Cắt clip dọc tự động**: bám theo người đang nói, đổi bố cục khi có hai người trong khung
  hoặc có màn hình chia sẻ. Video đã quay dọc được giữ nguyên, không bị thu nhỏ.
- **Điểm viral giải thích được**: kết hợp đánh giá của AI với các tín hiệu đo từ lời nói và âm
  thanh; bạn xem từng thành phần của điểm.
- **Phụ đề, hook và ảnh thu nhỏ**: nhiều kiểu phụ đề, chữ mở đầu, bộ tạo ảnh thu nhỏ.
- **Bộ nhận diện thương hiệu**: logo và kiểu phụ đề của bạn áp dụng cho mọi clip.
- **Lồng tiếng AI** sang nhiều ngôn ngữ, giữ giọng người nói (gói trả phí).
- **Đăng và lên lịch** lên các mạng xã hội bạn kết nối (gói trả phí).
- **AI Shorts** tạo video từ kịch bản (gói Pro) và **API / MCP** để tự động hoá (gói Pro).

## Gói và thanh toán

Credit là đơn vị trả phí duy nhất: tạo clip tốn 1 credit cho mỗi phút video nguồn, các thao tác AI
khác có giá riêng. Có gói miễn phí hằng tháng, gói trả phí theo tháng và credit nạp thêm (không
hết hạn). Thanh toán bằng thẻ quốc tế qua Stripe hoặc VietQR qua PayOS.

Các con số hiện hành được máy chủ công bố ở `GET /api/billing/plans` và hiển thị ở trang
`#/pricing`; nguồn gốc là `studio/plans.py`. Giá trong đó là **giá trị mẫu**, cần tính lại theo
chi phí API thực trước khi bán: xem [`docs/pricing.md`](docs/pricing.md) và
[`docs/payments.md`](docs/payments.md).

## Kiến trúc

```
Trình duyệt ──> Caddy (HTTPS tự động)
                 ├─ /api /videos /thumbnails /gallery /video /mcp /health ──> backend (FastAPI, SQLite)
                 └─ còn lại ────────────────────────────────────────────────> frontend (nginx, React build)
backend ──> renderer (Remotion, chỉ trong mạng nội bộ)
```

Luồng xử lý: nhập video, phiên âm (faster-whisper), phát hiện cảnh, AI chọn khoảnh khắc (Gemini),
cắt bằng FFmpeg, đổi khung dọc có bám đối tượng, phụ đề và hook, lồng tiếng tuỳ chọn, lưu trữ
và đăng.

| Thành phần | Nơi |
|---|---|
| Backend, hàng đợi việc, REST | `app.py`, `main.py` |
| Tài khoản, credit, thanh toán, thư | `studio/` |
| Giao diện | `dashboard/` (React + Vite + Tailwind) |
| Trang pháp lý tĩnh, robots, sitemap | `dashboard/seo/`, `dashboard/vite-plugin-seo.js` |
| Dựng video (Remotion) | `render-service/`, `remotion/` |
| Triển khai và sao lưu | `docker-compose.prod.yml`, `Caddyfile`, `ops/` |

Thư mục `cloud/` thuộc một giấy phép thương mại riêng và **không được dùng** cho dịch vụ này;
lớp tài khoản và thanh toán là mã viết riêng trong `studio/`.

## Chạy trên máy của bạn (phát triển)

Cần Docker. Tạo `.env` từ mẫu rồi điền ít nhất `GEMINI_API_KEY`:

```bash
cp .env.example .env
docker compose up --build
```

- Backend: <http://localhost:8000>
- Giao diện: <http://localhost:5175> (Vite chuyển tiếp các lời gọi API sang backend)

Để chạy chế độ có tài khoản và thanh toán, đặt `ACCOUNTS_ENABLED=1` và `STUDIO_PAID=1` trong
`.env` (các khoá Stripe và PayOS dùng chế độ test).

Chỉ giao diện:

```bash
cd dashboard
npm ci
npm run dev       # máy chủ dev, HMR
npm run lint      # ESLint nghiêm ngặt, không cho phép cảnh báo
npm run build     # bản build production (kèm các trang pháp lý tĩnh)
```

Kiểm thử backend:

```bash
pip install -r requirements.txt
pytest tests
```

## Triển khai

Hướng dẫn từng bước bằng tiếng Việt, từ mua tên miền đến kiểm tra sau khi chạy:
[`docs/deploy-vi.md`](docs/deploy-vi.md). Bản tham chiếu kỹ thuật (biến môi trường, giới hạn của
cách triển khai một VPS, sao lưu và khôi phục): [`ops/README.md`](ops/README.md).

Tóm tắt:

```bash
cp .env.example .env && chmod 600 .env     # điền DOMAIN, ACME_EMAIL, STUDIO_SECRET, GEMINI_API_KEY...
docker compose -f docker-compose.prod.yml up -d --build
```

## API và MCP

Gói Pro có khoá API (`vsk_...`, tạo ở trang Tài khoản) dùng như Bearer token cho REST và cho
điểm cuối MCP `/mcp`, để script hoặc trợ lý AI gọi các thao tác tạo clip và đăng bài. Khoá không
được dùng để quản lý khoá, xuất dữ liệu hay đăng xuất các thiết bị khác.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [`docs/deploy-vi.md`](docs/deploy-vi.md) | Triển khai từng bước |
| [`ops/README.md`](ops/README.md) | Vận hành, biến môi trường, sao lưu |
| [`docs/payments.md`](docs/payments.md) | Credit, Stripe, PayOS, email, quản trị |
| [`docs/pricing.md`](docs/pricing.md) | Gói, giá và cách định giá |
| [`docs/compliance/placeholders.md`](docs/compliance/placeholders.md) | Việc chủ sở hữu phải điền trước khi mở bán |
| [`docs/compliance/subprocessors.md`](docs/compliance/subprocessors.md) | Danh sách bên xử lý dữ liệu |
| [`docs/compliance/data-retention.md`](docs/compliance/data-retention.md) | Thời hạn lưu dữ liệu |
| [`docs/dsa-notice-and-action.md`](docs/dsa-notice-and-action.md) | Quy trình tiếp nhận báo cáo nội dung vi phạm |

## Giấy phép

Xem [`LICENSE`](LICENSE). Thư mục `cloud/` có giấy phép riêng ghi trong chính nó.
