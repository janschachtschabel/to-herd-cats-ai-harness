// The browser tests of live editing (review M2 R18): the real app (role all: API, SPA
// and collab process) on a scratch database, started by `global-setup.mjs`.
//
// - HERD_E2E_ADMIN_URL: a PostgreSQL database to create and drop the scratch database
//   from (default postgresql://herd:herd@localhost:5433/herd_test).
// - HERD_E2E_PORT: the public port (18080); the internal and collab ports follow it.
// - PLAYWRIGHT_CHROMIUM_EXECUTABLE: a Chromium to use instead of Playwright's own
//   (`npx playwright install chromium`), e.g. one installed with the system.
// The SPA must be built first (`cd frontend && npm run build`).
import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.HERD_E2E_PORT || 18080);
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;

export default defineConfig({
  testDir: "./tests",
  globalSetup: "./global-setup.mjs",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "de-DE",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } },
    },
  ],
});
