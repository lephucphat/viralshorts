# Thời hạn lưu trữ thực tế

> **Đây không phải tư vấn pháp lý.** Bản này là bản nháp kỹ thuật và cần được
> người có chuyên môn pháp lý tại Việt Nam rà soát trước khi mở bán.

**ViralShorts · [TÊN PHÁP NHÂN] · MST [MÃ SỐ THUẾ] · phiên bản 2026-11-12**

Bảng này là bản dài của Mục 5 trong trang Chính sách bảo mật
(`dashboard/seo/legal.js`). Mỗi hàng ghi **mã nào áp dụng thời hạn**, vì một thời
hạn không có trong mã chỉ là một ý định. Nếu đổi một hằng số, đổi bảng này và
chính sách trong cùng một lần thay đổi. (Tên tệp được giữ nguyên vì
`ops/README.md` đang trỏ tới nó.)

Ký hiệu **❓** là điều chưa được xác minh từ kho mã; **⚠️** là điểm chính sách
hứa nhưng mã chưa thực hiện.

---

## 1. Tệp làm việc trên máy chủ xử lý

| Gì | Thời hạn | Áp dụng ở đâu |
|---|---|---|
| Thư mục tác vụ `output/<job_id>`: video nguồn, clip đã render, checkpoint chép lời | `JOB_RETENTION_SECONDS`: mặc định **86400 s (24 giờ)** khi `BILLING_ENABLED` tắt (đúng với `studio/`), 3600 s khi bật | `app.cleanup_jobs` (`app.py`) |
| Bản tải nguồn giữ lại của tác vụ qua URL | Bằng thời hạn tác vụ, hoặc sớm hơn nếu cấu hình | `SOURCE_RETENTION_SECONDS` |
| Tệp trong `uploads/` | Cùng vòng quét của tác vụ | `app.cleanup_jobs` |
| Ảnh thu nhỏ đã tạo và khung hình lấy mẫu (`output/thumbnails/<phiên>`) | Quét riêng | ❓ Đối chiếu hằng số hiện hành trong `app.py` trước khi nêu số cụ thể. |
| Ảnh nhân vật người dùng tải lên (`output/actor_uploads`) | Quét riêng | ❓ Như trên. Đây là ảnh người thật: ưu tiên kiểm tra. |
| Giới hạn dung lượng ổ đĩa | Xoá tác vụ cũ nhất khi vượt `OUTPUT_MAX_GB` | `app._enforce_output_size_cap` |

Chính sách công khai nói "trong vòng 24 giờ" cho các tệp làm việc. Nếu bạn đổi
`JOB_RETENTION_SECONDS` lên cao hơn, phải sửa lại câu đó.

## 2. Clip của người dùng theo gói

| Gói (số liệu trong `studio/plans.py` là **giá trị mẫu**) | Thời hạn lưu clip |
|---|---|
| Miễn phí | `retention_days` (hiện 1 ngày) |
| Starter | `retention_days` (hiện 14 ngày) |
| Pro | `retention_days` (hiện 60 ngày) |
| Sau khi gói trả phí hết hạn | `[SỐ NGÀY LƯU TRỮ SAU KHI GÓI HẾT HẠN]` |

> **Đã có mã thực thi, nhưng phụ thuộc cấu hình.** `studio/archive.py` chép clip của
> gói trả phí (`archive_days`, tức `retention_days` lớn hơn 1) vào bucket S3/R2 `ARCHIVE_*`,
> cho phép khôi phục trong hạn và xoá khi hết hạn (`purge_expired`, chạy từ vòng dọn).
> Gói Miễn phí không được chép: clip nằm trong `output/<job_id>` và bị dọn theo
> `JOB_RETENTION_SECONDS`. **Nếu `ARCHIVE_BUCKET` để trống, mọi gói chỉ giữ khoảng 1
> ngày**, ngắn hơn con số 14 và 60 ngày trên trang giá. Chỉ công bố các con số đó sau khi
> đã đặt bucket và thử trọn vòng lưu, khôi phục và hết hạn.

## 3. Cơ sở dữ liệu (SQLite `data/studio.db`)

| Gì | Thời hạn | Áp dụng ở đâu |
|---|---|---|
| `users`, `projects`, `brand_kits`, `usage_ledger`, `credit_grants`, `subscriptions` | Trong thời gian tài khoản tồn tại; xoá ngay khi người dùng xoá tài khoản (xoá dây chuyền) | `studio/auth.delete_account` |
| `payment_events` (khử trùng lặp webhook) | ❓ Xác nhận có dữ liệu cá nhân không và có cần xoá cùng tài khoản không | `studio/payments/service.py` |
| Bản khai quyền nội dung (IP, user-agent, thời điểm) | ❓ `app.py` ghi nhận bản khai khi nhận tác vụ; xác minh nó được lưu ở đâu và xoá cùng tài khoản/dự án chưa | `app.py` (khoảng dòng 2779) |
| Dữ liệu thanh toán, hoá đơn, chứng từ kế toán | **Theo thời hạn pháp luật thuế và kế toán Việt Nam quy định** ❓ xác nhận số năm với kế toán/luật sư | Do Stripe/PayOS và sổ sách của doanh nghiệp giữ |

Bản ghi cho biết xoá tài khoản **chưa** ghi một dấu vết "đã xoá" như bản gốc. Nếu
cần chứng minh việc xoá khi có khiếu nại, ❓ cân nhắc thêm một bản ghi chỉ chứa
giá trị băm của email.

## 4. Xoá tài khoản

`DELETE /api/me` (`studio/api.py`) gọi `auth.delete_account`: xác thực bằng mật
khẩu (hoặc gõ lại email với tài khoản chỉ có Google), xoá hàng `users` (kéo theo
các bảng tham chiếu), rồi huỷ các tác vụ đang chạy và xoá tệp làm việc của
chúng (`ctx.cancel_job`, `ctx.remove_job_files`).

> ⚠️ **Xoá tài khoản chưa huỷ đăng ký Stripe.** Mã không gọi Stripe khi xoá, nên
> một người đang có đăng ký định kỳ có thể tiếp tục bị tính tiền sau khi xoá
> (webhook sẽ không tìm thấy người dùng). Chính sách công khai hiện chỉ nhắc
> người dùng tự huỷ gia hạn trước. Nên sửa mã để huỷ đăng ký Stripe **trước** khi
> xoá và dừng xoá nếu Stripe lỗi (đây là thay đổi ngoài phạm vi tài liệu này, ở
> `studio/`). ❓ Xác nhận cũng chưa có đoạn nào xoá tệp ở `output/` ngoài các tác
> vụ liệt kê bởi `projects.job_ids_for_user`.

## 5. Trình duyệt của người dùng (local storage)

| Gì | Thời hạn | Ở đâu |
|---|---|---|
| Mã phiên đăng nhập | Cho đến khi đăng xuất hoặc hết hạn token | `studio/security.py`, phía dashboard |
| Mã truy cập clip ngắn hạn, URL có chữ ký | Theo `expires` của chữ ký | `studio/security.sign_resource` |
| Lựa chọn cookie | Đến khi người dùng đổi, hoặc phiên bản biểu ngữ đổi | `dashboard/src/lib/consent.js` |
| Tuỳ chọn giao diện | Đến khi người dùng xoá dữ liệu trang | `dashboard/src` |

## 6. Nhật ký, sao lưu, phân tích

| Gì | Thời hạn | Ghi chú |
|---|---|---|
| Nhật ký ứng dụng (stdout của container) | `[THỜI HẠN LƯU NHẬT KÝ]` | ❓ Cần cấu hình xoay vòng log (`max-size`, `max-file`) ở runtime, nếu không thời hạn thực phụ thuộc vào Docker. |
| Bản sao lưu cơ sở dữ liệu | `[THỜI HẠN LƯU BẢN SAO LƯU]` | `ops/backup_studio.sh` (biến `RETENTION_DAYS`, mặc định 30). ❓ Cài, đặt lịch và thử khôi phục một lần; số ngày phải khớp với câu trong chính sách. |
| Phân tích (OpenPanel, chỉ khi đồng ý) | `[THỜI HẠN LƯU DỮ LIỆU PHÂN TÍCH]` | ❓ Cấu hình trên chính instance. |

## Còn tồn đọng

- Đặt `ARCHIVE_BUCKET` và thử trọn vòng lưu clip theo gói (mục 2).
- Cài `ops/backup_studio.sh` và thử khôi phục.
- Xoay vòng log của container.
- Dọn tài khoản miễn phí không hoạt động lâu (ví dụ 24 tháng, có báo trước): chưa
  quyết định, chưa triển khai.
