# Danh sách giữ chỗ cần điền trước khi mở bán

> **Đây không phải tư vấn pháp lý.** Bộ tài liệu pháp lý của ViralShorts là bản
> nháp kỹ thuật và cần được người có chuyên môn pháp lý tại Việt Nam rà soát
> trước khi mở bán.

Toàn bộ giữ chỗ của thông tin pháp nhân, các điều khoản do chủ sở hữu quyết định và tên
nhà cung cấp hạ tầng nằm ở **một file duy nhất: `dashboard/seo/site.js`**. Cả các trang
tĩnh `/terms`, `/privacy`, `/legal-notice`, `/report-content`, `/refunds` (`seo/legal.js`),
trang tổng hợp `#legal` (`src/Legal.jsx`), phần Liên hệ và chân trang của trang giới thiệu
(`src/Landing.jsx`) đều đọc từ đó, nên điền một lần là mọi nơi cùng cập nhật (cần build lại
frontend). Riêng một số giữ chỗ được viết thẳng trong văn bản (đánh dấu "trong văn bản")
nằm trong `dashboard/seo/legal.js`. Sau khi điền xong và được rà soát, đặt
`DRAFT_NOTICE = ''` trong `legal.js` để bỏ ghi chú nháp trên các trang, và xoá dòng
"Lưu ý (bản nháp)" trong `Legal.jsx`.

Ngoài frontend, mấy giá trị sau phải điền **cả trong `.env`** để biên nhận và email khớp
với trang pháp lý: `COMPANY_NAME`, `COMPANY_TAX_CODE`, `COMPANY_ADDRESS`, `SUPPORT_EMAIL`
(khối "người bán" trên biên nhận, `docs/payments.md`) và `SMTP_FROM`.

## 1. Thông tin pháp nhân

| Giữ chỗ | Dùng ở | Ghi chú |
|---|---|---|
| `[TÊN PHÁP NHÂN]` | tất cả các trang; Legal.jsx | Tên công ty/hộ kinh doanh/cá nhân kinh doanh |
| `[MÃ SỐ THUẾ]` | Điều khoản, Chính sách bảo mật, Thông tin pháp lý; Legal.jsx | |
| `[SỐ ĐĂNG KÝ KINH DOANH]` | Điều khoản, Thông tin pháp lý | Có thể trùng mã số thuế đối với doanh nghiệp |
| `[ĐỊA CHỈ]` | tất cả; Legal.jsx | Trụ sở |
| `[NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT]` | Thông tin pháp lý | |
| `[SỐ ĐIỆN THOẠI]` | Thông tin pháp lý | |
| `[EMAIL HỖ TRỢ]` | tất cả; Legal.jsx; mục Liên hệ trên trang giới thiệu | Cũng là đầu mối nhận thông báo vi phạm; đặt cùng giá trị cho `SUPPORT_EMAIL` trong `.env` |
| `[EMAIL BẢO VỆ DỮ LIỆU]` | Điều khoản, Chính sách bảo mật, Thông tin pháp lý | Có thể là cùng email hỗ trợ |
| `[TÊN MIỀN]` | Điều khoản, Chính sách bảo mật, Thông tin pháp lý; Legal.jsx | Ví dụ tên miền sản xuất |

## 2. Điều khoản do chủ sở hữu quyết định (chưa có giá trị mặc định)

| Giữ chỗ | Dùng ở |
|---|---|
| `[NGÀY CÓ HIỆU LỰC]` | Điều khoản dịch vụ, Mục 1 |
| `[SỐ NGÀY HOÀN TIỀN]` | Thanh toán và hoàn tiền |
| `[SỐ NGÀY XỬ LÝ HOÀN TIỀN]` | Thanh toán và hoàn tiền |
| `[SỐ NGÀY BÁO TRƯỚC KHI ĐỔI GIÁ]` | Điều khoản, Mục 11 |
| `[SỐ NGÀY BÁO TRƯỚC KHI ĐỔI ĐIỀU KHOẢN]` | Điều khoản, Mục 17 |
| `[SỐ NGÀY LƯU TRỮ SAU KHI GÓI HẾT HẠN]` | Điều khoản Mục 13, Chính sách bảo mật Mục 5 |
| `[SỐ NGÀY XỬ LÝ YÊU CẦU VỀ DỮ LIỆU]` | Chính sách bảo mật, Mục 6 (kiểm tra thời hạn bắt buộc theo luật) |
| `[MỨC TRẦN TRÁCH NHIỆM]` | Điều khoản, Mục 15 |
| `[TÒA ÁN HOẶC TRUNG TÂM TRỌNG TÀI GIẢI QUYẾT TRANH CHẤP]` | Điều khoản, Mục 18 |

## 3. Thanh toán và hoàn tiền (trong văn bản, ở trang `/refunds`)

- `[GIÁ ĐÃ BAO GỒM VAT HAY CHƯA]`
- `[CHÍNH SÁCH XUẤT HÓA ĐƠN ĐIỆN TỬ VÀ THÔNG TIN CẦN CUNG CẤP]`
- `[ĐIỀU KIỆN HOÀN TIỀN GÓI THÁNG]`
- `[QUY ĐỊNH HOÀN TIỀN GÓI THÁNG, VÍ DỤ CHƯA DÙNG CREDIT NÀO HAY HOÀN THEO TỶ LỆ]`
- `[QUY ĐỊNH HOÀN TIỀN CREDIT NẠP THÊM, VÍ DỤ CHỈ KHI CHƯA DÙNG]`
- `[QUY ĐỊNH VỀ CREDIT ĐÃ DÙNG]`
- `[QUY ĐỊNH VỀ TRƯỜNG HỢP VI PHẠM]`
- `[CÁCH HOÀN TIỀN QUA PAYOS VÀ THỜI GIAN]`
- `[QUY ĐỊNH THU HỒI CREDIT KHI HOÀN TIỀN]`

## 4. Nhà cung cấp hạ tầng

| Giữ chỗ | Dùng ở |
|---|---|
| `[TÊN NHÀ CUNG CẤP MÁY CHỦ]` | Chính sách bảo mật Mục 4; `subprocessors.md` |
| `[TÊN NHÀ CUNG CẤP LƯU TRỮ S3/R2]` | Chính sách bảo mật Mục 4; `subprocessors.md`. Bucket lưu clip theo gói là `ARCHIVE_*` (`studio/archive.py`), bucket sao lưu là `BACKUP_DEST` (`ops/backup_studio.sh`) |
| `[TÊN NHÀ CUNG CẤP EMAIL SMTP]` | Chính sách bảo mật Mục 4; `subprocessors.md`. Mã gửi email đã có (`studio/mailer.py`, `studio/lifecycle.py`, cấu hình `SMTP_*`); điền đúng nhà cung cấp SMTP bạn dùng |

## 5. Thời hạn lưu trữ (trong văn bản, ở Chính sách bảo mật Mục 5)

- `[THỜI HẠN LƯU NHẬT KÝ]`
- `[THỜI HẠN LƯU BẢN SAO LƯU]`
- `[THỜI HẠN LƯU DỮ LIỆU PHÂN TÍCH]`

Thêm vào `docs/dsa-notice-and-action.md`: `[SỐ NĂM LƯU TRỮ HỒ SƠ XỬ LÝ THÔNG BÁO]`.
Trong `docs/upload-post-dmca-section.md`: chỉ dùng nếu quyết định đăng khối DMCA.

## 6. Việc cần kiểm tra trước khi công bố (không phải giữ chỗ)

Những câu dưới đây đang được viết trong chính sách như một cam kết. Phải đúng
trước khi mở bán, hoặc phải sửa câu đó:

1. **"Chúng tôi dùng dự án Gemini trả phí, không dùng dữ liệu để huấn luyện."**
   Xác nhận khoá `GEMINI_API_KEY` thuộc dự án có bật thanh toán.
2. **Thời hạn lưu clip theo gói.** Đã có mã: `studio/archive.py` chép clip vào bucket
   `ARCHIVE_*` theo `Plan.retention_days` (gói trả phí) và xoá khi hết hạn
   (`purge_expired`). Nhưng **chỉ đúng khi `ARCHIVE_BUCKET` đã được đặt**; để trống thì
   mọi gói chỉ còn khoảng 1 ngày. Đặt bucket, thử một dự án qua cả vòng lưu, khôi phục,
   hết hạn, rồi mới giữ các con số 14 và 60 ngày trên trang giá và trong chính sách.
3. **Xoá tài khoản.** Chưa huỷ đăng ký Stripe (xem `data-retention.md` mục 4); chính
   sách đã nhắc người dùng tự huỷ gia hạn trước.
4. **Bản khai quyền nội dung.** Xác nhận nó được lưu bền vững ở đâu trong chế độ
   `studio/` (hiện `app.py` chỉ ghi nhận khi nhận tác vụ).
5. **Email.** Mã gửi email đã có (xác minh email, quên mật khẩu, biên nhận, nhắc hết
   credit, báo gia hạn). Chỉ chạy khi đã đặt `SMTP_HOST`; gửi thử các loại thư tới
   hộp thư thật (kiểm tra không rơi vào spam) và xác nhận các câu trong chính sách về
   email khớp với thư thực sự được gửi.
6. **Đồng ý đo lường (cookie).** Chính sách và biểu ngữ nói đo lường lượng truy cập chỉ
   chạy khi bạn đồng ý. Kiểm tra `dashboard/src/lib/consent.js` thực sự làm vậy (khi viết
   tài liệu này, `getConsent()` luôn trả `analytics: true`, `setConsent` bỏ qua lựa chọn
   về đo lường, và biểu ngữ chỉ hiện cho khách ở châu Âu, nên khách ở Việt Nam không thấy
   biểu ngữ). Nếu không sửa mã thì phải sửa câu. Để trống `VITE_OPENPANEL_*` lúc build thì
   không có gì được đo và mọi điều trên đúng.
7. **Chuyển dữ liệu ra nước ngoài** (Google, fal.ai, ElevenLabs, Stripe) và vị trí
   đặt máy chủ: làm thủ tục theo luật Việt Nam.
8. **Stripe nhận thanh toán thật** cho doanh nghiệp tại Việt Nam, và PayOS sandbox
   (xem `docs/payments.md`).
9. **Sao lưu.** `ops/backup_studio.sh` đã có; cần cài, chạy thử một lần khôi phục và đặt
   `RETENTION_DAYS` khớp với thời hạn nói trong chính sách (`ops/README.md`).
10. **Các tham chiếu luật** (Luật BVDLCN 91/2025/QH15, Nghị định 356/2025/NĐ-CP,
    Luật TMĐT 122/2025/QH15, Luật Bảo vệ quyền lợi người tiêu dùng 2023): luật sư
    xác nhận còn hiệu lực, có thêm nghĩa vụ đăng ký/thông báo nào không, và có
    thời hạn trả lời yêu cầu của chủ thể dữ liệu bắt buộc là bao lâu.

## 7. Việc chủ sở hữu phải tự làm, tóm tắt

Không thể làm từ kho mã:

- Điền mọi giữ chỗ ở mục 1 đến 5 (trong `dashboard/seo/site.js` và `.env`).
- Quyết định các con số hoàn tiền, trần trách nhiệm, tòa án/trọng tài, ngày có hiệu lực.
- Chọn và đăng ký: tên miền, VPS, nhà cung cấp SMTP, bucket S3/R2, Stripe, PayOS.
- Nhờ luật sư rà soát toàn bộ rồi mới đặt `DRAFT_NOTICE = ''`.
- Chạy một giao dịch thử Stripe và PayOS; thử khôi phục bản sao lưu.

## 8. Chương trình giới thiệu bạn bè (bản nháp, `/referral-terms`)

- `REFERRAL_MAX` trong `dashboard/seo/site.js` phải khớp biến môi trường `REFERRAL_MAX_REWARDS` của máy chủ
  (mặc định kỹ thuật 50 lượt thưởng cho mỗi người giới thiệu). Mức thưởng `REFERRAL_REWARD_CREDITS` (mặc định 20,
  đặt 0 để tắt chương trình) là quyết định của chủ sở hữu, không phải con số đã chốt.
- Điền `[QUY ĐỊNH THU HỒI THƯỞNG KHI HOÀN TIỀN]` trong `seo/legal.js`. Mã nguồn chưa tự thu hồi thưởng khi khoản
  thanh toán đầu bị hoàn tiền; việc này đang làm tay.
