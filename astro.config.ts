import { defineConfig } from 'astro/config';

// Where the build is served. Defaults to production (OVH, at the domain root);
// the dev deploy to GitHub Pages sets both (.github/workflows/deploy-dev.yml).
const site = process.env.SITE_URL || 'https://aaastrategy.eu';
const base = (process.env.BASE_PATH || '/').replace(/\/?$/, '/');

export default defineConfig({
  site,
  base,
  vite: {
    server: {
      allowedHosts: ['aaa.tierney.one'],
    },
  },
});
