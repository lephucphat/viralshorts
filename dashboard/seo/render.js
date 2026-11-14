/* Khung HTML tĩnh cho các trang build-time (pháp lý và 404). Không cần JavaScript để đọc.
 * Chỉ chạy trong Node lúc build / dev server, nên file này không được import vào src/. */

import { BRAND, SUPPORT_EMAIL } from './site.js'

export const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const CSS = `
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#1d1b17;--mut:#6b665c;--rule:#e4e0d6;--link:#8a5a12}
@media (prefers-color-scheme:dark){:root{--bg:#161512;--fg:#ece8df;--mut:#a39d90;--rule:#2d2a24;--link:#d9a54a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:46rem;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--rule)}
header.top .wrap{display:flex;align-items:center;justify-content:space-between;height:60px;gap:16px}
header.top nav{display:flex;gap:18px;font-size:.9375rem}
a{color:var(--link)}
.brand{display:flex;align-items:center;gap:10px;font-weight:600;color:var(--fg);text-decoration:none}
.brand img{border-radius:6px}
main{padding:32px 0 56px}
h1{font-size:2rem;line-height:1.2;margin:.2em 0 .4em}
h2{font-size:1.25rem;margin:2em 0 .4em}
.tldr{border:1px solid var(--rule);border-radius:10px;padding:4px 16px;margin:20px 0}
.meta{color:var(--mut);font-size:.875rem}
footer{border-top:1px solid var(--rule);color:var(--mut);font-size:.875rem;padding:24px 0}
footer nav{display:flex;flex-wrap:wrap;gap:6px 18px;margin-bottom:10px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid var(--rule);padding:6px 10px;text-align:left}
`

/** @param page {path,title,description,h1,body,tldr?,updated?,published?,noindex?}
 *  @param footerLinks [{path,h1}] trang pháp lý để liệt kê ở chân trang
 *  @param site        địa chỉ gốc tuyệt đối (rỗng thì bỏ canonical và og:url) */
export function renderPage(page, footerLinks, site) {
  const url = site ? `${site}${page.path}` : ''
  const date = page.updated || page.published
  const links = footerLinks.map((p) => `<a href="${p.path}">${esc(p.h1)}</a>`).join('')
  return `<!doctype html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(page.title)}</title>
<meta name="description" content="${esc(page.description)}">
<meta name="robots" content="${page.noindex ? 'noindex,follow' : 'index,follow'}">
${url ? `<link rel="canonical" href="${url}">\n<meta property="og:url" content="${url}">\n` : ''}<meta property="og:type" content="website">
<meta property="og:site_name" content="${BRAND}">
<meta property="og:locale" content="vi_VN">
<meta property="og:title" content="${esc(page.title)}">
<meta property="og:description" content="${esc(page.description)}">
${site ? `<meta property="og:image" content="${site}/logo-viralshorts.png">\n` : ''}<meta name="twitter:card" content="summary">
<link rel="icon" type="image/png" href="/logo-viralshorts.png">
<style>${CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="/"><img src="/logo-viralshorts.png" alt="" width="26" height="26">${BRAND}</a>
  <nav aria-label="Chính"><a href="/#/pricing">Bảng giá</a><a href="/help">Trợ giúp</a><a href="/#/login">Đăng nhập</a></nav>
</div></header>
<main><div class="wrap">
<h1>${esc(page.h1)}</h1>
${date ? `<p class="meta">Cập nhật: <time datetime="${esc(date)}">${esc(date)}</time></p>` : ''}
${page.tldr ? `<div class="tldr">${page.tldr.map((p) => `<p>${p}</p>`).join('')}</div>` : ''}
${page.body}
</div></main>
<footer><div class="wrap">
<nav aria-label="Pháp lý">${links}</nav>
<div>${BRAND} · <a href="mailto:${esc(SUPPORT_EMAIL)}">${esc(SUPPORT_EMAIL)}</a></div>
</div></footer>
</body>
</html>`
}
