# Bên xử lý phụ (subprocessors) của ViralShorts

> **Đây không phải tư vấn pháp lý.** Bản này là bản nháp kỹ thuật và cần được
> người có chuyên môn pháp lý tại Việt Nam rà soát trước khi mở bán.

**Bên kiểm soát dữ liệu:** [TÊN PHÁP NHÂN] · MST [MÃ SỐ THUẾ] · [ĐỊA CHỈ] ·
[EMAIL HỖ TRỢ] · [EMAIL BẢO VỆ DỮ LIỆU]
**Phiên bản:** 2026-11-12 (bản nháp đầu tiên cho ViralShorts)

Danh sách các bên thứ ba xử lý dữ liệu cá nhân thay mặt [TÊN PHÁP NHÂN] khi vận
hành ViralShorts: mỗi bên nhận gì, ở đâu, và biện pháp bảo đảm khi dữ liệu ra
khỏi Việt Nam. Đây là phiên bản tham chiếu của Mục 4 trong trang Chính sách bảo
mật (`dashboard/seo/legal.js`). Nếu thêm hoặc bỏ một nhà cung cấp, sửa tài liệu
này và trang chính sách trong cùng một lần thay đổi.

Ký hiệu **❓ cần xác minh** nghĩa là điều đó chưa được kiểm tra từ kho mã. Đừng
khẳng định nó với người dùng cho đến khi đã kiểm tra.

Căn cứ pháp lý tham chiếu (cần luật sư xác nhận phiên bản và điều khoản còn hiệu
lực): Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 (hiệu lực từ 1/1/2026) và
Nghị định 356/2025/NĐ-CP hướng dẫn thi hành (thay thế Nghị định 13/2023/NĐ-CP).
Dữ liệu chuyển ra nước ngoài thường kéo theo nghĩa vụ lập hồ sơ đánh giá tác
động chuyển dữ liệu và gửi cơ quan chuyên trách: ❓ xác nhận thủ tục hiện hành.

---

## 1. Xử lý video và AI

| Nhà cung cấp | Pháp nhân và nước | Nhận gì | Ghi chú / DPA |
|---|---|---|---|
| **Google Gemini API** | Google LLC (Hoa Kỳ) và các pháp nhân Google khác | Bản chép lời, khung hình lấy mẫu (có thể có khuôn mặt), ảnh tham chiếu cho ảnh thu nhỏ; trong một số bước kiểm tra bố cục có thể gồm cả tệp video nguồn | **Bắt buộc dùng khoá của một dự án có bật thanh toán (paid tier).** Điều khoản của gói miễn phí cho phép Google dùng dữ liệu để cải thiện mô hình, khi đó câu "không huấn luyện bằng nội dung của bạn" trong chính sách sẽ **sai**. ❓ Xác nhận `GEMINI_API_KEY` trên máy chủ thuộc dự án trả phí và lưu bằng chứng (ảnh chụp trang Billing). Xem điều khoản Gemini API "Paid Services" hiện hành. |
| **fal.ai** | Features & Labels, Inc. (Hoa Kỳ) | Ảnh nhân vật (có thể là ảnh người thật), âm thanh để khớp khẩu hình, video sinh ra. Mô hình: Flux, Kling, Hailuo | ❓ Đọc điều khoản và chính sách dữ liệu của fal.ai: có dùng dữ liệu để huấn luyện không, thời gian giữ đầu vào/đầu ra. ❓ Lưu thoả thuận xử lý dữ liệu nếu có. |
| **ElevenLabs** | ElevenLabs Inc. (Hoa Kỳ) | Âm thanh của clip khi lồng tiếng (giọng của người thật), văn bản cho giọng AI | ❓ Kiểm tra gói đang dùng có chặn việc dùng dữ liệu để huấn luyện không; ❓ lưu thoả thuận xử lý dữ liệu. Cảnh báo: nhân bản giọng nói cần có sự đồng ý của chủ giọng. |

## 2. Thanh toán

| Nhà cung cấp | Pháp nhân và nước | Nhận gì | Ghi chú |
|---|---|---|---|
| **Stripe** | Stripe Payments Europe Ltd. / Stripe, Inc. | Email, tên, dữ liệu thẻ (đi thẳng tới Stripe, không qua máy chủ của ta), lịch sử giao dịch | ❓ **Xác nhận với Stripe rằng một doanh nghiệp đặt tại Việt Nam được nhận thanh toán thật.** Mã hiện được thiết kế cho chế độ test (`docs/payments.md`). Stripe là bên kiểm soát độc lập với một số dữ liệu (chống gian lận, tuân thủ). |
| **PayOS** | ❓ xác minh pháp nhân vận hành PayOS và ngân hàng đối tác | Thông tin đơn hàng, số tiền, tham chiếu giao dịch; thông tin người chuyển tiền do ngân hàng/VietQR xử lý | Việt Nam. ❓ Mã PayOS viết theo tài liệu công khai và **chưa kiểm chứng trên sandbox thật** (`docs/payments.md`). ❓ Đọc điều khoản dành cho merchant, quy trình hoàn tiền. |

## 3. Email, đăng nhập, đăng bài

| Nhà cung cấp | Nhận gì | Ghi chú |
|---|---|---|
| **Nhà cung cấp email SMTP** `[TÊN NHÀ CUNG CẤP EMAIL SMTP]` | Địa chỉ email và nội dung thư dịch vụ (xác minh email, đặt lại mật khẩu, biên nhận, nhắc hết credit, báo gia hạn) | Mã gửi email có trong `studio/mailer.py` và `studio/lifecycle.py`, cấu hình bằng `SMTP_*`; không đặt `SMTP_HOST` thì không gửi gì. ❓ Điền nhà cung cấp thật, nước đặt máy chủ, DPA. |
| **Google (đăng nhập bằng Google)** | Phạm vi `openid email profile`: email, mã định danh Google, tên, ảnh đại diện | Chỉ bật khi đặt `GOOGLE_CLIENT_ID` và `GOOGLE_CLIENT_SECRET`. Bỏ dòng này khỏi chính sách nếu không bật. |
| **Upload-Post** | Nội dung clip và tiêu đề được đăng; giữ mã truy cập OAuth của các mạng xã hội | Trong chế độ `studio/` **không có khoá dùng chung**: người dùng tự nhập khoá Upload-Post của họ (để khoá của nhà vận hành không đăng bài lên mạng của người khác). Do đó người dùng ký thoả thuận với Upload-Post. ❓ Xác nhận cách này khớp với văn bản chính sách và Điều khoản Mục 10. Dịch vụ này **không** còn do cùng pháp nhân với nhà vận hành (khác bản gốc). |

## 4. Hạ tầng và lưu trữ

| Nhà cung cấp | Nhận gì | Ghi chú |
|---|---|---|
| **Nhà cung cấp lưu trữ S3/R2** `[TÊN NHÀ CUNG CẤP LƯU TRỮ S3/R2]` (AWS S3, Cloudflare R2 hoặc tương đương) | Clip đã lưu theo gói (`ARCHIVE_*`, `studio/archive.py`) và bản sao lưu mã hoá của cơ sở dữ liệu (`BACKUP_DEST`, `ops/backup_studio.sh`) | ❓ Xác định bucket, khu vực và nước đặt bucket; dùng hai bucket riêng, đều riêng tư. ❓ DPA. |
| **Nhà cung cấp máy chủ** `[TÊN NHÀ CUNG CẤP MÁY CHỦ]` | Toàn bộ dữ liệu trên máy chủ ứng dụng, cơ sở dữ liệu SQLite (`data/studio.db`) | ❓ Vị trí máy chủ (trong hay ngoài Việt Nam). Nếu dữ liệu người dùng Việt Nam nằm ở nước ngoài, ❓ kiểm tra yêu cầu lưu trữ dữ liệu trong nước và thủ tục chuyển dữ liệu xuyên biên giới. |
| **DNS / CDN** (nếu có, ví dụ Cloudflare) | IP và siêu dữ liệu yêu cầu của mọi khách truy cập | ❓ Điền nếu đang dùng; bỏ nếu không. |
| **OpenPanel** (nếu bật) | Sự kiện sử dụng với mã định danh ngẫu nhiên của tài khoản; **không có email** | Chỉ bật khi đặt `VITE_OPENPANEL_*` lúc build; chính sách nói chỉ chạy khi người dùng đồng ý trong biểu ngữ (kiểm tra mã khớp, xem `placeholders.md` mục 6). ❓ Xác nhận bạn tự lưu trữ (self-host) hay dùng dịch vụ đám mây của họ. |
| **Proxy tải video** (nếu có) | URL video và dữ liệu video; không có dữ liệu tài khoản | ❓ Mã (`main.py`) hỗ trợ biến `PROXY_URL`. Điền nhà cung cấp và nước nếu dùng; bỏ nếu không. |

## 5. Việc phải làm trước khi mở bán

Không việc nào làm được từ kho mã; thuộc về chủ sở hữu dịch vụ:

1. **Xác nhận khoá Gemini thuộc dự án trả phí** và giữ bằng chứng. Nếu không,
   sửa câu cam kết không huấn luyện trong Điều khoản (Mục 7) và Chính sách bảo
   mật (Mục 2).
2. **Đọc và lưu** điều khoản xử lý dữ liệu của fal.ai, ElevenLabs, Stripe, PayOS,
   nhà cung cấp lưu trữ và máy chủ. Lưu bản có ngày.
3. **Hoàn thành thủ tục chuyển dữ liệu cá nhân ra nước ngoài** theo luật Việt Nam
   nếu có nhà cung cấp ở nước ngoài (Google, fal.ai, ElevenLabs, Stripe...).
4. **Quyết định và điền** tên nhà cung cấp email, lưu trữ và máy chủ vào
   `dashboard/seo/site.js` và bảng trên.
5. **Chạy một giao dịch sandbox PayOS và một giao dịch test Stripe** trước khi
   tin vào luồng thanh toán.
6. **Thông báo cho người dùng** khi thêm bên xử lý phụ mới có thể ảnh hưởng đến
   họ (cập nhật chính sách và thông báo trong ứng dụng).

## Nhật ký thay đổi

| Ngày | Thay đổi |
|---|---|
| 2026-11-12 | Viết lại hoàn toàn cho ViralShorts bằng tiếng Việt. Bỏ các nhà cung cấp riêng của tác giả gốc (hệ thống hoá đơn riêng, Telegram, nhà cung cấp email, máy chủ và proxy cụ thể); thêm PayOS; Upload-Post chuyển thành dịch vụ do người dùng tự kết nối. |
