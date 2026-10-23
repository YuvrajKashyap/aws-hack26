import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// This app is served behind the code-editor port proxy (and CloudFront) under
// the sub-path `/ports/5173/`. The proxy STRIPS that prefix before forwarding
// to Vite (http-proxy `ignorePath: true`), while the browser still addresses
// everything under the prefix.
//
// To satisfy both sides:
//   1. `base` makes Vite emit asset/module URLs WITH the prefix, so the browser
//      requests `/ports/5173/@vite/client` (which the proxy can route).
//   2. A middleware re-adds the prefix to incoming requests, because the proxy
//      delivers them stripped (`/@vite/client`) and Vite now serves under BASE.
const BASE = "/ports/5173/";
const PREFIX = BASE.slice(0, -1); // "/ports/5173"
const PROXY_HOST = "d2f0yfmr5qn033.cloudfront.net";

export default defineConfig({
  base: BASE,
  plugins: [
    react(),
    {
      name: "reprefix-stripped-proxy-path",
      configureServer(server) {
        server.middlewares.use(
          (req: { url?: string }, _res: unknown, next: () => void) => {
            if (req.url && !req.url.startsWith(BASE) && req.url !== PREFIX) {
              req.url = PREFIX + req.url;
            }
            next();
          },
        );
      },
    },
  ],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // HMR websocket must travel back through CloudFront on 443 (wss).
    hmr: {
      protocol: "wss",
      host: PROXY_HOST,
      clientPort: 443,
      path: BASE,
    },
  },
});
