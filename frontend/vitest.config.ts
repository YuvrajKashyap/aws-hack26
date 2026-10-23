import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Test-only config: uses the React plugin for JSX/TSX transforms but omits the
// dev-server proxy middleware from vite.config.ts (irrelevant under jsdom).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
