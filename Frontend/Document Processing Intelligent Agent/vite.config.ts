// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 统一API代理配置
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // 为SSE长连接添加特殊配置
        ws: true,
        configure: (proxy, _options) => {
          // 确保代理不会过早关闭连接
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, _req, _res) => {
            // 确保为SSE请求设置正确的头部
            if (_req.url?.includes('/api/agent/stream')) {
              proxyReq.setHeader('Accept', 'text/event-stream');
              proxyReq.setHeader('Cache-Control', 'no-cache');
            }
          });
        },
      },
    },
  },
});
