import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { loadEnv } from "vite";

const workspaceRoot = fileURLToPath(new URL("..", import.meta.url));
const workspaceEnv = loadEnv("development", workspaceRoot, "");
for (const name of ["DEFAULT_ADMIN_EMAIL", "DEFAULT_ADMIN_PASSWORD"] as const) {
  process.env[name] ??= workspaceEnv[name];
}

const liveBaseUrl = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  failOnFlakyTests: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  // Lazy route chunks can approach the 5 s Playwright default during a cold,
  // fully parallel Firefox start. Keep assertions deterministic without
  // relaxing the independent navigation and test timeouts.
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["html", { open: "never" }], ["github"]] : "list",
  use: {
    baseURL: liveBaseUrl ?? "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: liveBaseUrl
    ? undefined
    : {
        command:
          "pnpm build && pnpm exec vite preview --host 127.0.0.1 --port 4173",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
