// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://heymeld.com',
  trailingSlash: 'never',
  integrations: [
    sitemap({
      // Only pages we actually want in search engines
      filter: (page) => !page.includes('/_'),
      changefreq: 'weekly',
      priority: 0.7,
    }),
  ],
  build: {
    // Clean URLs — /privacy not /privacy.html
    format: 'file',
    inlineStylesheets: 'auto',
  },
  // Astro ships zero JS by default. Any `<script>` we write is hydrated per-island.
  prefetch: {
    defaultStrategy: 'viewport',
  },
  // Default Vite CSS handling (esbuild minifier). Keeps deps small — no
  // lightningcss requirement.
});
