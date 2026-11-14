/* Bài trợ giúp của ViralShorts (tiếng Việt), nguồn duy nhất cho hai nơi:
 *   - src/pages/HelpPage.jsx (#/help, có ô tìm kiếm trong trang)
 *   - các trang tĩnh /help và /help/<slug> do vite-plugin-seo.js phát ra lúc build.
 *
 * Nội dung là dữ liệu thuần (không HTML), nên trang React không cần dangerouslySetInnerHTML và
 * trang tĩnh tự escape. Khối hợp lệ: { h }, { p }, { ul: [] }, { ol: [] }. Trong chữ có thể dùng
 * liên kết [chữ](địa chỉ).
 *
 * Quy tắc: không in con số giá hay hạn mức (chúng nằm ở máy chủ, studio/plans.py, và còn là
 * giá trị tạm). Chỉ nêu điều mã nguồn hiện làm thật.
 */

export const HELP_UPDATED = '2026-11-12'

export const HELP_ARTICLES = [
  {
    slug: 'bat-dau',
    title: 'Bắt đầu: từ video dài đến clip đầu tiên',
    summary: 'Tạo dự án, chọn tuỳ chọn, chờ AI xử lý và lấy clip về.',
    blocks: [
      { p: 'ViralShorts cắt một video dài thành nhiều clip dọc 9:16, chấm điểm từng clip và gợi ý tiêu đề. Cách làm nhanh nhất:' },
      { ol: [
        'Bấm **Tạo clip** ở góc trên bên phải (trên điện thoại là nút dấu cộng).',
        'Dán liên kết video (YouTube và một số trang khác) hoặc tải tệp từ máy.',
        'Mở phần tuỳ chọn nếu muốn: thể loại, từ khoá cần ưu tiên, độ dài clip, đoạn video cần xử lý, ngôn ngữ nói và bộ nhận diện thương hiệu.',
        'Bấm tạo và chờ. Dự án hiện trong **Dự án** với trạng thái đang xử lý; bạn có thể rời trang, kết quả vẫn được giữ.',
        'Khi xong, mở dự án để xem từng clip cùng điểm, chỉnh sửa, tải về hoặc đăng.',
      ] },
      { h: 'Điểm của clip là gì?' },
      { p: 'Điểm từ 0 đến 99 là dự đoán mức hấp dẫn của clip, kèm lý do (mở đầu, nhịp nói, độ dài…). Đó là gợi ý để bạn chọn clip nào đăng trước, không phải cam kết về lượt xem.' },
      { h: 'Nếu dự án bị lỗi' },
      { p: 'Dự án lỗi hoặc bị huỷ không tốn credit; phần đã tạm giữ được hoàn lại. Thử lại với video khác hoặc xem bài [Credit hoạt động thế nào](/help/credit).' },
    ],
  },
  {
    slug: 'credit',
    title: 'Credit hoạt động thế nào',
    summary: 'Credit tính ra sao, loại nào hết hạn, và chuyện gì xảy ra khi hết.',
    blocks: [
      { p: 'Credit là đơn vị dùng chung cho mọi tính năng. Một phút video nguồn xử lý ở bước tạo clip tốn một credit; các tính năng dùng dịch vụ AI bên thứ ba (lồng tiếng, video AI…) tốn nhiều hơn và con số hiện ngay trên nút trước khi bạn bấm.' },
      { h: 'Hai loại credit' },
      { ul: [
        '**Credit của gói**: cấp mỗi kỳ thanh toán và hết hạn cuối kỳ.',
        '**Credit nạp thêm**: mua riêng, không hết hạn.',
      ] },
      { p: 'Tài khoản miễn phí nhận một lượng credit mỗi tháng. Nếu hệ thống yêu cầu xác minh email thì credit miễn phí chỉ xuất hiện sau khi bạn bấm liên kết xác minh trong thư.' },
      { h: 'Khi nào credit bị trừ' },
      { ul: [
        'Khi bắt đầu một việc, hệ thống tạm giữ số credit ước tính.',
        'Khi việc xong, số thật được chốt: dư thì trả lại, thiếu thì trừ thêm trong giới hạn đã báo.',
        'Việc lỗi hoặc bị huỷ thì tạm giữ được hoàn lại.',
      ] },
      { h: 'Hết credit thì sao' },
      { p: 'Một cửa sổ sẽ báo bạn thiếu bao nhiêu và đưa bạn tới trang [Bảng giá](/#/pricing) để đổi gói hoặc nạp thêm. Mã khuyến mãi nhập ở trang Tài khoản.' },
    ],
  },
  {
    slug: 'caption',
    title: 'Phụ đề, hook và bộ nhận diện thương hiệu',
    summary: 'Chọn kiểu phụ đề, thêm hook mở đầu và đặt mặc định cho mọi dự án.',
    blocks: [
      { p: 'Mỗi clip có thể có phụ đề tự động từ lời thoại, chữ hook ở đầu clip và logo của bạn.' },
      { h: 'Phụ đề' },
      { ol: [
        'Mở dự án, chọn clip rồi vào công cụ phụ đề.',
        'Chọn một kiểu có sẵn (ví dụ TikTok, Reels, Shorts, Neon, Karaoke, Tối giản) và xem thử.',
        'Áp dụng. Clip được dựng lại với phụ đề đã chọn.',
      ] },
      { p: 'Phụ đề được nhận diện từ giọng nói, nên hãy đọc lướt một lượt trước khi đăng, nhất là tên riêng và từ chuyên ngành.' },
      { h: 'Hook' },
      { p: 'Hook là dòng chữ ngắn hiện ở đầu clip để giữ người xem. AI gợi ý sẵn; bạn có thể sửa chữ và chọn kiểu hiển thị.' },
      { h: 'Bộ nhận diện thương hiệu' },
      { p: 'Trang **Thương hiệu** lưu logo, vị trí logo, màu, kiểu phụ đề, kiểu hook và bố cục mặc định. Khi tạo dự án bạn chọn bộ nào dùng, hoặc chọn không dùng; nếu không chọn, bộ mặc định của bạn được áp dụng.' },
    ],
  },
  {
    slug: 'dang-bai',
    title: 'Đăng bài và lên lịch',
    summary: 'Kết nối Upload-Post, đăng ngay hoặc xếp lịch cả tuần trên TikTok, Reels, Shorts.',
    blocks: [
      { p: 'ViralShorts đăng bài qua dịch vụ Upload-Post bằng khoá của chính bạn. Khoá được lưu trong trình duyệt của bạn, máy chủ ViralShorts không lưu.' },
      { h: 'Kết nối' },
      { ol: [
        'Tạo tài khoản Upload-Post và kết nối TikTok, Instagram, YouTube ở đó.',
        'Vào trang [Lịch đăng](/#/calendar) và dán khoá Upload-Post vào thẻ kết nối.',
        'Hệ thống kiểm tra khoá và chọn hồ sơ đầu tiên tìm thấy.',
      ] },
      { h: 'Đăng và lên lịch' },
      { ul: [
        'Từ một clip, bạn có thể đăng ngay hoặc đặt giờ.',
        'Trong **Lịch đăng**, kéo clip vào một ngày (trên điện thoại: chạm vào ngày), chọn giờ, mạng xã hội, tiêu đề và mô tả rồi lưu. Bài ở trạng thái **Dự kiến** cho tới khi bạn bấm **Gửi lên lịch**.',
        'Sau khi gửi, bài là **Đã lên lịch** ở Upload-Post. Muốn đổi giờ hoặc nội dung, huỷ bài trong hàng đợi rồi sửa.',
        'Đăng bài cần gói có tính năng đăng. Nếu gói của bạn chưa có, hệ thống sẽ báo và dẫn tới Bảng giá.',
      ] },
      { h: 'Lưu ý về TikTok' },
      { p: 'Bài gửi lên TikTok qua đường này vào mục nháp của TikTok; bạn hoàn tất và bấm đăng trong ứng dụng TikTok. Phần mô tả không đi kèm bản nháp, hãy nhập lại khi đăng.' },
      { h: 'Trạng thái bài' },
      { p: '**Đã gửi đi** nghĩa là bài đã quá giờ và không còn trong hàng đợi của Upload-Post. Đó là suy luận của lịch, hãy xem kết quả thật trên mạng xã hội.' },
    ],
  },
  {
    slug: 'thanh-toan',
    title: 'Thanh toán, hoá đơn và huỷ gói',
    summary: 'Các cách thanh toán, xin hoá đơn, huỷ gia hạn và hoàn tiền.',
    blocks: [
      { p: 'Bạn thanh toán bằng thẻ quốc tế qua Stripe hoặc VietQR qua PayOS. Thẻ tự gia hạn mỗi kỳ; PayOS trả trước một kỳ và không tự gia hạn.' },
      { h: 'Mua gói hoặc nạp credit' },
      { ol: [
        'Mở [Bảng giá](/#/pricing), chọn gói hoặc gói nạp.',
        'Chọn cách thanh toán và hoàn tất trên trang của nhà cung cấp.',
        'Khi nhà cung cấp xác nhận, credit và gói được cập nhật. Có thể mất vài giây; nếu vẫn chưa thấy, tải lại trang Tài khoản.',
      ] },
      { h: 'Hoá đơn' },
      { p: 'Ở trang Tài khoản, điền thông tin xuất hoá đơn (tên đơn vị, mã số thuế, địa chỉ, email) rồi yêu cầu hoá đơn cho từng khoản thanh toán. Biên nhận xem được ngay trong danh sách thanh toán.' },
      { h: 'Huỷ gia hạn' },
      { p: 'Trang Tài khoản có nút huỷ gia hạn. Gói vẫn dùng được đến hết kỳ đã trả; sau đó tài khoản về gói miễn phí. Bạn có thể bật lại gia hạn trước khi kỳ kết thúc.' },
      { h: 'Hoàn tiền' },
      { p: 'Điều kiện và thời hạn hoàn tiền nằm ở trang [Thanh toán và hoàn tiền](/refunds). Gửi yêu cầu qua email hỗ trợ cuối trang này.' },
    ],
  },
  {
    slug: 'lich-dang',
    title: 'Dùng Lịch đăng hiệu quả',
    summary: 'Xem theo tháng hoặc tuần, kéo bài sang ngày khác, xử lý bài lỗi.',
    blocks: [
      { ul: [
        'Chuyển giữa **Tháng** và **Tuần** ở góc trên của lịch. Giờ hiển thị theo múi giờ của trình duyệt.',
        'Kéo một bài **Dự kiến** hoặc **Lỗi** sang ngày khác để đổi ngày, giờ giữ nguyên.',
        'Bài **Đã lên lịch** không kéo được: mở bài, huỷ trong hàng đợi, rồi sửa.',
        'Nút **Lên lịch cả tuần** xếp mỗi clip của dự án đang chọn vào một ngày liên tiếp và gửi ngay. Các bài này hiện trên lịch dưới dạng chỉ đọc vì chúng không đi qua bước xếp lịch ở đây.',
        'Bài bị lỗi hiển thị lý do từ Upload-Post. Sửa nội dung hoặc giờ rồi gửi lại.',
      ] },
    ],
  },
  {
    slug: 'xoa-tai-khoan',
    title: 'Xoá tài khoản và dữ liệu',
    summary: 'Tải dữ liệu của bạn, rồi xoá tài khoản vĩnh viễn.',
    blocks: [
      { p: 'Bạn có thể tự xoá tài khoản bất kỳ lúc nào. Việc này không hoàn tác được.' },
      { ol: [
        'Vào trang Tài khoản và chọn **Tải dữ liệu của tôi** nếu muốn giữ một bản (hồ sơ, dự án, thanh toán, lịch đăng).',
        'Kéo xuống mục xoá tài khoản và bấm xoá.',
        'Nhập mật khẩu (tài khoản đăng nhập bằng Google thì nhập lại email) để xác nhận.',
      ] },
      { h: 'Điều gì xảy ra' },
      { ul: [
        'Gói thanh toán thẻ đang gia hạn được huỷ trước; nếu huỷ không được, tài khoản chưa bị xoá để bạn không phải trả tiền cho thứ không còn.',
        'Dự án, clip, bộ thương hiệu, khoá API và lịch đăng bị xoá.',
        'Hồ sơ thanh toán tối thiểu có thể được giữ lại theo yêu cầu của pháp luật về kế toán, không còn gắn với bạn. Chi tiết ở [Chính sách bảo mật](/privacy).',
      ] },
    ],
  },
]

// ---- tiện ích dùng chung ------------------------------------------------------------------
const INLINE = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g

/** Tách một đoạn chữ thành các mảnh { text } | { bold } | { text, href }. */
export function inlineParts(text) {
  return String(text)
    .split(INLINE)
    .filter(Boolean)
    .map((part) => {
      const b = /^\*\*([^*]+)\*\*$/.exec(part)
      if (b) return { bold: b[1] }
      const l = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part)
      if (l) return { text: l[1], href: l[2] }
      return { text: part }
    })
}

const plain = (s) => inlineParts(s).map((x) => x.bold || x.text).join('')

/** Toàn bộ chữ của bài, không dấu định dạng, để tìm kiếm. */
export function articleText(a) {
  const out = [a.title, a.summary]
  for (const b of a.blocks) {
    if (b.h) out.push(b.h)
    if (b.p) out.push(plain(b.p))
    for (const li of b.ul || b.ol || []) out.push(plain(li))
  }
  return out.join(' \n ')
}

/** Bỏ dấu tiếng Việt và hạ chữ thường: "Hoàn tiền" khớp "hoan tien". */
export function fold(s) {
  return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase()
}

/** Bài khớp mọi từ trong câu tìm. Câu rỗng trả về tất cả. */
export function searchArticles(query, articles = HELP_ARTICLES) {
  const words = fold(query).split(/\s+/).filter(Boolean)
  if (!words.length) return articles
  // Every word must appear somewhere; articles whose title or summary carry the words come first.
  const score = (a) => {
    const head = fold(`${a.title} ${a.summary}`)
    return words.filter((w) => head.includes(w)).length
  }
  return articles
    .filter((a) => {
      const hay = fold(articleText(a))
      return words.every((w) => hay.includes(w))
    })
    .map((a, i) => ({ a, i, s: score(a) }))
    .sort((x, y) => y.s - x.s || x.i - y.i)
    .map((x) => x.a)
}

/** HTML tĩnh cho một danh sách khối. `esc` là hàm escape của seo/render.js. */
export function blocksToHtml(blocks, esc) {
  const inline = (s) => inlineParts(s).map((x) => {
    if (x.bold) return `<strong>${esc(x.bold)}</strong>`
    if (x.href) return `<a href="${esc(x.href)}">${esc(x.text)}</a>`
    return esc(x.text)
  }).join('')
  return blocks.map((b) => {
    if (b.h) return `<h2>${esc(b.h)}</h2>`
    if (b.p) return `<p>${inline(b.p)}</p>`
    if (b.ul) return `<ul>${b.ul.map((li) => `<li>${inline(li)}</li>`).join('')}</ul>`
    if (b.ol) return `<ol>${b.ol.map((li) => `<li>${inline(li)}</li>`).join('')}</ol>`
    return ''
  }).join('\n')
}
