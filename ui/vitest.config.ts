import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    setupFiles: "./vitest.setup.ts",
    // Reduce flakiness in CI/Windows: use threads instead of forks to avoid зависания раннера
    pool: "threads",
    fileParallelism: false,
    isolate: true,
    testTimeout: 10000,
    hookTimeout: 10000,
    reporters: ["basic"],
  }
});
