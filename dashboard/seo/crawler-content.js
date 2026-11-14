/* Nội dung chữ cho trình thu thập không chạy JavaScript (nhiều bot AI và công cụ xem
 * trước liên kết). Được chèn vào <noscript> bên trong #root của index.html lúc build;
 * trình duyệt có JS thì React dựng lại #root nên người dùng không bao giờ thấy khối này.
 *
 * Chỉ nêu những điều đúng và không đổi theo cấu hình: giá và hạn mức thật do máy chủ trả
 * về ở trang bảng giá (studio/plans.py), nên ở đây không in con số nào để tránh lệch. */

import { BRAND } from './site.js'

export const CRAWLER_CONTENT = `
<h1>${BRAND}: tự động cắt video dài thành short viral</h1>
<p>${BRAND} biến một video dài thành các clip dọc 9:16 sẵn sàng đăng lên TikTok, Instagram
Reels và YouTube Shorts. Bạn tải lên một tệp MP4 hoặc MOV, hoặc dán liên kết video; hệ
thống phiên âm lời thoại, chọn những khoảnh khắc có tiềm năng nhất, cắt sang khung dọc và
chấm điểm viral kèm lý do cho từng clip.</p>
<h2>Tính năng</h2>
<ul>
<li>Cắt clip dọc 9:16 tự động, bám theo người đang nói.</li>
<li>Điểm viral giải thích được: xem từng thành phần của điểm rồi tự quyết định đăng clip nào.</li>
<li>Phụ đề tự động nhiều kiểu, tạo hook mở đầu và ảnh thu nhỏ.</li>
<li>Lồng tiếng AI sang nhiều ngôn ngữ, giữ giọng người nói (gói trả phí).</li>
<li>Đăng và lên lịch cả tuần lên các mạng xã hội bạn kết nối (gói trả phí).</li>
</ul>
<h2>Cách hoạt động</h2>
<ol>
<li>Dán link video (YouTube, Vimeo, TikTok và nhiều trang khác) hoặc tải một tệp lên.</li>
<li>Hệ thống chọn khoảnh khắc đáng xem, đổi sang khung dọc, thêm phụ đề và hook, rồi chấm điểm từng clip.</li>
<li>Xem các clip theo điểm, sửa nhanh rồi tải về hoặc đăng.</li>
</ol>
<h2>Giá</h2>
<p>Bắt đầu miễn phí với một số credit mỗi tháng, không cần thẻ. Gói trả phí theo tháng có
thêm credit, lưu clip lâu hơn và nhiều tính năng hơn; hết credit có thể nạp thêm, credit nạp
thêm không hết hạn. Thanh toán bằng thẻ quốc tế qua Stripe hoặc VietQR qua PayOS. Xem
<a href="/#/pricing">bảng giá</a>.</p>
<h2>Câu hỏi thường gặp</h2>
<dl>
<dt>Credit là gì?</dt>
<dd>Credit là đơn vị trả phí duy nhất. Tạo clip tốn 1 credit cho mỗi phút video nguồn; các thao tác khác có giá riêng ở trang bảng giá.</dd>
<dt>Điểm viral có đảm bảo lượt xem không?</dt>
<dd>Không. Điểm là dự đoán dựa trên các tín hiệu đo được từ lời nói và âm thanh, kèm lý do để bạn tự cân nhắc.</dd>
<dt>Tôi có thể huỷ gói bất cứ lúc nào không?</dt>
<dd>Có với gói trả bằng thẻ: huỷ trong trang Tài khoản và dùng đến hết kỳ đã trả. Thanh toán QR là trả trước một kỳ, không tự gia hạn.</dd>
</dl>
<h2>Thông tin</h2>
<ul>
<li><a href="/terms">Điều khoản dịch vụ</a></li>
<li><a href="/privacy">Chính sách bảo mật</a></li>
<li><a href="/refunds">Thanh toán và hoàn tiền</a></li>
<li><a href="/legal-notice">Thông tin pháp lý và liên hệ</a></li>
<li><a href="/report-content">Báo cáo nội dung vi phạm</a></li>
</ul>
`
