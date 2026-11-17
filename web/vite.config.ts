// Vite's build settings. Vite runs the dev server (`npm run dev`) and builds
// the site for Vercel (`npm run build`); Vitest reads this file too.
//
// Key decision: kept at the defaults plus the React plugin (JSX and fast
// refresh while developing). There's nothing custom to maintain.

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
