/* Bề mặt SEO và pháp lý, sinh lúc build. Không có gì chạy ở runtime.
 *
 * Phát ra:
 *   - /terms, /privacy, /refunds, /legal-notice, /report-content: HTML tĩnh (seo/legal.js
 *     lo nội dung, seo/render.js lo khung), đọc được khi không có JavaScript.
 *   - 404.html (nginx dùng làm error_page), robots.txt, và khi có SITE_URL: sitemap.xml
 *     và llms.txt với địa chỉ tuyệt đối.
 *   - một khối <noscript> trong #root của index.html cho trình thu thập không chạy JS.
 *
 * nginx phân giải đường dẫn sạch bằng `try_files $uri $uri.html`, nên terms.html trả lời
 * cho /terms. Dev server trả cùng các trang từ bộ nhớ nên liên kết chạy cả khi dev.
 *
 * Build THẤT BẠI nếu thiếu trang pháp lý bắt buộc, hoặc nếu một trang đã phát ra không
 * có trong dist/: form đăng ký trỏ tới /terms thì /terms không bao giờ được trả về vỏ SPA.
 *
 * SITE_URL (ví dụ https://viralshorts.example) đặt lúc build để có canonical, og:url,
 * sitemap và llms.txt tuyệt đối. Không đặt thì các thứ đó bị bỏ ra, không bịa địa chỉ.
 * (docker-compose.prod.yml chưa truyền biến này vào lúc build; xem docs/deploy-vi.md.)
 */

import fs from 'node:fs'
import path from 'node:path'
import { legalPages } from './seo/legal.js'
import { helpPages } from './seo/help-pages.js'
import { renderPage } from './seo/render.js'
import { CRAWLER_CONTENT } from './seo/crawler-content.js'
import { BRAND, SUPPORT_EMAIL, PUBLISHED } from './seo/site.js'

const REQUIRED = ['/terms', '/privacy', '/refunds', '/legal-notice', '/report-content']
const ROOT_EMPTY = '<div id="root"></div>'

const notFoundPage = () => ({
  path: '/404',
  noindex: true,
  title: `Không tìm thấy trang | ${BRAND}`,
  description: `Địa chỉ này không phải là một trang của ${BRAND}.`,
  h1: 'Không tìm thấy trang',
  body: `<p>Địa chỉ bạn mở không tồn tại. Ứng dụng nằm ở <a href="/">trang chủ</a>; bảng giá ở
<a href="/#/pricing">đây</a>.</p>`,
})

export default function seoPlugin() {
  const site = (process.env.SITE_URL || '').replace(/\/+$/, '')
  const legal = legalPages()
  const missing = REQUIRED.filter((p) => !legal.some((x) => x.path === p))
  if (missing.length) throw new Error(`[viralshorts-seo] seo/legal.js thiếu trang: ${missing.join(', ')}`)
  // Trợ giúp (/help, /help/<bài>) và /changelog; địa chỉ hỗ trợ lấy từ SUPPORT_EMAIL lúc build.
  const help = helpPages(process.env.SUPPORT_EMAIL)
  const pages = [...legal, ...help]
  // Chân trang chỉ liệt kê trang pháp lý, trợ giúp và changelog, không liệt kê từng bài trợ giúp.
  const footerLinks = [...legal, ...help.filter((p) => p.path === '/help' || p.path === '/changelog')]

  const render = (page) => renderPage(page, footerLinks, site)
  const fileOf = (page) => `${page.path.slice(1)}.html`

  const robots =
    'User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /videos/\nDisallow: /thumbnails/\n' +
    (site ? `\nSitemap: ${site}/sitemap.xml\n` : '')

  const sitemap = () =>
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    [`${site}/`, ...pages.map((p) => `${site}${p.path}`)]
      .map((u) => `  <url><loc>${u}</loc><lastmod>${PUBLISHED}</lastmod></url>`)
      .join('\n') +
    '\n</urlset>\n'

  // llms.txt chỉ là phần phụ, không phải chiến lược: chưa nhà cung cấp mô hình lớn nào cam
  // kết đọc nó. Giữ ngắn và chỉ nêu điều đúng.
  const llms = () =>
    `# ${BRAND}\n\n` +
    `> ${BRAND} là dịch vụ trả phí tự động cắt video dài thành clip dọc 9:16 cho TikTok, ` +
    `Instagram Reels và YouTube Shorts, kèm điểm viral giải thích được.\n\n` +
    `Có gói miễn phí với một số credit mỗi tháng; gói trả phí theo tháng và credit nạp thêm. ` +
    `Giá hiện hành ở ${site}/#/pricing. Liên hệ: ${SUPPORT_EMAIL}.\n\n## Trang\n\n` +
    pages.map((p) => `- [${p.h1}](${site}${p.path}): ${p.description}`).join('\n') +
    '\n'

  return {
    name: 'viralshorts-seo',

    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        if (!html.includes(ROOT_EMPTY)) {
          // Báo lỗi thay vì âm thầm phát một trang chủ rỗng cho bot.
          throw new Error(`[viralshorts-seo] không thấy ${ROOT_EMPTY} trong index.html; khối nội dung cho trình thu thập chưa được chèn.`)
        }
        // canonical, og:url và og:image cần địa chỉ tuyệt đối nên chỉ có khi đặt SITE_URL.
        const absolute = site
          ? `  <link rel="canonical" href="${site}/" />
  <meta property="og:url" content="${site}/" />
` +
            `  <meta property="og:image" content="${site}/logo-viralshorts.png" />
`
          : ''
        return html
          .replace('</head>', `${absolute}</head>`)
          .replace(ROOT_EMPTY, `<div id="root"><noscript>${CRAWLER_CONTENT}</noscript></div>`)
      },
    },

    generateBundle() {
      for (const page of pages) this.emitFile({ type: 'asset', fileName: fileOf(page), source: render(page) })
      this.emitFile({ type: 'asset', fileName: '404.html', source: render(notFoundPage()) })
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robots })
      if (site) {
        this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemap() })
        this.emitFile({ type: 'asset', fileName: 'llms.txt', source: llms() })
      }
    },

    // Kiểm tra sau khi ghi đĩa: file thật sự có mặt trong dist/ và không rỗng.
    closeBundle() {
      const outDir = path.resolve(process.cwd(), 'dist')
      if (!fs.existsSync(outDir)) return // không phải lượt build ghi ra đĩa
      const expected = [...pages.map(fileOf), '404.html', 'robots.txt', ...(site ? ['sitemap.xml', 'llms.txt'] : [])]
      const bad = expected.filter((f) => {
        try { return fs.statSync(path.join(outDir, f)).size === 0 } catch { return true }
      })
      if (bad.length) throw new Error(`[viralshorts-seo] dist/ thiếu hoặc rỗng: ${bad.join(', ')}`)
    },

    configureServer(server) {
      const byUrl = new Map([...pages, notFoundPage()].map((p) => [p.path, p]))
      server.middlewares.use((req, res, next) => {
        const url = (req.url || '').split('?')[0]
        const page = byUrl.get(url)
        if (url === '/404' || !page) return next()
        res.setHeader('Content-Type', 'text/html; charset=utf-8')
        res.end(render(page))
        return undefined
      })
    },
  }
}
