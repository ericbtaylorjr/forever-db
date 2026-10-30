import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { config } from './src/config.ts';

/**
 * GitHub Pages can't set response headers, so the CSP ships as a <meta> tag (build only: the dev server injects an
 * HMR websocket and inline scripts). Everything is first-party except spell/item icons, which load from `config.iconHost`.
 * `style-src` needs 'unsafe-inline' for the few inline style attributes (quality colours, bar widths).
 */
const csp = (): Plugin => ({
  name: 'csp-meta',
  apply: 'build',
  transformIndexHtml: () => [
    {
      tag: 'meta',
      attrs: {
        'http-equiv': 'Content-Security-Policy',
        content: [
          "default-src 'self'",
          "script-src 'self'",
          "style-src 'self' 'unsafe-inline'",
          `img-src 'self' data: ${new URL(config.iconUrl('x')).origin}`,
          "connect-src 'self'",
          "base-uri 'self'",
          "form-action 'none'",
        ].join('; '),
      },
      injectTo: 'head-prepend',
    },
  ],
});

// A relative base lets the same build work at https://<user>.github.io/forever-db/ and on a custom domain.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss(), csp()],
  build: { target: 'es2022', sourcemap: false },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
