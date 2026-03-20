import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// When deploying to GitHub Pages, set the VITE_BASE_PATH env variable
// to match your repository name: e.g. /pdf-to-llm-context/
// This is set automatically by the GitHub Actions workflow.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH || '/',
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
