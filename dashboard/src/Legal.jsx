import React from 'react';
import { ArrowLeft, FileText, Shield, Landmark, Flag, RotateCcw } from 'lucide-react';

// Văn bản pháp lý chính thức là các trang tĩnh do vite-plugin-seo.js phát ra khi build
// từ seo/legal.js (/terms, /privacy, /legal-notice, /report-content, /refunds). Màn hình
// này chỉ là trang tổng hợp có phần tóm tắt và liên kết, để route SPA (#legal) và các
// trang cho trình thu thập không bao giờ lệch nhau: toàn văn chỉ nằm ở một nơi.
//
// Thông tin pháp nhân (tên, mã số thuế, địa chỉ, email, tên miền) nằm ở seo/site.js,
// nguồn duy nhất dùng chung với các trang tĩnh. Bản nháp này CHƯA phải tư vấn pháp lý
// và cần được rà soát trước khi mở bán.
import { PUBLISHED as LAST_UPDATED, SUPPORT_EMAIL, ENTITY, TAX_ID, ADDRESS, DOMAIN } from '../seo/site.js';

const DOCS = [
    {
        icon: FileText,
        title: 'Điều khoản dịch vụ',
        desc: 'Bạn được làm gì với dịch vụ, quyền đối với nội dung của bạn, credit và thanh toán, quy tắc sử dụng.',
        href: '/terms',
    },
    {
        icon: Shield,
        title: 'Chính sách bảo mật',
        desc: 'Chúng tôi lưu gì, trong bao lâu, nhà cung cấp nào xử lý dữ liệu và các quyền của bạn theo pháp luật bảo vệ dữ liệu cá nhân của Việt Nam. Không có gì không thiết yếu được tải cho đến khi bạn đồng ý.',
        href: '/privacy',
    },
    {
        icon: Landmark,
        title: 'Thông tin pháp lý',
        desc: 'Đơn vị sở hữu và vận hành trang: tên pháp nhân, mã số thuế, địa chỉ và đầu mối liên hệ.',
        href: '/legal-notice',
    },
    {
        icon: RotateCcw,
        title: 'Thanh toán và hoàn tiền',
        desc: 'Thanh toán qua Stripe và PayOS, cách credit gói và credit nạp thêm hết hạn, huỷ gói và điều kiện hoàn tiền.',
        href: '/refunds',
    },
    {
        icon: Flag,
        title: 'Báo cáo nội dung vi phạm',
        desc: 'Cách báo cáo nội dung vi phạm hoặc trái pháp luật, chúng tôi xử lý thông báo ra sao và cách phản đối việc gỡ nội dung.',
        href: '/report-content',
    },
];

export default function Legal() {
    const handleBack = () => {
        window.location.hash = '';
    };

    return (
        <div className="min-h-screen bg-paper text-ink2">
            <header className="border-b border-rule sticky top-0 bg-paper z-10">
                <div className="max-w-[65ch] mx-auto px-6 py-3 flex items-center">
                    <button onClick={handleBack} className="btn-quiet">
                        <ArrowLeft size={16} /> Quay lại
                    </button>
                </div>
            </header>

            <main className="max-w-[65ch] mx-auto px-6 py-12">
                <h1 className="font-display lowercase text-3xl md:text-4xl text-ink mb-3">Điều khoản &amp; Bảo mật</h1>
                <p className="readout mb-10">Cập nhật lần cuối: {LAST_UPDATED}</p>

                <div className="text-ink2 leading-relaxed space-y-3 text-sm mb-10">
                    <p>
                        <strong className="text-ink">Lưu ý (bản nháp):</strong> các văn bản dưới đây chưa phải tư vấn
                        pháp lý và cần được người có chuyên môn pháp lý rà soát trước khi dịch vụ được mở bán.
                    </p>
                    <p>Tóm tắt ngắn:</p>
                    <ul className="list-disc pl-6 space-y-2">
                        <li><strong className="text-ink">Video và clip của bạn là của bạn.</strong> Chúng tôi không dùng nội dung của bạn để huấn luyện mô hình AI.</li>
                        <li><strong className="text-ink">Bạn phải có quyền</strong> với mọi video bạn tải lên hoặc dán liên kết, và bạn là người đăng những gì bạn đăng.</li>
                        <li><strong className="text-ink">Không có bộ theo dõi quảng cáo.</strong> Đo lường lượng truy cập, nếu bật, chỉ chạy sau khi bạn đồng ý.</li>
                        <li><strong className="text-ink">Credit của gói hết hạn cuối kỳ;</strong> credit nạp thêm thì không hết hạn. Thanh toán bằng thẻ quốc tế qua Stripe hoặc VietQR qua PayOS.</li>
                        <li><strong className="text-ink">Xoá tất cả bất kỳ lúc nào.</strong> Tài khoản &rarr; Xoá tài khoản xoá dự án, clip và khoá của bạn ngay lập tức, không cần gửi email cho chúng tôi.</li>
                    </ul>
                    <p>Toàn văn các tài liệu:</p>
                </div>

                <div className="space-y-3 mb-12">
                    {DOCS.map((doc) => { const { title, desc, href } = doc; const Icon = doc.icon; return (
                        <a
                            key={href}
                            href={href}
                            className="flex items-start gap-4 p-4 border border-rule rounded-card hover:border-brass transition-colors"
                        >
                            <Icon size={18} className="text-brass shrink-0 mt-0.5" />
                            <span>
                                <span className="block text-ink font-medium">{title}</span>
                                <span className="block text-sm text-muted mt-1">{desc}</span>
                            </span>
                        </a>
                    ); })}
                </div>

                <p className="text-sm text-muted">
                    {DOMAIN} do {ENTITY} (mã số thuế {TAX_ID}), địa chỉ {ADDRESS}, vận hành. Câu hỏi:{' '}
                    <a className="underline underline-offset-2 hover:text-brass transition-colors" href={`mailto:${SUPPORT_EMAIL}`}>
                        {SUPPORT_EMAIL}
                    </a>
                    .
                </p>
            </main>
        </div>
    );
}
