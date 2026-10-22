/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const api = process.env.YOMIKOE_API ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/documents': api,
      '/audio': api,
      '/voices': api,
      '/settings': api,
      '/pronunciations': api,
    },
  },
  test: {
    include: ['tests/unit/**/*.test.ts'],
  },
})
