import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import seo from './vite-plugin-seo.js'

// Backend target for the dev proxy. Defaults to the docker-compose service
// name; set VITE_PROXY_TARGET=http://localhost:8000 to run the dev server on
// the host against a backend reachable at localhost (no CORS, same-origin).
const backend = process.env.VITE_PROXY_TARGET || 'http://backend:8000'
const renderer = process.env.VITE_RENDER_TARGET || 'http://renderer:3100'

// https://vitejs.dev/config/
export default defineConfig({
  // vite-plugin-seo.js emits the static legal pages (/terms, /privacy, /refunds, /legal-notice,
  // /report-content), 404.html, robots.txt and, with SITE_URL set, sitemap.xml and llms.txt.
  // It fails the build when one of the legal pages is missing.
  plugins: [react(), seo()],
  server: {
    allowedHosts: [
      // Extra hostnames the dev server answers to, comma-separated in VITE_ALLOWED_HOSTS.
      ...(process.env.VITE_ALLOWED_HOSTS || '').split(',').map((h) => h.trim()).filter(Boolean),
    ],
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/videos': { target: backend, changeOrigin: true },
      '/thumbnails': { target: backend, changeOrigin: true },
      '/gallery': { target: backend, changeOrigin: true },
      '/video': { target: backend, changeOrigin: true },
      '/render': { target: renderer, changeOrigin: true },
    }
  }
})
