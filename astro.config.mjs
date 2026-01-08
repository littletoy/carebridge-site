import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite'; // <--- NEW v4 Plugin
import sitemap from '@astrojs/sitemap';
import icon from 'astro-icon';
// import mdx from '@astrojs/mdx'; // Keep commented unless you installed MDX

export default defineConfig({
  site: 'https://carebridge-health.com',
  
  integrations: [
    sitemap(), 
    icon(),
    // mdx()
  ],

  vite: {
    plugins: [tailwindcss()], // <--- Where v4 lives now
  },
});