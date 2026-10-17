import { execFileSync } from 'node:child_process'
import { defineConfig, devices } from '@playwright/test'

// The e2e API (FakeBackend, temp data dir) listens on a free port chosen once in the runner
// process; workers inherit it through the environment. Never 8765 (the user's server, D21).
if (!process.env.HEARNARRO_E2E_API_PORT) {
  process.env.HEARNARRO_E2E_API_PORT = execFileSync(process.execPath, [
    '-e',
    "const s=require('net').createServer();s.listen(0,'127.0.0.1',()=>{console.log(s.address().port);s.close()})",
  ])
    .toString()
    .trim()
}
export const E2E_API_BASE = `http://127.0.0.1:${process.env.HEARNARRO_E2E_API_PORT}`

export default defineConfig({
  testDir: 'tests/e2e',
  reporter: 'list',
  // One worker: the worker-scoped API fixture binds the single port above, and audio timing
  // probes must not compete for CPU.
  workers: 1,
  fullyParallel: false,
  use: { baseURL: 'http://127.0.0.1:5173', actionTimeout: 5_000 },
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort --host 127.0.0.1',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: false,
    // vite.config.ts proxies /documents, /audio, /voices to HEARNARRO_API.
    env: { HEARNARRO_API: E2E_API_BASE },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: { args: ['--autoplay-policy=no-user-gesture-required'] },
      },
    },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
})
