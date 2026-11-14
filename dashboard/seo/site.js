/* Nguồn duy nhất cho thông tin thương hiệu, pháp nhân và các điều khoản do chủ sở hữu
 * quyết định. Được nạp bởi seo/legal.js (trang pháp lý tĩnh, chạy lúc build trong Node),
 * seo/render.js, vite-plugin-seo.js và src/Legal.jsx (trình duyệt), nên file này chỉ chứa
 * hằng số thuần, không import gì.
 *
 * ĐIỀN TRƯỚC KHI MỞ BÁN, KHÔNG TỰ SUY ĐOÁN. Mọi giá trị trong ngoặc vuông là chỗ giữ chỗ.
 * Danh sách đầy đủ và cách điền: docs/compliance/placeholders.md.
 */

export const BRAND = 'ViralShorts'
export const PUBLISHED = '2026-11-12'

// ---- Thông tin pháp nhân ---------------------------------------------------
export const ENTITY = '[TÊN PHÁP NHÂN]'
export const TAX_ID = '[MÃ SỐ THUẾ]'
export const REG_NO = '[SỐ ĐĂNG KÝ KINH DOANH]'
export const ADDRESS = '[ĐỊA CHỈ]'
export const SUPPORT_EMAIL = '[EMAIL HỖ TRỢ]'
export const PRIVACY_EMAIL = '[EMAIL BẢO VỆ DỮ LIỆU]'
export const PHONE = '[SỐ ĐIỆN THOẠI]'
export const DOMAIN = '[TÊN MIỀN]'
export const REPRESENTATIVE = '[NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT]'

// ---- Điều khoản do chủ sở hữu quyết định (chưa có giá trị mặc định) --------
export const REFUND_DAYS = '[SỐ NGÀY HOÀN TIỀN]'
export const REFUND_PROCESS_DAYS = '[SỐ NGÀY XỬ LÝ HOÀN TIỀN]'
export const PRICE_NOTICE_DAYS = '[SỐ NGÀY BÁO TRƯỚC KHI ĐỔI GIÁ]'
export const TERMS_NOTICE_DAYS = '[SỐ NGÀY BÁO TRƯỚC KHI ĐỔI ĐIỀU KHOẢN]'
export const GRACE_DAYS = '[SỐ NGÀY LƯU TRỮ SAU KHI GÓI HẾT HẠN]'
export const REQUEST_DAYS = '[SỐ NGÀY XỬ LÝ YÊU CẦU VỀ DỮ LIỆU]'
export const LIABILITY_CAP = '[MỨC TRẦN TRÁCH NHIỆM]'
export const DISPUTE_FORUM = '[TÒA ÁN HOẶC TRUNG TÂM TRỌNG TÀI GIẢI QUYẾT TRANH CHẤP]'
export const EFFECTIVE_DATE = '[NGÀY CÓ HIỆU LỰC]'
export const REFERRAL_MAX = '[SỐ LƯỢT THƯỞNG TỐI ĐA CHO MỖI NGƯỜI GIỚI THIỆU]'

// ---- Nhà cung cấp hạ tầng chưa xác định ------------------------------------
export const HOST_PROVIDER = '[TÊN NHÀ CUNG CẤP MÁY CHỦ]'
export const STORAGE_PROVIDER = '[TÊN NHÀ CUNG CẤP LƯU TRỮ S3/R2]'
export const SMTP_PROVIDER = '[TÊN NHÀ CUNG CẤP EMAIL SMTP]'
