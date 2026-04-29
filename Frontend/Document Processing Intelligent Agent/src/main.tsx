import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import "./index.css";

async function prepareApp() {
  document.title = "DocSmart AI - 外贸单证识别系统";

  // 禁用模拟功能，使用真实后端服务

  // 禁用模拟功能，使用真实后端
  (window as any).__USE_MOCK__ = false;
  console.log("✅ 使用真实后端服务");
  
  // 清理可能的模拟服务工作线程
  if ("serviceWorker" in navigator) {
    try {
      const regs = await navigator.serviceWorker.getRegistrations();
      for (const reg of regs) {
        const url = reg.active?.scriptURL || reg.installing?.scriptURL || reg.waiting?.scriptURL;
        if (url && url.includes("mockServiceWorker")) await reg.unregister();
      }
    } catch (err) {
      console.warn("清理Service Worker时出错:", err);
    }
  }
  if ("caches" in window) {
    try {
      const keys = await caches.keys();
      for (const k of keys) if (k.toLowerCase().includes("msw")) await caches.delete(k);
    } catch (err) {
      console.warn("清理缓存时出错:", err);
    }
  }

  const root = document.getElementById("root");
  if (!root) return console.error("❌ Root 未找到");

  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
}

prepareApp();
