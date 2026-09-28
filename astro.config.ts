import { defineConfig } from 'astro/config';

export default defineConfig({
    vite: {
    server: {
      allowedHosts: ['aaa.tierney.one'],
    },
  },
});
