/* Trang pháp lý của ViralShorts (tiếng Việt): Điều khoản dịch vụ, Chính sách
 * bảo mật, Thông tin pháp lý, Báo cáo nội dung vi phạm, và Chính sách thanh
 * toán & hoàn tiền.
 *
 * Các trang được phát ra dưới dạng HTML tĩnh khi build (vite-plugin-seo.js),
 * có mặt trong sitemap.xml và llms.txt; người dùng tìm chúng ở chân trang.
 *
 * ĐÂY KHÔNG PHẢI TƯ VẤN PHÁP LÝ. Toàn bộ văn bản là bản nháp kỹ thuật, cần
 * được người có chuyên môn pháp lý tại Việt Nam rà soát trước khi mở bán.
 *
 * CÁCH ĐIỀN: mọi thông tin của pháp nhân và mọi điều khoản do chủ sở hữu tự
 * quyết định được gom thành hằng số trong seo/site.js, dưới dạng giữ chỗ trong
 * ngoặc vuông. Điền giá trị thật vào đúng chỗ đó là đủ. Danh sách đầy đủ các
 * giữ chỗ nằm ở docs/compliance/placeholders.md. Khi đã rà soát xong, đặt
 * DRAFT_NOTICE = '' để bỏ ghi chú nháp ở đầu mỗi trang.
 *
 * Các trang giữ nguyên đường dẫn /terms, /privacy, /legal-notice,
 * /report-content, /refunds vì LoginModal và chân trang đang liên kết tới đó.
 */

import {
  PUBLISHED, BRAND, ENTITY, TAX_ID, REG_NO, ADDRESS, SUPPORT_EMAIL, PRIVACY_EMAIL, PHONE, DOMAIN, REPRESENTATIVE, REFUND_DAYS, REFUND_PROCESS_DAYS, PRICE_NOTICE_DAYS, TERMS_NOTICE_DAYS, GRACE_DAYS, REQUEST_DAYS, LIABILITY_CAP, DISPUTE_FORUM, EFFECTIVE_DATE, REFERRAL_MAX, HOST_PROVIDER, STORAGE_PROVIDER, SMTP_PROVIDER,
} from './site.js'

// Mọi hằng số (thông tin pháp nhân, điều khoản do chủ sở hữu quyết định, nhà cung cấp
// hạ tầng) nằm ở seo/site.js, nguồn duy nhất cho cả trang tĩnh này và src/Legal.jsx.

// Ghi chú nháp hiển thị ở đầu mỗi trang. Đặt '' sau khi đã được rà soát pháp lý.
const DRAFT_NOTICE = `<p><strong>Lưu ý quan trọng (bản nháp):</strong> văn bản này
chưa phải tư vấn pháp lý và chưa được người có chuyên môn pháp lý rà soát. Các
nội dung trong ngoặc vuông, ví dụ ${ENTITY} hoặc ${SUPPORT_EMAIL}, là chỗ giữ chỗ
cần được điền trước khi dịch vụ được mở bán. Chỉ nên công bố sau khi luật sư
hoặc cố vấn pháp lý tại Việt Nam đã xem xét.</p>`

const TERMS_VI = `
${DRAFT_NOTICE}

<h2>1. Chúng tôi là ai</h2>
<p>${BRAND} (${DOMAIN}) là dịch vụ trực tuyến do ${ENTITY} vận hành, mã số thuế
${TAX_ID}, đăng ký kinh doanh số ${REG_NO}, trụ sở tại ${ADDRESS} (sau đây gọi
là "${BRAND}", "chúng tôi"). Bạn có thể liên hệ với chúng tôi qua
${SUPPORT_EMAIL}. Điều khoản dịch vụ này ("Điều khoản") điều chỉnh việc bạn sử
dụng dịch vụ được lưu trữ tại ${DOMAIN}. Điều khoản có hiệu lực từ
${EFFECTIVE_DATE}.</p>

<h2>2. Dịch vụ</h2>
<p>${BRAND} biến video dài thành các clip dọc ngắn. Theo chỉ dẫn của bạn, dịch
vụ tiếp nhận video bạn tải lên hoặc video ở một đường dẫn (URL) bạn cung cấp,
chuyển lời thoại thành văn bản, dùng mô hình AI để chọn các khoảnh khắc, cắt
sang khung dọc, và tuỳ chọn thêm phụ đề, chữ chèn, lồng tiếng AI, ảnh thu nhỏ,
video AI, cũng như đăng kết quả lên các tài khoản mạng xã hội bạn kết nối.
Dịch vụ có gói miễn phí với hạn mức, các gói trả phí theo tháng và credit nạp
thêm. Chi tiết về giá, hạn mức và tính năng của từng gói được hiển thị trên
trang bảng giá.</p>

<h2>3. Điều kiện sử dụng và tài khoản</h2>
<p>Bạn phải từ đủ 16 tuổi. Nếu bạn dưới 18 tuổi, bạn chỉ được mua gói trả phí
hoặc nạp credit khi có sự đồng ý của cha mẹ hoặc người giám hộ hợp pháp. Bạn
chịu trách nhiệm về mọi hoạt động diễn ra qua tài khoản và khoá API của mình.
Hãy giữ bí mật thông tin đăng nhập và báo ngay cho chúng tôi qua
${SUPPORT_EMAIL} nếu bạn nghi ngờ tài khoản bị xâm nhập.</p>

<h2>4. Nội dung của bạn vẫn là của bạn</h2>
<p>Bạn giữ toàn bộ quyền sở hữu đối với các video bạn gửi lên. Khi gửi nội dung,
bạn cấp cho chúng tôi giấy phép không độc quyền, miễn phí bản quyền, có hiệu
lực trên toàn cầu để lưu trữ, sao chép, chuyển mã, chỉnh sửa và xử lý nội dung
đó, cũng như hiển thị lại cho bạn, chỉ trong phạm vi cần thiết để vận hành và
bảo vệ dịch vụ. Giấy phép này chấm dứt khi nội dung bị xoá khỏi hệ thống của
chúng tôi theo quy tắc lưu trữ ở Mục 13, trừ bản sao lưu được giữ trong thời
gian giới hạn và nội dung chúng tôi buộc phải giữ theo quy định của pháp
luật.</p>
<p><strong>Các clip là của bạn.</strong> Giữa bạn và chúng tôi, bạn sở hữu các
clip đầu ra mà dịch vụ tạo từ nội dung của bạn, kể cả để dùng cho mục đích
thương mại, trong phạm vi chúng tôi có quyền đối với chúng. Nếu gói của bạn
gắn watermark lên clip, bạn không được gỡ hoặc che watermark đó bằng cách nào
khác ngoài việc nâng cấp lên gói không có watermark.</p>
<p>Chúng tôi không dùng nội dung của bạn để huấn luyện mô hình AI, của chúng tôi
hay của bất kỳ ai. Xem Mục 7.</p>
<p>Chỉ khi có sự cho phép riêng của bạn, chúng tôi mới nêu tên bạn hoặc giới
thiệu clip công khai của bạn làm ví dụ khách hàng. Chúng tôi không bao giờ làm
việc này theo mặc định.</p>

<h2>5. Cam kết của bạn về nội dung</h2>
<p>Dịch vụ xử lý nội dung theo chỉ dẫn của bạn, gồm cả tệp bạn tải lên và video
bạn yêu cầu chúng tôi lấy từ một URL. Với mỗi video bạn gửi, bằng bất kỳ cách
nào, bạn cam kết rằng:</p>
<ul>
<li>bạn là chủ sở hữu, hoặc có quyền hay sự cho phép cần thiết để tải xuống, xử
lý, chỉnh sửa và đăng lại video đó;</li>
<li>việc bạn dùng video đó qua dịch vụ không xâm phạm quyền tác giả, quyền liên
quan, nhãn hiệu, quyền về hình ảnh hay quyền riêng tư của bất kỳ ai, và không
vi phạm điều khoản của nền tảng nơi video xuất phát;</li>
<li>video không chứa hình ảnh hoặc giọng nói của người có thể nhận diện được nếu
chưa có sự đồng ý mà pháp luật yêu cầu; và</li>
<li>nếu dùng lồng tiếng AI hoặc video AI, bạn có sự đồng ý của chủ giọng nói hoặc
người trong ảnh để tạo giọng nói hay hình ảnh tổng hợp từ họ.</li>
</ul>
<p>Mỗi lần tạo tác vụ, bạn tích vào một bản khai xác nhận điều này. Chúng tôi lưu
bản khai cùng thời điểm, địa chỉ IP và định danh trình duyệt của bạn, và có thể
xuất trình bản ghi này khi có tranh chấp. Gửi nội dung của người khác khi chưa
được phép là lý do dễ dẫn đến việc tài khoản bị chấm dứt nhất theo Mục 16.</p>

<h2>6. Dữ liệu cá nhân trong video của bạn: vai trò xử lý dữ liệu</h2>
<p>Video thường chứa dữ liệu cá nhân của những người xuất hiện trong đó (hình
ảnh, giọng nói). Với dữ liệu đó, bạn là bên quyết định mục đích và phương tiện
xử lý (bên kiểm soát dữ liệu cá nhân) còn chúng tôi xử lý thay cho bạn, theo
chỉ dẫn của bạn (các tác vụ bạn gửi), theo cách hiểu của pháp luật Việt Nam về
bảo vệ dữ liệu cá nhân. Chúng tôi chỉ dùng các bên xử lý phụ được nêu trong
<a href="/privacy">Chính sách bảo mật</a>, áp dụng biện pháp bảo mật phù hợp và
xoá nội dung theo quy tắc ở Mục 13, hoặc sớm hơn nếu bạn yêu cầu. Bạn có trách
nhiệm bảo đảm đã có căn cứ hợp pháp, gồm sự đồng ý khi pháp luật yêu cầu, để
đưa dữ liệu cá nhân của người khác vào video bạn gửi. Nếu doanh nghiệp của bạn
cần một thoả thuận xử lý dữ liệu bằng văn bản, hãy gửi yêu cầu tới
${PRIVACY_EMAIL}.</p>
<p>Cần lưu ý rằng nội dung của bạn đi qua máy chủ của chúng tôi trước khi tới
nhà cung cấp AI, kể cả khi bạn tự có tài khoản với nhà cung cấp đó.</p>

<h2>7. Xử lý bằng AI: cái gì chạy ở đâu</h2>
<p>Dịch vụ dùng các hệ thống AI để làm việc và chúng tôi nêu tên chúng:
chuyển lời thoại thành văn bản chạy trên máy chủ của chúng tôi; chọn khoảnh
khắc, đặt tiêu đề, quyết định bố cục và tạo ảnh thu nhỏ dùng Gemini API của
Google; lồng tiếng và giọng AI tuỳ chọn dùng ElevenLabs; video AI (ảnh nhân vật,
hoạt ảnh người dẫn) dùng fal.ai. Nội dung video, âm thanh, bản chép lời, khung
hình lấy mẫu và ảnh nhân vật bạn cung cấp chỉ được gửi tới các nhà cung cấp này
trong phạm vi cần để thực hiện tác vụ bạn yêu cầu. Chúng tôi chỉ dùng các tài
khoản API mà điều khoản của nhà cung cấp không cho phép dùng dữ liệu của khách
hàng để huấn luyện mô hình. <a href="/privacy">Chính sách bảo mật</a> nêu cụ thể
từng bên nhận những gì.</p>
<p><strong>Chúng tôi không huấn luyện mô hình AI bằng nội dung của bạn, không bán
và không chia sẻ nó cho mục đích huấn luyện.</strong></p>
<p>Kết quả AI mang tính xác suất: lựa chọn clip, bản chép lời, bản dịch, tiêu đề
và giọng lồng tiếng có thể có sai sót, và những đầu vào giống nhau có thể cho
đầu ra giống nhau ở các khách hàng khác nhau, nên không bảo đảm là duy nhất.
Bạn có trách nhiệm xem lại kết quả AI trước khi dùng hoặc đăng. Bạn không được
dùng dịch vụ hoặc kết quả của nó để phát triển hay huấn luyện mô hình, dịch vụ
cạnh tranh.</p>
<p>Clip dùng lồng tiếng AI chứa giọng nói tổng hợp; video làm bằng nhân vật AI và
ảnh thu nhỏ do mô hình ảnh tạo cũng là nội dung tổng hợp. Chúng tôi đánh dấu các
tệp đó là do AI tạo ra ở dạng máy đọc được (thẻ siêu dữ liệu trên video, đánh
dấu XMP <code>DigitalSourceType: trainedAlgorithmicMedia</code> trên ảnh do AI
tạo). Bạn không được gỡ hay xoá dấu này. Lưu ý rằng các nền tảng thường mã hoá
lại video tải lên và việc đó có thể làm mất dấu. Chúng tôi không in nhãn nhìn
thấy được lên hình. Khi bạn đăng một clip như vậy, bạn có trách nhiệm cho khán
giả biết nội dung đó do AI tạo ra hoặc chỉnh sửa, và công cụ gắn nhãn nội dung
AI của từng nền tảng (TikTok, Instagram, YouTube và các nền tảng khác) là cách
thông thường để làm điều đó.</p>

<h2>8. Sử dụng được chấp nhận</h2>
<p>Bạn không được dùng dịch vụ để:</p>
<ul>
<li>xử lý hoặc phát tán nội dung trái pháp luật Việt Nam, phỉ báng, quấy rối, thù
hận, bóc lột tình dục trẻ em, kích động bạo lực, xâm phạm an ninh quốc gia,
trật tự an toàn xã hội hoặc thuộc các hành vi bị cấm khác theo quy định của
pháp luật;</li>
<li>xâm phạm quyền sở hữu trí tuệ, quyền về hình ảnh hay quyền riêng tư, kể cả gửi
URL của nội dung mà bạn không có quyền;</li>
<li>mạo danh bất kỳ ai, hoặc tạo nội dung có hình ảnh hay giọng nói của một người
có thể nhận diện được khi chưa có sự đồng ý (deepfake);</li>
<li>dò quét, làm gián đoạn hoặc làm quá tải dịch vụ, thu thập dữ liệu tự động, hay
truy cập bằng phương tiện tự động nào khác ngoài API và điểm cuối MCP có tài
liệu, trong giới hạn tần suất của chúng;</li>
<li>dịch ngược dịch vụ được lưu trữ hoặc cố trích xuất mô hình, prompt hay các
thành phần không công khai;</li>
<li>bán, chuyển nhượng hoặc chia sẻ khoá API, tài khoản hay credit, hoặc tạo nhiều
tài khoản để lách giới hạn của gói miễn phí;</li>
<li>thao túng giả tạo các chỉ số tương tác trên bất kỳ nền tảng nào bạn đăng
lên.</li>
</ul>
<p>Mục này, cùng Mục 5 và Mục 9, là chính sách kiểm duyệt nội dung của chúng tôi.
Nội dung vi phạm có thể bị gỡ; tài khoản vi phạm có thể bị hạn chế, tạm ngưng
hoặc chấm dứt, kèm lý do gửi tới người dùng bị ảnh hưởng. Chúng tôi có thể chặn
đăng ký lại của cùng một người sau khi chấm dứt vì lạm dụng.</p>

<h2>9. Khiếu nại bản quyền và gỡ nội dung</h2>
<p>Quy trình đầy đủ, gồm thông báo cần chứa gì và cách phản đối việc gỡ, nằm ở
trang riêng: <a href="/report-content">Báo cáo nội dung vi phạm</a>.</p>
<p>Nếu bạn cho rằng nội dung được xử lý hoặc lưu trữ qua dịch vụ xâm phạm quyền
của bạn, hãy gửi email tới ${SUPPORT_EMAIL} (đầu mối tiếp nhận của người dùng và
cơ quan nhà nước có thẩm quyền) kèm: họ tên và thông tin liên hệ của bạn, tác
phẩm hoặc quyền bạn sở hữu, URL hoặc mã định danh chính xác của nội dung bị cho
là vi phạm, tuyên bố thiện chí rằng việc sử dụng đó chưa được phép, và chữ ký
của bạn. Chúng tôi xem xét thông báo kịp thời, gỡ hoặc vô hiệu hoá truy cập vào
nội dung khi thông báo có cơ sở, và thông báo cho người dùng bị ảnh hưởng kèm lý
do; người dùng đó có thể gửi phản đối có căn cứ. Chúng tôi chấm dứt tài khoản
của người vi phạm nhiều lần. Chúng tôi cũng sẽ thực hiện yêu cầu gỡ bỏ hợp lệ
của cơ quan nhà nước có thẩm quyền theo quy định của pháp luật Việt Nam.</p>

<h2>10. Đăng lên tài khoản mạng xã hội của bạn</h2>
<p>Nếu bạn kết nối tài khoản mạng xã hội (qua đối tác đăng bài Upload-Post), bạn
cho phép rõ ràng chúng tôi và đối tác đăng nội dung lên các tài khoản đó theo
chỉ dẫn của bạn. Bạn vẫn là người đăng mọi thứ được đăng: bạn chịu trách nhiệm
về nội dung, lịch đăng và việc tuân thủ điều khoản của từng nền tảng (YouTube,
TikTok, Instagram và các nền tảng khác). Bạn có thể ngắt kết nối bất kỳ lúc nào
từ bảng điều khiển hoặc từ phần cài đặt của chính nền tảng, việc này thu hồi
quyền truy cập của chúng tôi.</p>

<h2>11. Gói, credit và thanh toán</h2>
<p>Dịch vụ dùng đơn vị "credit". Credit được trừ khi bạn dùng các tính năng,
theo bảng quy đổi hiển thị trên trang bảng giá. Gói trả phí theo tháng cấp một
lượng credit mỗi kỳ; <strong>credit của gói hết hạn vào cuối kỳ thanh toán</strong>
và không được cộng dồn sang kỳ sau. Credit nạp thêm
<strong>không hết hạn</strong>. Khi trừ, credit sắp hết hạn được dùng trước,
rồi mới đến credit nạp thêm. Tác vụ thất bại hoặc bị huỷ không bị trừ credit.</p>
<p>Thanh toán được xử lý bởi Stripe (thẻ quốc tế) và PayOS (chuyển khoản
VietQR); chúng tôi không nhìn thấy hay lưu số thẻ của bạn. Gói thanh toán qua
Stripe là đăng ký định kỳ tự động gia hạn đến khi bạn huỷ. Gói thanh toán qua
PayOS là trả trước cho một kỳ 30 ngày và không tự động gia hạn: bạn mua lại để
tiếp tục. Việc huỷ gia hạn có hiệu lực vào cuối kỳ hiện tại, bạn vẫn dùng đầy đủ
phần đã trả. Chúng tôi sẽ báo trước ít nhất ${PRICE_NOTICE_DAYS} ngày qua email
hoặc trong ứng dụng trước khi tăng giá có hiệu lực.</p>
<p>Chi tiết về giá, thuế, hoá đơn, hoàn tiền và các trường hợp ngoại lệ nằm ở
<a href="/refunds">Chính sách thanh toán và hoàn tiền</a>, là một phần của các
Điều khoản này.</p>

<h2>12. Quyền của người tiêu dùng</h2>
<p>Nếu bạn là người tiêu dùng theo pháp luật Việt Nam, các Điều khoản này không
loại trừ hay hạn chế những quyền mà Luật Bảo vệ quyền lợi người tiêu dùng và các
văn bản hướng dẫn trao cho bạn và không thể từ bỏ, bao gồm quyền được cung cấp
thông tin đầy đủ, chính xác về dịch vụ, giá và điều kiện giao dịch, quyền được
bồi thường khi dịch vụ không đúng cam kết, và quyền khiếu nại. Điều kiện hoàn
tiền cụ thể của chúng tôi nằm ở <a href="/refunds">Chính sách thanh toán và hoàn
tiền</a>. Mọi khiếu nại xin gửi tới ${SUPPORT_EMAIL}.</p>

<h2>13. Lưu trữ và xoá nội dung</h2>
<p>Thời hạn lưu clip phụ thuộc vào gói của bạn và được ghi trên trang bảng giá.
Hết thời hạn đó, clip bị xoá vĩnh viễn; hãy tải xuống những gì bạn muốn giữ. Khi
gói trả phí hết hạn mà bạn không gia hạn, dự án và clip được giữ thêm
${GRACE_DAYS} ngày rồi bị xoá, trừ khi bạn xoá sớm hơn. Các tệp làm việc tạm
trên máy chủ xử lý được dọn dẹp tự động, trong vòng 24 giờ sau khi tác vụ kết
thúc. Khi bạn xoá tài khoản,
chúng tôi xoá nội dung của bạn theo cùng lịch, trừ các bản sao lưu ngắn hạn và
những bản ghi chúng tôi buộc phải giữ theo pháp luật (ví dụ dữ liệu hoá đơn, chứng
từ kế toán). Chúng tôi không chịu trách nhiệm về việc mất nội dung mà việc xoá đã
được các Điều khoản này thông báo trước.</p>

<h2>14. Miễn trừ</h2>
<p>Dịch vụ được cung cấp "nguyên trạng" và "theo khả năng sẵn có", không bảo đảm
hoạt động liên tục, không có lỗi hoặc phù hợp với một mục đích cụ thể, trong
phạm vi pháp luật nơi bạn cư trú cho phép các miễn trừ đó. Không có nội dung nào
trong các Điều khoản này giới hạn những bảo đảm hay quyền mà pháp luật bảo vệ
người tiêu dùng trao cho bạn và không thể từ bỏ.</p>

<h2>15. Trách nhiệm</h2>
<p>Trong phạm vi tối đa pháp luật cho phép, tổng trách nhiệm của chúng tôi đối
với các khiếu nại phát sinh từ dịch vụ bị giới hạn ở ${LIABILITY_CAP}, và chúng
tôi không chịu trách nhiệm về thiệt hại gián tiếp, hệ quả, mất lợi nhuận hay mất
dữ liệu mà việc xoá đã được thông báo ở Mục 13. Giới hạn này không áp dụng cho
thiệt hại do cố ý hoặc lỗi nghiêm trọng của chúng tôi, thiệt hại về tính mạng
hoặc sức khoẻ, hay trách nhiệm không thể bị giới hạn theo pháp luật Việt Nam.</p>

<h2>16. Bồi thường, tạm ngưng và chấm dứt</h2>
<p>Nếu bên thứ ba khiếu nại chúng tôi vì nội dung bạn gửi hoặc yêu cầu chúng tôi
lấy, hoặc vì bạn vi phạm các Điều khoản này, bạn sẽ bồi thường cho chúng tôi,
gồm cả giám đốc, nhân viên và nhà cung cấp của chúng tôi, các thiệt hại, khoản
phạt và chi phí bào chữa hợp lý phát sinh, trừ phần khiếu nại do chính chúng tôi
vi phạm. Nếu bạn là người tiêu dùng, nghĩa vụ này chỉ áp dụng cho các khiếu nại
do bạn vi phạm Điều khoản hoặc pháp luật gây ra.</p>
<p>Chúng tôi có thể tạm ngưng hoặc chấm dứt tài khoản khi có vi phạm nghiêm
trọng. Khi vi phạm có thể khắc phục, chúng tôi sẽ báo trước và cho bạn một thời
hạn hợp lý để sửa; khi không thể (nội dung trái pháp luật, vi phạm lặp lại, lạm
dụng, gian lận), chúng tôi có thể tạm ngưng ngay kèm lý do. Sau khi chấm dứt, bạn
có thêm thời gian ngắn để tải nội dung còn lại, trừ khi pháp luật buộc chúng tôi
phải gỡ. Các Mục 4 đến 9 và 14 đến 18 tiếp tục có hiệu lực sau khi chấm dứt.</p>

<h2>17. Thay đổi dịch vụ và Điều khoản</h2>
<p>Chúng tôi liên tục cải tiến dịch vụ và có thể thay đổi hoặc ngừng một số tính
năng. Chúng tôi có thể sửa các Điều khoản; thay đổi quan trọng sẽ được thông báo
qua email hoặc trong ứng dụng ít nhất ${TERMS_NOTICE_DAYS} ngày trước, và việc
bạn tiếp tục dùng dịch vụ sau thời điểm đó được coi là chấp nhận. Nếu không đồng
ý, bạn có thể ngừng dùng và huỷ trước khi điều khoản mới áp dụng; việc hoàn tiền
cho phần chưa dùng của kỳ đã trả trước thực hiện theo
<a href="/refunds">Chính sách thanh toán và hoàn tiền</a>.</p>

<h2>18. Luật áp dụng và giải quyết tranh chấp</h2>
<p>Các Điều khoản này được điều chỉnh bởi pháp luật Việt Nam. Tranh chấp được ưu
tiên giải quyết qua thương lượng; bạn hãy liên hệ ${SUPPORT_EMAIL} trước, phần
lớn vấn đề được xử lý trong vài ngày. Nếu không thương lượng được, tranh chấp
được giải quyết tại ${DISPUTE_FORUM}. Nếu bạn là người tiêu dùng, bạn vẫn giữ
các quyền khiếu nại tới cơ quan quản lý nhà nước, tổ chức bảo vệ người tiêu
dùng, hoà giải, trọng tài hoặc khởi kiện tại Toà án theo quy định của pháp luật
Việt Nam.</p>
`

const PRIVACY_VI = `
${DRAFT_NOTICE}

<h2>1. Ai chịu trách nhiệm về dữ liệu của bạn</h2>
<p>Bên kiểm soát dữ liệu cá nhân là ${ENTITY} (mã số thuế ${TAX_ID}), địa chỉ
${ADDRESS}, đơn vị vận hành ${BRAND} (${DOMAIN}). Mọi vấn đề về dữ liệu của bạn,
xin gửi tới ${PRIVACY_EMAIL}. Chính sách này được soạn theo Luật Bảo vệ dữ liệu
cá nhân (Luật số 91/2025/QH15) và các văn bản hướng dẫn thi hành đang có hiệu
lực.</p>

<h2>2. Chúng tôi xử lý gì, vì sao, và dựa trên căn cứ nào</h2>
<h3>Tài khoản của bạn</h3>
<p>Địa chỉ email, tên hiển thị, ngôn ngữ giao diện, ngày đăng ký, và mật khẩu
của bạn ở dạng băm một chiều (scrypt), không bao giờ ở dạng đọc được. Nếu bạn
đăng nhập bằng Google, chúng tôi nhận thêm mã định danh tài khoản Google và ảnh
đại diện. Căn cứ: sự đồng ý của bạn khi đăng ký và việc thực hiện hợp đồng dịch
vụ với bạn.</p>
<h3>Thanh toán</h3>
<p>Thanh toán chạy trên Stripe (thẻ quốc tế) và PayOS (chuyển khoản VietQR).
Chúng tôi lưu mã tham chiếu giao dịch hoặc khách hàng, gói, trạng thái đăng ký,
số credit và lịch sử cộng trừ credit; chúng tôi không lưu số thẻ của bạn. Dữ
liệu thanh toán và hoá đơn được giữ vì pháp luật về thuế và kế toán yêu cầu. Căn
cứ: thực hiện hợp đồng và nghĩa vụ pháp lý.</p>
<h3>Video bạn xử lý</h3>
<p>Video bạn tải lên hoặc yêu cầu chúng tôi lấy, bản chép lời và các clip tạo ra
từ chúng được xử lý để thực hiện đúng tác vụ bạn yêu cầu. Bộ nhận diện khuôn mặt
dùng để quyết định cắt khung chạy trên máy chủ của chúng tôi, chỉ để xác định vị
trí trong hình, không dùng để nhận dạng ai và không tạo mẫu sinh trắc học nào.
Căn cứ: thực hiện hợp đồng. Khi video chứa dữ liệu cá nhân của người khác (hình
ảnh, giọng nói), bạn là bên kiểm soát dữ liệu đó, chúng tôi là bên xử lý theo
chỉ dẫn của bạn; xem Mục 6 của <a href="/terms">Điều khoản dịch vụ</a>.</p>
<h3>Bản khai quyền nội dung</h3>
<p>Mỗi lần gửi tác vụ, bạn xác nhận mình có quyền với nội dung. Chúng tôi lưu bản
khai đó cùng ngày giờ, địa chỉ IP và định danh trình duyệt của bạn, làm bằng
chứng về sự cẩn trọng khi có tranh chấp bản quyền hoặc quyền hình ảnh. Căn cứ:
lợi ích hợp pháp trong việc xác lập và bảo vệ quyền, yêu cầu pháp lý.</p>
<h3>Email dịch vụ</h3>
<p>Chúng tôi gửi email xác nhận, biên nhận, nhắc gia hạn, thông báo clip sẵn sàng
và cảnh báo trước khi clip bị xoá, nếu dịch vụ email được cấu hình. Đây là một
phần của dịch vụ, không phải quảng cáo. Chúng tôi không gửi bản tin quảng cáo
cho bạn nếu chưa có sự đồng ý riêng của bạn, và không bán hay cho thuê địa chỉ
của bạn.</p>
<h3>Phân tích sử dụng sản phẩm</h3>
<p>Nếu được bật, chúng tôi đo cách ứng dụng được dùng bằng OpenPanel chạy trên máy
chủ do chúng tôi quản lý, với script phục vụ từ chính tên miền này.
<strong>Không có gì được tải cho đến khi bạn chấp nhận nhóm "đo lường lượng truy
cập" trong biểu ngữ cookie</strong>, và từ chối chỉ cần một cú nhấp; bạn có thể
đổi ý bất kỳ lúc nào qua liên kết "cookie" ở chân trang. Chúng tôi gửi mã định
danh nội bộ ngẫu nhiên của tài khoản (không phải email). Không có pixel quảng
cáo, không theo dõi chéo trang, không chia sẻ với ai. Căn cứ: sự đồng ý của bạn,
có thể rút lại bất kỳ lúc nào.</p>
<h3>Bảo mật và chống lạm dụng</h3>
<p>Nhật ký máy chủ, giới hạn tần suất theo IP và tín hiệu gian lận, được giữ để
bảo vệ dịch vụ và người dùng. Căn cứ: lợi ích hợp pháp trong việc bảo đảm an
toàn hệ thống.</p>
<p>Chúng tôi không chủ đích xử lý dữ liệu cá nhân nhạy cảm như một phần của dịch
vụ, không đưa ra quyết định tự động nào có hiệu lực pháp lý với bạn, và
<strong>không dùng nội dung hay dữ liệu của bạn để huấn luyện mô hình AI, của
chúng tôi hay của ai khác, và không bán nó.</strong> Nếu video của bạn chứa dữ
liệu nhạy cảm của người khác, bạn chịu trách nhiệm về căn cứ xử lý hợp pháp.</p>

<h2>3. Cookie và lưu trữ cục bộ</h2>
<p>Chúng tôi không đặt cookie của bên thứ ba và không tải script bên thứ ba khi
mở trang. Những gì trang lưu thuộc hai nhóm.</p>
<p><strong>Thiết yếu, luôn bật.</strong> Toàn bộ là dữ liệu của chính chúng tôi,
nằm trong bộ nhớ cục bộ (local storage) của trình duyệt: mã phiên đăng nhập, mã
truy cập ngắn hạn để trình duyệt tải clip và ảnh của chính bạn, tuỳ chọn giao
diện (ngôn ngữ, tab, thiết lập chỉnh sửa gần nhất), và bản ghi lựa chọn cookie
của bạn. Riêng luồng đăng nhập Google dùng một cookie HttpOnly ngắn hạn để chống
giả mạo yêu cầu.</p>
<p><strong>Đo lường lượng truy cập, chỉ sau khi bạn đồng ý.</strong> Xem Mục 2.</p>
<p><strong>Quảng cáo.</strong> Chúng tôi không dùng bộ theo dõi quảng cáo hay tiếp thị
lại. Nhóm này tồn tại trong biểu ngữ để nếu sau này có, nó mặc định tắt.</p>

<h2>4. Ai nhận dữ liệu (bên xử lý phụ) và ở đâu</h2>
<p>Dưới đây là các nhà cung cấp chúng tôi dùng, mỗi bên nhận gì. Phiên bản chi
tiết hơn, kèm biện pháp bảo đảm cho từng bên, được giữ nội bộ trong tài liệu
tuân thủ của chúng tôi và được cập nhật khi có thay đổi.</p>
<ul>
<li><strong>Google (Gemini API)</strong>: phân tích AI để chọn khoảnh khắc, bố
cục, tiêu đề và ảnh thu nhỏ. Nhận bản chép lời, khung hình lấy mẫu (có thể có
khuôn mặt), ảnh tham chiếu bạn chọn cho ảnh thu nhỏ, và trong một số bước kiểm
tra bố cục có thể nhận cả tệp video nguồn. Chúng tôi dùng dự án trả phí, theo đó
điều khoản của Google không cho phép dùng dữ liệu khách hàng để huấn luyện mô
hình. Hoa Kỳ và các khu vực khác của Google.</li>
<li><strong>ElevenLabs</strong>: lồng tiếng AI và giọng AI, chỉ khi bạn yêu cầu.
Nhận âm thanh của clip, tức là giọng của người nói trong đó. Hoa Kỳ.</li>
<li><strong>fal.ai</strong>: các mô hình ảnh và video đằng sau video AI. Nhận ảnh
nhân vật bạn tải lên hoặc tạo (có thể là ảnh người thật) và âm thanh để khớp
khẩu hình. Hoa Kỳ.</li>
<li><strong>Stripe</strong>: thanh toán thẻ quốc tế và quản lý đăng ký. Nhận
email, thông tin thanh toán và dữ liệu giao dịch của bạn. Số thẻ đi thẳng tới
Stripe, không qua máy chủ của chúng tôi. Hoa Kỳ và các khu vực khác của
Stripe.</li>
<li><strong>PayOS</strong>: thanh toán VietQR bằng chuyển khoản ngân hàng. Nhận
thông tin đơn hàng và dữ liệu giao dịch. Việt Nam.</li>
<li><strong>Google (đăng nhập bằng Google)</strong>: chỉ nếu bạn chọn, và chỉ với
phạm vi "openid email profile".</li>
<li><strong>${SMTP_PROVIDER}</strong>: gửi email dịch vụ. Nhận địa chỉ email và
nội dung thư.</li>
<li><strong>Upload-Post</strong>: đăng lên tài khoản mạng xã hội bạn kết nối, chỉ
theo chỉ dẫn của bạn. Bạn kết nối bằng khoá và hồ sơ Upload-Post của chính mình,
và Upload-Post giữ mã truy cập các nền tảng đó theo chính sách riêng của họ.</li>
<li><strong>${STORAGE_PROVIDER}</strong>: lưu trữ clip và tệp dự án.</li>
<li><strong>${HOST_PROVIDER}</strong>: máy chủ nơi dịch vụ chạy.</li>
<li><strong>OpenPanel</strong>: đo lường lượng truy cập, nếu được bật và chỉ khi bạn
đồng ý (Mục 3). Chạy trên máy chủ của chúng tôi.</li>
</ul>
<p>Một số nhà cung cấp trên xử lý dữ liệu ở ngoài lãnh thổ Việt Nam. Khi chuyển
dữ liệu cá nhân ra nước ngoài, chúng tôi thực hiện theo quy định của pháp luật
Việt Nam về chuyển dữ liệu cá nhân xuyên biên giới, bao gồm các thủ tục đánh
giá tác động và thông báo cho cơ quan có thẩm quyền khi pháp luật yêu cầu, và
dùng các bảo đảm hợp đồng, kỹ thuật của nhà cung cấp.</p>

<h2>5. Chúng tôi giữ dữ liệu bao lâu</h2>
<ul>
<li>Clip và dự án: theo thời hạn của gói bạn dùng (hiển thị trên trang bảng giá),
rồi bị xoá. Sau khi gói trả phí hết hạn: thêm ${GRACE_DAYS} ngày.</li>
<li>Dữ liệu tài khoản: trong thời gian tài khoản tồn tại; sau khi xoá, chỉ giữ phần
cần thiết để đáp ứng nghĩa vụ pháp lý hoặc giải quyết tranh chấp.</li>
<li>Dữ liệu thanh toán, hoá đơn, chứng từ kế toán: theo thời hạn mà pháp luật về
thuế và kế toán của Việt Nam yêu cầu.</li>
<li>Bản khai quyền nội dung: cùng với dự án, và bị xoá khi bạn xoá tài khoản, trừ
khi có tranh chấp đang diễn ra.</li>
<li>Tệp làm việc trên máy chủ xử lý (video nguồn tải về, bản sao làm việc): được
dọn tự động, trong vòng 24 giờ sau khi tác vụ kết thúc.</li>
<li>Ảnh thu nhỏ đã tạo và khung hình lấy mẫu để tạo chúng: thời hạn ngắn, sau lần
tải gần nhất.</li>
<li>Ảnh bạn tải lên để tạo nhân vật AI: xoá cùng tác vụ dùng chúng.</li>
<li>Nhật ký ứng dụng: [THỜI HẠN LƯU NHẬT KÝ].</li>
<li>Bản sao lưu cơ sở dữ liệu: [THỜI HẠN LƯU BẢN SAO LƯU], sau đó việc xoá bạn đã
thực hiện cũng biến mất khỏi mọi bản sao.</li>
<li>Dữ liệu phân tích (nếu bạn đồng ý): [THỜI HẠN LƯU DỮ LIỆU PHÂN TÍCH].</li>
</ul>

<h2>6. Quyền của bạn với tư cách chủ thể dữ liệu</h2>
<p>Theo pháp luật Việt Nam về bảo vệ dữ liệu cá nhân, bạn có các quyền sau đối
với dữ liệu cá nhân của mình:</p>
<ul>
<li>được biết về việc xử lý dữ liệu cá nhân của bạn;</li>
<li>đồng ý hoặc không đồng ý, và rút lại sự đồng ý đã cho;</li>
<li>xem, chỉnh sửa hoặc yêu cầu chỉnh sửa dữ liệu;</li>
<li>yêu cầu cung cấp bản sao dữ liệu của bạn;</li>
<li>yêu cầu xoá dữ liệu;</li>
<li>yêu cầu hạn chế xử lý dữ liệu;</li>
<li>phản đối việc xử lý dữ liệu trong những trường hợp pháp luật cho phép;</li>
<li>khiếu nại, tố cáo hoặc khởi kiện, và yêu cầu bồi thường thiệt hại khi bị xâm
phạm;</li>
<li>tự bảo vệ hoặc yêu cầu cơ quan, tổ chức có thẩm quyền bảo vệ quyền của
mình.</li>
</ul>
<p>Để thực hiện các quyền này, hãy gửi yêu cầu từ địa chỉ email của tài khoản
tới ${PRIVACY_EMAIL}; chúng tôi trả lời trong vòng ${REQUEST_DAYS}. Việc xoá có
thể do chính bạn thực hiện: <strong>Tài khoản &rarr; Xoá tài khoản</strong> trong
bảng điều khiển xoá tài khoản và dữ liệu của bạn ngay lập tức, không thể khôi
phục. Nếu bạn đang có đăng ký định kỳ qua Stripe, hãy huỷ gia hạn trước khi xoá
tài khoản. Những gì được giữ lại sau khi xoá là dữ liệu thanh toán, hoá đơn mà pháp luật yêu cầu chúng tôi giữ (Mục 5). Nếu
bạn cho rằng chúng tôi xử lý dữ liệu của bạn sai quy định, bạn có thể liên hệ
chúng tôi trước, và có quyền khiếu nại tới cơ quan nhà nước có thẩm quyền về bảo
vệ dữ liệu cá nhân của Việt Nam.</p>

<h2>7. Bảo mật dữ liệu</h2>
<p>Chúng tôi áp dụng các biện pháp kỹ thuật và quản lý phù hợp để bảo vệ dữ liệu
cá nhân, gồm lưu mật khẩu ở dạng băm một chiều, đường dẫn tải clip có chữ ký và
thời hạn, phân quyền để mỗi người chỉ truy cập dự án của mình, và giới hạn quyền
truy cập nội bộ. Nếu xảy ra sự cố vi phạm dữ liệu cá nhân, chúng tôi sẽ thông
báo cho cơ quan có thẩm quyền và cho bạn trong các trường hợp và thời hạn mà
pháp luật Việt Nam yêu cầu.</p>

<h2>8. Độ tuổi</h2>
<p>Dịch vụ không dành cho trẻ em. Bạn phải từ đủ 16 tuổi để tạo tài khoản, và
việc xử lý dữ liệu của người dưới 16 tuổi cần sự đồng ý của cha mẹ hoặc người
giám hộ theo quy định của pháp luật. Nếu bạn cho rằng một trẻ em đã tạo tài
khoản, hãy viết tới ${PRIVACY_EMAIL} và chúng tôi sẽ xoá tài khoản đó.</p>

<h2>9. Nội dung do AI tạo ra</h2>
<p>Lồng tiếng, video AI và ảnh thu nhỏ AI tạo ra nội dung tổng hợp. Chúng tôi
đánh dấu những gì chúng tôi tạo ở dạng máy đọc được (thẻ siêu dữ liệu trên video,
đánh dấu XMP <code>DigitalSourceType: trainedAlgorithmicMedia</code> trên ảnh).
Dấu này không phải lúc nào cũng còn sau khi nền tảng mã hoá lại video của bạn,
nên khi đăng nội dung tổng hợp, bạn là người phải bật nhãn nội dung AI của nền
tảng; ứng dụng nhắc bạn vào lúc đăng. Nhân bản giọng nói hoặc làm động ảnh của
người thật khi chưa có sự đồng ý của họ bị cấm theo
<a href="/terms">Điều khoản dịch vụ</a>.</p>

<h2>10. Thay đổi chính sách</h2>
<p>Nếu chúng tôi thay đổi chính sách này theo cách đáng kể, chúng tôi sẽ thông
báo qua email hoặc trong ứng dụng trước khi thay đổi có hiệu lực, và ngày ở đầu
trang luôn phản ánh phiên bản hiện hành.</p>
`

const LEGAL_VI = `
${DRAFT_NOTICE}

<h2>Chủ sở hữu trang web</h2>
<p>Thông tin về đơn vị sở hữu và vận hành ${DOMAIN}:</p>
<ul>
<li><strong>Tên pháp nhân:</strong> ${ENTITY}</li>
<li><strong>Mã số thuế:</strong> ${TAX_ID}</li>
<li><strong>Số đăng ký kinh doanh:</strong> ${REG_NO}</li>
<li><strong>Địa chỉ trụ sở:</strong> ${ADDRESS}</li>
<li><strong>Người đại diện theo pháp luật:</strong> ${REPRESENTATIVE}</li>
<li><strong>Điện thoại:</strong> ${PHONE}</li>
<li><strong>Liên hệ:</strong> ${SUPPORT_EMAIL} (hỗ trợ, khiếu nại và thông báo
pháp lý) và ${PRIVACY_EMAIL} (bảo vệ dữ liệu cá nhân)</li>
</ul>

<h2>Mục đích của trang</h2>
<p>${DOMAIN} cung cấp ${BRAND}, dịch vụ AI biến video dài thành các clip dọc
ngắn, theo <a href="/terms">Điều khoản dịch vụ</a>. Dữ liệu cá nhân được xử lý
như mô tả trong <a href="/privacy">Chính sách bảo mật</a>. Thanh toán, hoàn tiền
và hoá đơn được quy định tại <a href="/refunds">Chính sách thanh toán và hoàn
tiền</a>. Giá hiển thị trên trang bảng giá nêu rõ đã hoặc chưa bao gồm thuế;
khoản thuế áp dụng, nếu có, được hiển thị trước khi bạn thanh toán.</p>

<h2>Sở hữu trí tuệ</h2>
<p>Trang ${DOMAIN}, nhãn hiệu và nội dung của nó thuộc sở hữu của ${ENTITY} hoặc bên cấp
phép của chúng tôi. Video và clip được xử lý qua dịch vụ thuộc về chủ sở hữu
tương ứng của chúng.</p>

<h2>Trách nhiệm</h2>
<p>${ENTITY} là bên cung cấp dịch vụ lưu trữ và xử lý nội dung do người dùng gửi
lên. Thông báo về nội dung bị cho là vi phạm có thể gửi tới ${SUPPORT_EMAIL}, là
đầu mối của chúng tôi với người dùng và cơ quan nhà nước có thẩm quyền; quy trình
được mô tả ở <a href="/report-content">Báo cáo nội dung vi phạm</a>.</p>

<h2>Luật áp dụng</h2>
<p>Thông tin pháp lý này được điều chỉnh bởi pháp luật Việt Nam.</p>
`

const REPORT_VI = `
${DRAFT_NOTICE}

<h2>Trang này dùng để làm gì</h2>
<p>Đây là cơ chế tiếp nhận và xử lý thông báo vi phạm của ${BRAND}. Hãy dùng nó để
báo cho chúng tôi rằng nội dung được xử lý, lưu trữ hoặc truyền qua ${DOMAIN}
là trái pháp luật hoặc xâm phạm quyền của bạn, gồm xâm phạm quyền tác giả, nhãn
hiệu, quyền về hình ảnh hay quyền riêng tư. Bạn không cần có tài khoản và không
cần luật sư.</p>
<p>Nếu khiếu nại của bạn về tài khoản, thanh toán hay dữ liệu của chính bạn, đây
không phải trang phù hợp: hãy viết tới ${SUPPORT_EMAIL} và nêu bạn cần gì.</p>

<h2>Cách gửi thông báo</h2>
<p>Gửi email tới <strong>${SUPPORT_EMAIL}</strong> với tiêu đề
<strong>Báo cáo nội dung vi phạm</strong>, bằng tiếng Việt hoặc tiếng Anh. Để
chúng tôi xử lý được ngay mà không phải hỏi lại, thông báo cần có:</p>
<ul>
<li>URL hoặc mã định danh chính xác của nội dung, đủ để chúng tôi tìm thấy mà không
phải dò tìm;</li>
<li>giải thích vì sao bạn cho rằng nội dung đó vi phạm, và vi phạm quy định nào;</li>
<li>họ tên và địa chỉ email của bạn, trừ khi báo cáo liên quan tới nội dung bóc lột
hoặc xâm hại tình dục trẻ em, có thể gửi ẩn danh;</li>
<li>nếu bạn là chủ sở hữu quyền hoặc người được uỷ quyền: nói rõ là bên nào, kèm
thông tin chứng minh quyền của bạn với tác phẩm;</li>
<li>tuyên bố rằng bạn tin một cách thiện chí rằng thông tin trong thông báo là
chính xác và đầy đủ, và chữ ký (điện tử cũng được).</li>
</ul>
<p>Thông báo có đủ các yếu tố trên khiến chúng tôi biết rõ về nội dung, và đó là
điều làm phát sinh nghĩa vụ hành động của chúng tôi.</p>

<h2>Điều gì xảy ra tiếp theo</h2>
<p>Chúng tôi xác nhận đã nhận thông báo của bạn không chậm trễ. Sau đó chúng tôi
xem xét cẩn trọng, khách quan, bằng đánh giá của con người chứ không phải quy tắc
tự động. Khi thông báo có cơ sở, chúng tôi gỡ hoặc vô hiệu hoá truy cập vào nội
dung và cho bạn biết quyết định cùng lý do. Nếu quyết định không hành động, chúng
tôi cũng nói cho bạn biết, kèm lý do.</p>
<p>Thông báo hiển nhiên không có cơ sở, hoặc đến từ người gửi lặp lại với ác ý,
sẽ bị tạm ngừng xử lý sau khi chúng tôi cảnh báo người gửi. Tài khoản tải lên
nội dung vi phạm nhiều lần sẽ bị chấm dứt.</p>

<h2>Nếu nội dung của bạn bị gỡ</h2>
<p>Khi chúng tôi gỡ nội dung của bạn, hạn chế nó hoặc tạm ngưng tài khoản vì lý
do này, bạn nhận được thông báo nêu: chúng tôi đã gỡ hoặc hạn chế cái gì, các sự
kiện chúng tôi dựa vào, căn cứ pháp lý hoặc điều khoản được áp dụng, có hệ thống
tự động nào tham gia hay không, và cách phản đối quyết định.</p>
<p>Để phản đối, hãy trả lời thư đó hoặc viết tới ${SUPPORT_EMAIL}, kèm lý do bạn
cho rằng nội dung hợp pháp (ví dụ bạn là chủ sở hữu hoặc có giấy phép). Một người
xem xét, không phải bộ lọc. Chúng tôi chuyển phản đối cho bên đã gửi thông báo và
có thể khôi phục nội dung nếu họ không cung cấp thêm căn cứ hợp lý trong một thời
hạn hợp lý. Bạn vẫn giữ quyền khiếu nại tới cơ quan nhà nước có thẩm quyền hoặc
khởi kiện tại Toà án; không có nội dung nào ở trang này hạn chế quyền đó.</p>

<h2>Yêu cầu từ cơ quan nhà nước</h2>
<p>Chúng tôi thực hiện yêu cầu gỡ bỏ hoặc cung cấp thông tin hợp lệ của cơ quan
nhà nước có thẩm quyền theo quy định của pháp luật Việt Nam. ${SUPPORT_EMAIL} là
đầu mối tiếp nhận.</p>

<h2>Đầu mối liên hệ</h2>
<p>${SUPPORT_EMAIL} là đầu mối duy nhất của chúng tôi với người dùng và cơ quan
nhà nước có thẩm quyền. Chúng tôi nhận thông báo bằng tiếng Việt và tiếng Anh.
Dịch vụ do ${ENTITY}, mã số thuế ${TAX_ID}, địa chỉ ${ADDRESS}, vận hành.</p>
`

const REFUNDS_VI = `
${DRAFT_NOTICE}

<h2>Tóm tắt</h2>
<p>${BRAND} bán hai thứ: <strong>gói theo tháng</strong> và
<strong>credit nạp thêm</strong>. Trang này nói về cách thanh toán, cách credit
hết hạn, và khi nào bạn được hoàn tiền. Các số ngày và điều kiện cụ thể về hoàn
tiền hiện để trống dưới dạng giữ chỗ, vì đó là quyết định của chủ sở hữu dịch vụ
và chưa được điền.</p>

<h2>Bạn có thể thanh toán bằng cách nào</h2>
<ul>
<li><strong>Stripe (thẻ quốc tế):</strong> gói theo tháng là đăng ký định kỳ, tự
gia hạn mỗi tháng đến khi bạn huỷ. Credit nạp thêm là thanh toán một lần. Stripe
xử lý thẻ của bạn; chúng tôi không nhìn thấy số thẻ.</li>
<li><strong>PayOS (VietQR, VND):</strong> gói là trả trước cho một kỳ 30 ngày và
<strong>không tự gia hạn</strong>; bạn mua lại để tiếp tục. Credit nạp thêm là
thanh toán một lần.</li>
</ul>
<p>Giá được hiển thị trên trang bảng giá. Giá đã bao gồm thuế hay chưa:
[GIÁ ĐÃ BAO GỒM VAT HAY CHƯA]. Ngân hàng hoặc tổ chức phát hành thẻ có thể áp
phí chuyển đổi ngoại tệ riêng, nằm ngoài tầm kiểm soát của chúng tôi.
Hoá đơn: [CHÍNH SÁCH XUẤT HÓA ĐƠN ĐIỆN TỬ VÀ THÔNG TIN CẦN CUNG CẤP].</p>

<h2>Credit hoạt động ra sao</h2>
<ul>
<li><strong>Credit của gói hết hạn vào cuối kỳ thanh toán</strong> và không được
cộng dồn sang kỳ sau.</li>
<li><strong>Credit nạp thêm không hết hạn</strong> và vẫn còn sau khi gói kết
thúc.</li>
<li>Khi bạn dùng dịch vụ, credit sắp hết hạn được trừ trước, rồi mới đến credit
nạp thêm.</li>
<li>Tác vụ thất bại hoặc bị huỷ không bị trừ credit; credit tạm giữ cho tác vụ đó
được trả lại.</li>
<li>Một tác vụ có thể tạm giữ trước một lượng credit ước tính và chỉ trừ số thực
dùng khi hoàn tất.</li>
</ul>

<h2>Huỷ gói</h2>
<p>Bạn có thể huỷ gia hạn bất kỳ lúc nào từ trang Tài khoản. Việc huỷ có hiệu lực
vào cuối kỳ đã trả; bạn vẫn dùng đầy đủ phần credit của kỳ đó đến hết kỳ. Huỷ gia
hạn không tự động kéo theo hoàn tiền.</p>

<h2>Khi nào được hoàn tiền</h2>
<p>Bạn có thể yêu cầu hoàn tiền trong vòng ${REFUND_DAYS} ngày kể từ ngày thanh
toán nếu thoả các điều kiện sau: [ĐIỀU KIỆN HOÀN TIỀN GÓI THÁNG].</p>
<ul>
<li><strong>Gói theo tháng:</strong> [QUY ĐỊNH HOÀN TIỀN GÓI THÁNG, VÍ DỤ CHƯA DÙNG
CREDIT NÀO HAY HOÀN THEO TỶ LỆ].</li>
<li><strong>Credit nạp thêm:</strong> [QUY ĐỊNH HOÀN TIỀN CREDIT NẠP THÊM, VÍ DỤ CHỈ
KHI CHƯA DÙNG].</li>
<li><strong>Credit đã sử dụng:</strong> [QUY ĐỊNH VỀ CREDIT ĐÃ DÙNG].</li>
<li><strong>Tài khoản bị chấm dứt vì vi phạm</strong> (tải lên nội dung trái pháp
luật, xâm phạm bản quyền lặp lại, gian lận): [QUY ĐỊNH VỀ TRƯỜNG HỢP VI PHẠM].</li>
</ul>
<p>Khi có lỗi từ phía chúng tôi (bạn bị tính tiền hai lần, dịch vụ không cung cấp
được như đã cam kết), bạn có quyền được xử lý theo quy định của pháp luật về bảo
vệ người tiêu dùng, bất kể chính sách hoàn tiền nói gì.</p>

<h2>Cách yêu cầu hoàn tiền</h2>
<p>Gửi email từ địa chỉ email của tài khoản tới <strong>${SUPPORT_EMAIL}</strong>,
nêu rõ giao dịch (ngày, số tiền, cổng thanh toán Stripe hay PayOS) và lý do.
Chúng tôi xác nhận đã nhận yêu cầu và trả lời kết quả trong vòng
${REFUND_PROCESS_DAYS} ngày làm việc. Việc hoàn tiền hiện được xử lý thủ công.</p>

<h2>Khi nào bạn nhận lại tiền</h2>
<ul>
<li><strong>Stripe:</strong> hoàn về đúng thẻ đã thanh toán. Ngân hàng phát hành
thẻ có thể mất thêm vài ngày làm việc để hiển thị khoản hoàn.</li>
<li><strong>PayOS:</strong> [CÁCH HOÀN TIỀN QUA PAYOS VÀ THỜI GIAN].</li>
</ul>
<p>Khi hoàn tiền một khoản thanh toán, phần credit đã cấp từ khoản thanh toán đó
bị thu hồi tương ứng: [QUY ĐỊNH THU HỒI CREDIT KHI HOÀN TIỀN]. Hoàn tiền một lần
thanh toán đăng ký định kỳ cũng huỷ đăng ký đó để bạn không bị tính tiền tiếp.</p>

<h2>Quyền theo pháp luật là quyền riêng</h2>
<p>Chính sách này không loại trừ hay hạn chế các quyền mà pháp luật Việt Nam về
bảo vệ quyền lợi người tiêu dùng và thương mại điện tử trao cho bạn. Nếu các quyền
đó tốt hơn chính sách này, quyền theo pháp luật được áp dụng. Chúng tôi sẽ chỉ
cho bạn thấy quyền đó thay vì để bạn mất nó.</p>
`

const REFERRAL_VI = `
${DRAFT_NOTICE}

<h2>1. Chương trình là gì</h2>
<p>Chương trình giới thiệu bạn bè của ${BRAND} cho phép người dùng chia sẻ mã giới thiệu cá nhân.
Khi một người mới ("người được giới thiệu") dùng mã đó và thanh toán thành công lần đầu, cả người
giới thiệu và người được giới thiệu nhận một khoản credit thưởng. Chương trình do ${ENTITY} vận
hành và có thể bật hoặc tắt theo từng máy chủ.</p>

<h2>2. Điều kiện nhận thưởng</h2>
<ul>
<li>Mã phải được gắn vào tài khoản của người được giới thiệu <strong>trước</strong> khoản thanh toán đầu tiên của tài khoản đó.</li>
<li>Mỗi tài khoản chỉ gắn được một mã giới thiệu, và không dùng được mã của chính mình hay của một tài khoản dùng cùng hộp thư.</li>
<li>Thưởng chỉ trả sau khi khoản thanh toán đầu tiên được nhà cung cấp thanh toán xác nhận thành công, và chỉ một lần cho mỗi người được giới thiệu. Các lần gia hạn hoặc nạp thêm sau đó không sinh thưởng mới.</li>
<li>Mỗi người giới thiệu được hưởng tối đa ${REFERRAL_MAX} lượt thưởng.</li>
</ul>

<h2>3. Mức thưởng và cách dùng</h2>
<p>Mức thưởng hiện hành hiển thị trong trang Tài khoản, mục "Giới thiệu bạn bè". Thưởng được cộng
dưới dạng credit nạp thêm, không hết hạn, dùng như credit mua thêm. Credit thưởng không đổi được
thành tiền và không chuyển được sang tài khoản khác.</p>

<h2>4. Hành vi bị cấm</h2>
<p>Không được tạo tài khoản giả, tự giới thiệu mình qua nhiều tài khoản, mua rồi hoàn tiền để lấy
thưởng, spam hoặc quảng cáo gây hiểu lầm khi chia sẻ mã. Chúng tôi có quyền từ chối hoặc thu hồi
thưởng, khoá mã giới thiệu và, trong trường hợp nghiêm trọng, khoá tài khoản liên quan.</p>

<h2>5. Hoàn tiền</h2>
<p>Nếu khoản thanh toán đầu tiên của người được giới thiệu bị hoàn tiền hoặc bị khiếu nại, chúng
tôi có thể thu hồi phần credit thưởng chưa dùng của cả hai bên: [QUY ĐỊNH THU HỒI THƯỞNG KHI HOÀN TIỀN].</p>

<h2>6. Thay đổi và chấm dứt</h2>
<p>Chúng tôi có thể thay đổi hoặc chấm dứt chương trình; thay đổi áp dụng cho các khoản thanh toán
đầu tiên phát sinh sau ngày thông báo. Điều khoản này có hiệu lực từ ${EFFECTIVE_DATE}. Thắc mắc
gửi tới ${SUPPORT_EMAIL}.</p>

<h2>7. Dữ liệu</h2>
<p>Để vận hành chương trình, chúng tôi lưu mã của bạn, việc tài khoản nào dùng mã nào và trạng thái
trả thưởng. Dữ liệu này bị xoá cùng tài khoản. Xem thêm Chính sách bảo mật.</p>
`

export function legalPages() {
  return [
    {
      path: '/terms',
      title: `Điều khoản dịch vụ | ${BRAND}`,
      description:
        'Điều khoản điều chỉnh việc sử dụng ViralShorts: nội dung của bạn vẫn là của bạn, không huấn luyện AI bằng video của bạn, credit và thanh toán, quyền người tiêu dùng, thời hạn lưu trữ và quy tắc sử dụng.',
      h1: 'Điều khoản dịch vụ',
      breadcrumb: [{ name: 'Điều khoản dịch vụ' }],
      published: PUBLISHED,
      updated: PUBLISHED,
      lang: 'vi',
      tldr: [
        'Video của bạn và các clip chúng tôi tạo từ chúng là của bạn. Chúng tôi không dùng nội dung của bạn để huấn luyện mô hình AI.',
        'Bạn phải có quyền với mọi video bạn tải lên hoặc dán liên kết, và bạn là người đăng mọi thứ bạn đăng qua dịch vụ.',
        'Credit của gói hết hạn cuối kỳ; credit nạp thêm không hết hạn. Chi tiết thanh toán và hoàn tiền ở trang chính sách thanh toán.',
      ],
      body: TERMS_VI,
    },
    {
      path: '/privacy',
      title: `Chính sách bảo mật | ${BRAND}`,
      description:
        'ViralShorts lưu gì (email, tham chiếu thanh toán, video bạn xử lý), trong bao lâu, nhà cung cấp nào tham gia và các quyền của chủ thể dữ liệu theo pháp luật Việt Nam.',
      h1: 'Chính sách bảo mật',
      breadcrumb: [{ name: 'Chính sách bảo mật' }],
      published: PUBLISHED,
      updated: PUBLISHED,
      lang: 'vi',
      tldr: [
        'Chúng tôi lưu email, tham chiếu thanh toán và các video bạn xử lý, không hơn những gì dịch vụ cần.',
        'Không có bộ theo dõi quảng cáo; đo lường lượng truy cập, nếu bật, chỉ chạy sau khi bạn đồng ý trong biểu ngữ.',
        'Nội dung của bạn không bao giờ được dùng để huấn luyện mô hình AI. Bạn có thể tự xoá tài khoản và dữ liệu bất kỳ lúc nào.',
      ],
      body: PRIVACY_VI,
    },
    {
      path: '/legal-notice',
      title: `Thông tin pháp lý | ${BRAND}`,
      description:
        'Thông tin nhận diện pháp lý của đơn vị sở hữu và vận hành ViralShorts: tên pháp nhân, mã số thuế, địa chỉ và đầu mối liên hệ.',
      h1: 'Thông tin pháp lý',
      breadcrumb: [{ name: 'Thông tin pháp lý' }],
      published: PUBLISHED,
      updated: PUBLISHED,
      lang: 'vi',
      tldr: [
        `${BRAND} do ${ENTITY} vận hành, mã số thuế ${TAX_ID}, địa chỉ ${ADDRESS}, liên hệ ${SUPPORT_EMAIL}.`,
      ],
      body: LEGAL_VI,
    },
    {
      path: '/report-content',
      title: `Báo cáo nội dung vi phạm | ${BRAND}`,
      description:
        'Cách báo cáo nội dung trái pháp luật hoặc xâm phạm quyền trên ViralShorts: thông báo cần chứa gì, chúng tôi xử lý ra sao và cách phản đối việc gỡ nội dung.',
      h1: 'Báo cáo nội dung vi phạm',
      breadcrumb: [{ name: 'Báo cáo nội dung vi phạm' }],
      published: PUBLISHED,
      updated: PUBLISHED,
      lang: 'vi',
      tldr: [
        'Gửi email tới địa chỉ hỗ trợ với tiêu đề "Báo cáo nội dung vi phạm", URL chính xác, lý do vi phạm và thông tin liên hệ của bạn.',
        'Chúng tôi xác nhận đã nhận không chậm trễ, để một người xem xét, và cho bạn biết quyết định cùng lý do.',
        'Nếu nội dung của bạn bị gỡ, bạn nhận được thông báo nêu lý do và có thể phản đối; quyền khiếu nại tới cơ quan nhà nước và khởi kiện vẫn nguyên vẹn.',
      ],
      body: REPORT_VI,
    },
    {
      path: '/refunds',
      title: `Chính sách thanh toán và hoàn tiền | ${BRAND}`,
      description:
        'Cách thanh toán ViralShorts qua Stripe và PayOS, cách credit gói và credit nạp thêm hết hạn, huỷ gói và điều kiện hoàn tiền.',
      h1: 'Chính sách thanh toán và hoàn tiền',
      breadcrumb: [{ name: 'Thanh toán và hoàn tiền' }],
      published: PUBLISHED,
      updated: PUBLISHED,
      lang: 'vi',
      tldr: [
        'Gói theo tháng cấp credit mỗi kỳ và credit đó hết hạn cuối kỳ; credit nạp thêm không hết hạn.',
        'Thanh toán bằng thẻ quốc tế qua Stripe (tự gia hạn) hoặc VietQR qua PayOS (trả trước 30 ngày, không tự gia hạn).',
        'Yêu cầu hoàn tiền gửi qua email hỗ trợ; điều kiện và thời hạn cụ thể do chủ sở hữu dịch vụ quy định ở trang này.',
      ],
      body: REFUNDS_VI,
    },
    {
      path: '/referral-terms',
      title: `Điều khoản chương trình giới thiệu bạn bè | ${BRAND}`,
      description:
        'Điều kiện nhận thưởng credit khi giới thiệu bạn bè dùng ViralShorts: khi nào thưởng được trả, giới hạn, hành vi bị cấm và thu hồi thưởng. Bản nháp.',
      h1: 'Điều khoản chương trình giới thiệu bạn bè',
      breadcrumb: [{ name: 'Chương trình giới thiệu' }],
      published: PUBLISHED,
      updated: PUBLISHED,
      lang: 'vi',
      tldr: [
        'Khi bạn bè dùng mã của bạn và trả tiền lần đầu, cả hai nhận credit thưởng, một lần cho mỗi người được giới thiệu.',
        'Thưởng là credit nạp thêm (không hết hạn), không đổi thành tiền.',
        'Tài khoản giả, tự giới thiệu và mua rồi hoàn tiền bị cấm; thưởng có thể bị thu hồi.',
      ],
      body: REFERRAL_VI,
    },
  ]
}
