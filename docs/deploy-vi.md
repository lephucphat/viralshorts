# Triển khai ViralShorts lên một VPS (hướng dẫn từng bước)

Hướng dẫn này đi từ con số không đến một trang web chạy thật có HTTPS, đăng ký, thanh
toán và sao lưu. Bản tham chiếu kỹ thuật (bảng biến môi trường, giới hạn của cách triển
khai này) nằm ở [`ops/README.md`](../ops/README.md); danh sách việc pháp lý phải điền
nằm ở [`docs/compliance/placeholders.md`](compliance/placeholders.md).

> **Trung thực về mức độ đã kiểm chứng.** File `docker-compose.prod.yml` và `Caddyfile`
> đã được viết và kiểm tra cú pháp nhưng **chưa được chạy trọn vẹn trên một VPS thật**.
> Lần triển khai đầu tiên có thể phải sửa vài chỗ nhỏ. Hãy đọc kỹ đầu ra của lệnh
> `docker compose ... config` trước khi `up`, và đừng mở bán trước khi làm hết mục 9.

Một VPS, một container backend, cơ sở dữ liệu SQLite: phù hợp cho đồ án và vài trăm tài
khoản. Không có chạy song song nhiều máy, không có dự phòng: máy chủ tắt thì trang tắt.

## 1. Chuẩn bị (không cần máy chủ)

Những thứ này chỉ bạn làm được. Hãy làm trước vì một số cần vài ngày để được duyệt.

| Việc | Ghi chú |
|---|---|
| Mua **tên miền** | Ở nhà đăng ký bất kỳ (Namecheap, Cloudflare, nhà đăng ký .vn nếu muốn tên miền Việt Nam). Chỉ cần quyền sửa bản ghi DNS. |
| Chọn **VPS** | Tối thiểu 4 vCPU, 8 GB RAM, 80 GB SSD, Ubuntu 22.04/24.04 hoặc Debian 12, có IPv4 công khai. Thoải mái hơn: 8 vCPU, 16 GB RAM, 160 GB. Không cần GPU. Hãy đo bằng video thật của bạn trước khi chốt cấu hình: video dài một giờ xử lý lâu hơn thời lượng thật khi chạy bằng CPU. |
| Khoá **Gemini API** | Từ Google AI Studio. Bắt buộc, không có thì xử lý video trả lỗi 503. Dùng dự án có bật thanh toán nếu chính sách của bạn nói không dùng dữ liệu để huấn luyện. |
| Tài khoản **Stripe** (thẻ quốc tế) | Nhận tiền thật cần doanh nghiệp ở quốc gia Stripe hỗ trợ. Bắt đầu bằng chế độ test (`sk_test_...`). |
| Tài khoản **PayOS** (VietQR) | Tạo kênh thanh toán ở my.payos.vn, lấy `Client ID`, `API Key`, `Checksum Key`. |
| Nhà cung cấp **email SMTP** | Để gửi thư xác minh email, quên mật khẩu, biên nhận. Không có SMTP thì không gửi thư nào và không bắt xác minh email. |
| Bucket **S3 hoặc Cloudflare R2** (hai cái) | Một bucket lưu clip theo gói trả phí (14 và 60 ngày), một bucket riêng cho bản sao lưu. Cả hai để riêng tư. |
| Thông tin **pháp nhân** | Tên, mã số thuế, địa chỉ, email hỗ trợ. Xem mục 9. |

Tuỳ chọn: `FAL_KEY` (video AI), `ELEVENLABS_API_KEY` (giọng nói và lồng tiếng), Google
OAuth (đăng nhập bằng Google).

## 2. Thuê và chuẩn bị VPS

1. Tạo VPS, ghi lại địa chỉ IP công khai.
2. Đăng nhập bằng SSH và cập nhật máy:

```bash
sudo apt-get update && sudo apt-get -y upgrade
```

3. Thêm swap 2 đến 4 GB để chịu được lúc dùng bộ nhớ tăng đột biến:

```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

4. Cài Docker Engine và compose plugin theo hướng dẫn chính thức:
   <https://docs.docker.com/engine/install/>. Kiểm tra: `docker compose version`.

5. Mở tường lửa: chỉ SSH (22), 80, 443 (tcp) và 443/udp (HTTP/3). Tuyệt đối không mở 8000
   hay 3100.

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp && sudo ufw enable
```

Docker bỏ qua ufw khi công bố cổng, nên điều thực sự bảo vệ bạn là file compose: chỉ
service `caddy` có `ports:`. Đừng thêm `ports:` cho `backend`.

## 3. Trỏ DNS

Trước lần khởi động đầu tiên, tạo bản ghi `A` (và `AAAA` nếu có IPv6) cho tên miền trỏ về IP
của VPS. Nếu muốn `www.` cũng chạy, thêm bản ghi cho `www` rồi bỏ comment khối `www` ở cuối
`Caddyfile`.

Kiểm tra DNS đã lan (có thể mất vài phút đến vài giờ):

```bash
dig +short ten-mien-cua-ban.com
```

Phải trả về IP VPS. **Đừng khởi động Caddy khi DNS còn sai**: Let's Encrypt sẽ từ chối và
có thể giới hạn tần suất bạn thử lại.

## 4. Lấy mã nguồn và điền `.env`

```bash
sudo git clone <địa chỉ kho mã của bạn> /opt/viralshorts && cd /opt/viralshorts
cp .env.example .env && chmod 600 .env
nano .env
```

`.env` chứa bí mật: không bao giờ commit nó, và lưu một bản trong trình quản lý mật khẩu
(không nằm trong bản sao lưu; mất nó thì máy chủ dựng lại không khởi động được).

Điền tối thiểu:

| Biến | Giá trị |
|---|---|
| `DOMAIN` | Tên miền, không có `https://`, ví dụ `viralshorts.example.com` |
| `ACME_EMAIL` | Email nhận thông báo hết hạn chứng chỉ của Let's Encrypt |
| `STUDIO_SECRET` | `openssl rand -hex 32`. Giữ cố định: đổi nó là mọi người bị đăng xuất |
| `GEMINI_API_KEY` | Khoá Gemini |
| `STUDIO_PAID` | `1` để bật credit, gói và thanh toán |
| `ADMIN_EMAILS` | Email của bạn (được vào `#/admin`; email này cũng phải được xác minh) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Thông tin SMTP |
| `COMPANY_NAME`, `COMPANY_TAX_CODE`, `COMPANY_ADDRESS`, `SUPPORT_EMAIL` | Khối người bán trên biên nhận. Dùng cùng giá trị với trang pháp lý |
| `ARCHIVE_BUCKET`, `ARCHIVE_ACCESS_KEY_ID`, `ARCHIVE_SECRET_ACCESS_KEY`, `ARCHIVE_ENDPOINT_URL` | Bucket lưu clip theo gói. Để trống thì mọi gói chỉ giữ clip khoảng 1 ngày |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Xem mục 7 |
| `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` | Xem mục 7 |
| `DAILY_AI_BUDGET_CREDITS` | Trần credit tiêu cho API trả phí mỗi ngày, để một ngày xấu không đốt hết ngân sách |

Các giá trị khác (`FAL_KEY`, `ELEVENLABS_API_KEY`, `GOOGLE_CLIENT_ID`...) xem `.env.example`.

`BILLING_ENABLED` được compose ép về `0` và `ACCOUNTS_ENABLED=1`: đừng đặt lại trong `.env`.

### Địa chỉ gốc cho sitemap (SITE_URL)

Các trang pháp lý (`/terms`, `/privacy`, `/refunds`, `/legal-notice`, `/report-content`),
`404.html` và `robots.txt` luôn được tạo khi build. `sitemap.xml`, `llms.txt` và các thẻ
`canonical` chỉ được tạo khi lúc build biết địa chỉ gốc của trang, qua đối số build `SITE_URL`
của image frontend. `docker-compose.prod.yml` hiện **chưa truyền** đối số này; để bật, thêm dòng
sau vào `frontend.build.args` rồi build lại:

```yaml
        SITE_URL: https://${DOMAIN}
```

Chưa làm điều này thì trang vẫn chạy bình thường, chỉ thiếu sitemap và `canonical`.

## 5. Điền thông tin pháp lý và build

Các trang pháp lý đang là **bản nháp có chỗ giữ chỗ trong ngoặc vuông** (`[TÊN PHÁP NHÂN]`,
`[EMAIL HỖ TRỢ]`...). Điền chúng trong `dashboard/seo/site.js` **trước khi mở bán** (mục 9),
vì frontend được build sẵn vào image, mỗi lần sửa phải build lại.

Kiểm tra file compose và các biến bắt buộc:

```bash
docker compose -f docker-compose.prod.yml config > /dev/null && echo OK
```

Lệnh này báo lỗi nếu thiếu `DOMAIN`, `ACME_EMAIL` hoặc `STUDIO_SECRET`.

## 6. Khởi động

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Lần build đầu mất một lúc (tải mô hình, dựng Remotion). `backend` sẽ chuyển sang trạng thái
`healthy`; Caddy tự xin chứng chỉ HTTPS khi DNS đúng. Xem log nếu có gì lạ:

```bash
docker compose -f docker-compose.prod.yml logs -f backend caddy
```

Kiểm tra nhanh từ máy bạn:

```bash
curl -fsS https://ten-mien-cua-ban.com/health/ready
curl -fsSI https://ten-mien-cua-ban.com/terms
```

Cập nhật về sau: `git pull && docker compose -f docker-compose.prod.yml up -d --build`.
Lúc triển khai backend khởi động lại; việc đang chạy được chờ tối đa
`DRAIN_TIMEOUT_SECONDS` (840 giây) nên sẽ có một quãng gián đoạn ngắn.

### Tài khoản quản trị đầu tiên

Đăng ký tài khoản bằng email trong `ADMIN_EMAILS`. Nếu chưa có SMTP và cần đánh dấu email đã
xác minh bằng tay:

```bash
docker compose -f docker-compose.prod.yml exec backend python -m studio.manage verify email-cua-ban@example.com
```

## 7. Đăng ký webhook thanh toán

Chỉ **webhook có chữ ký** mới làm thay đổi tài khoản (cộng credit, đổi gói). Trình duyệt quay
về từ trang thanh toán không bao giờ đổi gì. Vì vậy phải đăng ký webhook, và máy chủ phải đang
chạy ở địa chỉ HTTPS công khai trước.

### PayOS (VietQR)

1. Điền `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` trong `.env`, khởi động lại
   backend: `docker compose -f docker-compose.prod.yml up -d`.
2. Đăng ký địa chỉ webhook:

```bash
docker compose -f docker-compose.prod.yml exec backend python -m studio.manage payos-webhook https://ten-mien-cua-ban.com/api/payos/webhook
```

PayOS gửi một thông báo thử có chữ ký; máy chủ trả 200 và không cộng gì. Mã PayOS được viết
theo tài liệu công khai và **chưa kiểm chứng trên sandbox thật**: hãy chạy một giao dịch thử
trước khi tin vào luồng này (`docs/payments.md`).

### Stripe (thẻ quốc tế)

1. Trong Stripe Dashboard, mục Developers, Webhooks, thêm endpoint:
   `https://ten-mien-cua-ban.com/api/stripe/webhook`.
2. Chọn các sự kiện mà mã xử lý: `checkout.session.completed`,
   `checkout.session.async_payment_succeeded`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`,
   `invoice.payment_failed`, `charge.refunded`, `charge.dispute.created`.
3. Sao chép `Signing secret` (`whsec_...`) vào `STRIPE_WEBHOOK_SECRET` trong `.env`, cùng với
   `STRIPE_SECRET_KEY`, rồi khởi động lại backend.
4. Bắt đầu bằng khoá test. Chuyển sang khoá thật chỉ khi tài khoản Stripe của bạn đã được duyệt.

## 8. Sao lưu hằng đêm

Tài khoản, dự án, sổ credit và bản ghi thanh toán đều nằm trong `state/data/studio.db`. Bản sao
lưu ngoài máy là bản duy nhất còn lại khi mất VPS: **làm trước khi mời người dùng thật**.
Chạy trên máy host (không phải trong container):

```bash
sudo apt-get install -y sqlite3 age awscli
sudo install -d -m 0750 /opt/viralshorts/ops
sudo install -m 0750 ops/backup_studio.sh /opt/viralshorts/ops/backup_studio.sh
```

Tạo cặp khoá `age` **trên máy cá nhân**, không phải trên server (server chỉ cần khoá công khai):

```bash
age-keygen -o viralshorts-backup.key
grep 'public key' viralshorts-backup.key
```

Cất file `.key` trong trình quản lý mật khẩu. Rồi tạo `/etc/viralshorts-backup.env` (quyền `0600`):

```sh
STATE_DIR="/opt/viralshorts/state"
BACKUP_AGE_RECIPIENT="age1................................................"
BACKUP_DEST="s3://ten-bucket-sao-luu/studio"
BACKUP_S3_ENDPOINT="https://<accountid>.r2.cloudflarestorage.com"   # để trống nếu dùng AWS S3
AWS_ACCESS_KEY_ID="..."
AWS_SECRET_ACCESS_KEY="..."
RETENTION_DAYS=30
```

Chạy thử (mã hoá nhưng không tải lên đâu cả), rồi đặt lịch bằng `sudo crontab -e`:

```bash
set -a; . /etc/viralshorts-backup.env; set +a
cd /tmp && DRY_RUN=1 /opt/viralshorts/ops/backup_studio.sh
```

```cron
15 3 * * * set -a; . /etc/viralshorts-backup.env; set +a; /opt/viralshorts/ops/backup_studio.sh >> /var/log/viralshorts-backup.log 2>&1
```

`RETENTION_DAYS` phải khớp với số ngày bạn hứa trong chính sách bảo mật. Hãy thử **khôi phục
một lần** trên máy khác (các bước nằm ở `ops/README.md`, mục Restore): một bản sao lưu chưa
từng khôi phục chỉ là một giả thuyết.

## 9. Trước khi mở bán

Làm hết các việc dưới đây, hoặc sửa cho khớp với thực tế.

- [ ] Điền mọi chỗ giữ chỗ trong `dashboard/seo/site.js` và `.env` (danh sách đầy đủ ở
      [`placeholders.md`](compliance/placeholders.md)), build lại frontend.
- [ ] Nhờ người có chuyên môn pháp lý ở Việt Nam rà soát điều khoản, chính sách bảo mật và
      chính sách hoàn tiền, rồi mới đặt `DRAFT_NOTICE = ''` trong `dashboard/seo/legal.js`.
- [ ] Đặt `ARCHIVE_BUCKET` và thử một dự án đi hết vòng: lưu, khôi phục, hết hạn.
- [ ] Gửi thử đủ các loại thư (xác minh email, quên mật khẩu, biên nhận) tới hộp thư thật.
- [ ] Chạy một giao dịch thử Stripe (chế độ test) và một giao dịch PayOS.
- [ ] Kiểm tra sao lưu đã chạy qua đêm và đã khôi phục thử thành công.
- [ ] Đặt một dịch vụ giám sát bên ngoài (UptimeRobot, Better Stack...) vào
      `https://ten-mien-cua-ban.com/health`.
- [ ] Đo thời gian xử lý một video điển hình trên VPS của bạn và chỉnh `MAX_CONCURRENT_JOBS`,
      `STUDIO_MAX_ACTIVE_JOBS` cho phù hợp.
- [ ] Giá trong `studio/plans.py` là **giá trị mẫu**: tính lại chi phí API thực của bạn trước
      khi bán (`docs/pricing.md`).

## 10. Kiểm tra sau khi chạy

| Kiểm tra | Cách | Kết quả mong đợi |
|---|---|---|
| Sức khoẻ | `curl -fsS https://DOMAIN/health/ready` | 200 |
| HTTPS | Mở `https://DOMAIN` | Ổ khoá hợp lệ, trang giới thiệu hiện ra |
| Trang pháp lý | Mở `/terms`, `/privacy`, `/refunds`, `/legal-notice`, `/report-content` | Mỗi trang trả 200, có khung ViralShorts |
| 404 thật | Mở `/khong-co-trang-nay` | Trang "Không tìm thấy trang" với mã 404, không phải vỏ ứng dụng |
| `robots.txt` | `curl https://DOMAIN/robots.txt` | Chặn `/api/`, `/videos/`, `/thumbnails/` |
| Đăng ký | Tạo tài khoản mới | Nhận thư xác minh (nếu đã đặt SMTP), có 30 credit miễn phí |
| Bảng giá | `https://DOMAIN/#/pricing` | Hiện đủ gói và giá từ máy chủ |
| Xử lý video | Tải một video ngắn lên | Clip ra được, credit bị trừ đúng |
| Thanh toán | Mua gói bằng khoá test | Credit được cộng sau khi webhook tới (xem log backend) |
| Quản trị | Mở `#/admin` bằng email trong `ADMIN_EMAILS` | Thấy bảng điều khiển; tài khoản khác thấy 404 |

Khi có sự cố: `docker compose -f docker-compose.prod.yml logs -f backend caddy`.
