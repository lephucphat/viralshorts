/* Trang tĩnh của trung tâm trợ giúp và lịch sử thay đổi, sinh lúc build (chỉ chạy trong Node).
 * Cùng dạng đối tượng với seo/legal.js để vite-plugin-seo.js phát ra bằng renderPage().
 *
 * Địa chỉ hỗ trợ lấy từ biến môi trường SUPPORT_EMAIL của lượt build (giống phía máy chủ,
 * studio/payments/api.py). Không đặt thì in chỗ giữ chỗ của seo/site.js, như các trang pháp lý. */

import { BRAND, PUBLISHED, SUPPORT_EMAIL } from './site.js'
import { HELP_ARTICLES, HELP_UPDATED, blocksToHtml } from './help.js'
import { CHANGELOG } from './changelog.js'
import { esc } from './render.js'

export function helpPages(supportEmail = '') {
  const mail = (supportEmail || '').trim() || SUPPORT_EMAIL
  const contact = `<h2>Vẫn cần giúp?</h2>
<p>Gửi email tới <a href="mailto:${esc(mail)}">${esc(mail)}</a>, kèm email tài khoản và mô tả điều bạn thấy.</p>`

  const index = {
    path: '/help',
    title: `Trung tâm trợ giúp | ${BRAND}`,
    description: 'Hướng dẫn ViralShorts: bắt đầu, credit, phụ đề, đăng bài và lịch đăng, thanh toán, xoá tài khoản.',
    h1: 'Trung tâm trợ giúp',
    published: PUBLISHED,
    updated: HELP_UPDATED,
    body: `<ul>${HELP_ARTICLES.map((a) => `<li><a href="/help/${a.slug}">${esc(a.title)}</a><br>${esc(a.summary)}</li>`).join('')}</ul>
<p><a href="/changelog">Lịch sử thay đổi</a></p>
${contact}`,
  }

  const articles = HELP_ARTICLES.map((a) => ({
    path: `/help/${a.slug}`,
    title: `${a.title} | ${BRAND}`,
    description: a.summary,
    h1: a.title,
    published: PUBLISHED,
    updated: HELP_UPDATED,
    body: `${blocksToHtml(a.blocks, esc)}
<p><a href="/help">← Tất cả bài trợ giúp</a></p>
${contact}`,
  }))

  const changelog = {
    path: '/changelog',
    title: `Lịch sử thay đổi | ${BRAND}`,
    description: 'Những thay đổi lớn gần đây của ViralShorts.',
    h1: 'Lịch sử thay đổi',
    published: PUBLISHED,
    updated: CHANGELOG[0]?.date || PUBLISHED,
    body: CHANGELOG.map((c) => `<h2>${esc(c.title)}</h2>
<p class="meta"><time datetime="${esc(c.date)}">${esc(c.date)}</time></p>
<ul>${c.items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>`).join('\n'),
  }

  return [index, ...articles, changelog]
}
