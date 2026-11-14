# Quy trình nội bộ: tiếp nhận và xử lý thông báo vi phạm

> **Đây không phải tư vấn pháp lý.** Bản này là bản nháp kỹ thuật và cần được
> người có chuyên môn pháp lý tại Việt Nam rà soát trước khi mở bán.

Tên tệp `dsa-notice-and-action.md` được giữ nguyên để không làm gãy liên kết,
nhưng nội dung đã viết lại cho ViralShorts theo pháp luật Việt Nam. Quy định DSA
của Liên minh châu Âu (Quy định (EU) 2022/2065) **chỉ áp dụng nếu bạn chủ động
phục vụ người dùng ở EU**; nếu dịch vụ nhắm tới người dùng Việt Nam thì không.
❓ Luật sư xác nhận.

Phần công khai của quy trình nằm ở trang `/report-content`
(`dashboard/seo/legal.js`). Tài liệu này là phần bên trong mà người ngoài không
thấy: thời hạn, mẫu thư và quy tắc với người vi phạm lặp lại. Công bố một cơ chế
mà ta không vận hành còn tệ hơn không công bố gì, vì khi đó trang đó là bằng
chứng ta biết điều pháp luật yêu cầu.

## Khung pháp lý tham chiếu (cần luật sư xác nhận)

- Quyền sở hữu trí tuệ: Luật Sở hữu trí tuệ và các văn bản hướng dẫn. Chủ sở
  hữu quyền có thể gửi thông báo yêu cầu gỡ; cơ quan có thẩm quyền có thể có yêu
  cầu chính thức.
- Nội dung bị cấm trên không gian mạng: Luật An ninh mạng và các nghị định về quản
  lý, cung cấp, sử dụng dịch vụ internet và thông tin trên mạng. ❓ Xác định ngưỡng
  nghĩa vụ của một dịch vụ lưu trữ nội dung do người dùng gửi (có phải đăng ký
  hay thông báo với Bộ Khoa học và Công nghệ / Bộ Công an không).
- Thương mại điện tử: Luật Thương mại điện tử 2025 (Luật số 122/2025/QH15, hiệu
  lực 1/7/2026) có thể áp đặt nghĩa vụ riêng với nền tảng thương mại điện tử. ❓ Xác
  định ViralShorts có thuộc diện đó không và cần đăng ký/thông báo gì.
- Bảo vệ dữ liệu cá nhân: Luật số 91/2025/QH15 áp dụng cho dữ liệu (hình ảnh, giọng
  nói) trong video bị khiếu nại; xem `docs/compliance/`.
- Nếu muốn có lá chắn bảo vệ của Mỹ (DMCA 512) cho chủ sở hữu quyền ở Mỹ: xem
  `docs/upload-post-dmca-section.md`. Mặc định không bắt buộc.

## Thời gian xử lý

1. **Xác nhận đã nhận** không chậm trễ, **trong cùng ngày làm việc**. Đây là bước
   dễ bị bỏ sót nhất vì nó phải xảy ra trước khi ai đó đưa ra quyết định.
2. **Ra quyết định** một cách cẩn trọng, khách quan, không tuỳ tiện. Mục tiêu: 72
   giờ; sớm hơn với bất kỳ nội dung nào liên quan tới trẻ em, luôn được xử lý
   trước.
3. **Báo cho người gửi thông báo** quyết định và lý do, kèm các cách khiếu nại
   tiếp theo.
4. **Báo cho người dùng bị ảnh hưởng**, kèm bản nêu lý do dưới đây.

Một thông báo có đủ các yếu tố mà trang công khai yêu cầu khiến ta **biết rõ** về
nội dung. Từ lúc đó, việc ta có thể viện dẫn vai trò chỉ lưu trữ để tránh trách
nhiệm với nội dung cụ thể ấy suy yếu, nên đồng hồ ở trên không phải phép lịch sự.

## Mẫu thư

**Xác nhận đã nhận** (ngay lập tức, gửi cho người gửi thông báo)

> Chúng tôi đã nhận báo cáo của bạn vào ngày <ngày>, mã tham chiếu <mã>. Chúng tôi
> sẽ xem xét và trả lời bạn bằng quyết định cùng lý do. Nếu cần thêm thông tin để
> xác định nội dung, chúng tôi sẽ hỏi bạn.

**Quyết định, gửi cho người gửi thông báo**

> Về báo cáo <mã> ngày <ngày>: chúng tôi đã <gỡ nội dung / vô hiệu hoá truy cập
> vào nó / quyết định không hành động>. <Một đoạn nêu lý do.> Nếu bạn không đồng
> ý, bạn có thể khiếu nại tới cơ quan nhà nước có thẩm quyền hoặc khởi kiện tại
> Toà án.

**Bản nêu lý do, gửi cho người dùng bị ảnh hưởng** (giữ đủ mọi dòng, kể cả khi có
dòng rất ngắn)

> - Chúng tôi đã làm gì: <gỡ / vô hiệu hoá truy cập / hạn chế tài khoản>, và với
>   nội dung nào, xác định chính xác.
> - Các sự kiện đã dựa vào: <thông báo nói gì, chúng tôi tự kiểm tra gì>.
> - Căn cứ: <quy định pháp luật bị vi phạm, hoặc điều khoản trong Điều khoản dịch
>   vụ của chúng tôi>.
> - Phương tiện tự động: không. Một người đã xem xét việc này. <Chỉ đổi khi điều
>   đó không còn đúng.>
> - Phạm vi: <toàn cầu / chỉ Việt Nam>.
> - Cách phản đối: hãy trả lời thư này hoặc viết tới [EMAIL HỖ TRỢ]. Một người sẽ
>   xem xét. Bạn cũng có thể khiếu nại tới cơ quan nhà nước có thẩm quyền hoặc khởi
>   kiện tại Toà án.

## Người vi phạm lặp lại

Các trang công khai nói rằng người vi phạm lặp lại bị chấm dứt tài khoản; đây là
ý nghĩa cụ thể của điều đó, vì một quy tắc không viết ra thì không chứng minh
được là đã được áp dụng một cách hợp lý.

- Một thông báo có cơ sở đối với một người dùng là một **cảnh cáo (strike)**.
  Thông báo bị ta bác bỏ không tính.
- Strike 1 và 2: gỡ nội dung, báo người dùng, ghi strike kèm mã thông báo và ngày.
- **Strike 3: chấm dứt tài khoản** và chặn đăng ký lại, như Điều khoản dịch vụ
  Mục 8 cho phép.
- Strike hết hiệu lực sau 12 tháng. (Các số này là giá trị mẫu, chủ sở hữu có thể
  đổi.)
- Trường hợp quá rõ ràng (nội dung xâm hại tình dục trẻ em, lệnh của toà án hoặc
  cơ quan có thẩm quyền, sao chép nguyên cả phim thương mại) bỏ qua việc đếm và
  chấm dứt ngay.

Ghi strike ở nơi tồn tại sau khi triển khai lại, không phải trong hộp thư của một
người nào đó.

## Người gửi thông báo ác ý

Người liên tục gửi thông báo hiển nhiên không có cơ sở được **cảnh báo bằng văn
bản nêu rõ hành vi**, rồi mới bị tạm ngừng xử lý thông báo của họ trong một thời
gian hợp lý. Luôn cảnh báo trước, và quy luật phải nhiều hơn hai lần nhầm lẫn.

## Lưu trữ

Thông báo, quyết định và strike được giữ [SỐ NĂM LƯU TRỮ HỒ SƠ XỬ LÝ THÔNG BÁO]
năm, khớp với thời hạn giữ bản khai quyền nội dung trong chính sách bảo mật. Chúng
là bằng chứng ta đã hành động cẩn trọng; bằng chứng không ai giữ thì coi như
không có.
