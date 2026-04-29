/**
 * src/api/sseClient.ts
 * --------------------
 * 负责管理前端与后端（或 mockServer）的 SSE 连接。
 * 配合 agui.d.ts 中的类型定义使用。
 * 增强版：添加自动重连、错误处理和用户友好提示
 */

import type { AGUI } from "../types/agui";

/** SSE 连接实例 */
let eventSource: EventSource | null = null;
/** 重连计时器 */
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
/** 重连配置 */
const RECONNECT_CONFIG = {
  maxAttempts: 5,
  initialDelay: 1000, // 初始延迟1秒
  maxDelay: 10000, // 最大延迟10秒
  backoffFactor: 2 // 退避因子
};

/** 连接状态和上下文 */
interface SSEContext {
  url: string;
  onEvent: (event: AGUI.Event) => void;
  onStatusChange?: (status: AGUI.SSEConnectionStatus, error?: Error) => void;
  onUserNotification?: (message: string, type: "info" | "error" | "warning") => void;
  reconnectAttempts: number;
}

let sseContext: SSEContext | null = null;

/**
 * 显示用户通知
 */
function showUserNotification(message: string, type: "info" | "error" | "warning" = "info") {
  if (sseContext?.onUserNotification) {
    sseContext.onUserNotification(message, type);
  } else {
    // 降级处理：如果没有通知回调，使用console
    const prefix = type === "error" ? "❌" : type === "warning" ? "⚠️" : "ℹ️";
    console[type === "error" ? "error" : type === "warning" ? "warn" : "info"](`${prefix} ${message}`);
  }
}

/**
 * 计算重连延迟
 */
function calculateReconnectDelay(attempt: number): number {
  const delay = Math.min(
    RECONNECT_CONFIG.initialDelay * Math.pow(RECONNECT_CONFIG.backoffFactor, attempt - 1),
    RECONNECT_CONFIG.maxDelay
  );
  // 添加一些随机抖动，避免多客户端同时重连
  return delay * (0.9 + Math.random() * 0.2);
}

/**
 * 尝试重新连接
 */
function attemptReconnect() {
  if (!sseContext) return;
  
  // 检查是否已达到最大重连次数
  if (sseContext.reconnectAttempts >= RECONNECT_CONFIG.maxAttempts) {
    showUserNotification(
      `连接失败，已达到最大重连次数(${RECONNECT_CONFIG.maxAttempts})。请刷新页面重试。`, 
      "error"
    );
    sseContext.onStatusChange?.("error");
    return;
  }

  sseContext.reconnectAttempts++;
  const delay = calculateReconnectDelay(sseContext.reconnectAttempts);
  
  showUserNotification(
    `连接中断，${Math.round(delay / 1000)}秒后第${sseContext.reconnectAttempts}次尝试重连...`, 
    "warning"
  );
  
  reconnectTimer = setTimeout(() => {
    showUserNotification("正在尝试重新连接...", "info");
    sseContext!.onStatusChange?.("connecting");
    connectSSEInternal(sseContext!.url, sseContext!.onEvent, sseContext!.onStatusChange, sseContext!.onUserNotification);
  }, delay);
}

/**
 * 内部连接实现
 */
function connectSSEInternal(
  url: string,
  onEvent: (event: AGUI.Event) => void,
  onStatusChange?: (status: AGUI.SSEConnectionStatus, error?: Error) => void,
  onUserNotification?: (message: string, type: "info" | "error" | "warning") => void
): EventSource | null {
  // 清除现有的重连计时器
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  // 关闭现有连接
  if (eventSource) {
    try {
      eventSource.close();
    } catch (err) {
      console.error("关闭现有SSE连接时出错:", err);
    }
    eventSource = null;
  }

  try {
    eventSource = new EventSource(url);
    showUserNotification("正在建立连接...", "info");
    onStatusChange?.("connecting");

    eventSource.onopen = () => {
      showUserNotification("连接成功", "info");
      onStatusChange?.("open");
      // 重置重连计数
      if (sseContext) {
        sseContext.reconnectAttempts = 0;
      }
    };

    eventSource.onmessage = (msg: MessageEvent) => {
      try {
        // 每条消息是字符串，要先反序列化
        const raw: AGUI.SSEMessage = {
          data: msg.data,
          id: (msg as any).lastEventId,
          event: (msg as any).type,
        };

        const parsed = JSON.parse(raw.data) as AGUI.Event;
        onEvent(parsed);
      } catch (err) {
        const errorMessage = `数据解析失败: ${err instanceof Error ? err.message : String(err)}`;
        showUserNotification(errorMessage, "error");
        console.error("❌ SSE 数据解析失败:", err);
      }
    };

    eventSource.onerror = (err) => {
      const error = err instanceof Error ? err : new Error(String(err));
      const errorMessage = `连接异常: ${error.message || "未知错误"}`;
      showUserNotification(errorMessage, "error");
      console.error("⚠️ SSE 连接异常:", err);
      
      onStatusChange?.("error", error);
      
      // 清理资源
      try {
        eventSource?.close();
      } catch (closeErr) {
        console.error("关闭异常SSE连接时出错:", closeErr);
      }
      eventSource = null;
      onStatusChange?.("closed", error);
      
      // 尝试自动重连
      attemptReconnect();
    };

    return eventSource;
  } catch (err) {
    const error = err as Error;
    const errorMessage = `创建连接失败: ${error.message || "未知错误"}`;
    showUserNotification(errorMessage, "error");
    console.error("❌ SSE 连接创建失败:", err);
    onStatusChange?.("error", error);
    onStatusChange?.("error", error);
    return null;
  }
}

/**
 * 建立 SSE 连接
 * @param url SSE 地址（例如 http://localhost:3000/sse）
 * @param onEvent 收到事件时的回调
 * @param onStatusChange 可选，连接状态变化时的回调
 * @param onUserNotification 可选，用户通知回调
 */
export function connectSSE(
  url: string,
  onEvent: (event: AGUI.Event) => void,
  onStatusChange?: (status: AGUI.SSEConnectionStatus, error?: Error) => void,
  onUserNotification?: (message: string, type: "info" | "error" | "warning") => void
) {
  // 保存上下文
  sseContext = {
    url,
    onEvent,
    onStatusChange,
    onUserNotification,
    reconnectAttempts: 0
  };

  return connectSSEInternal(url, onEvent, onStatusChange, onUserNotification);
}

/**
 * 主动断开 SSE 连接
 * @param showNotification 是否显示通知
 */
export function disconnectSSE(showNotification: boolean = true) {
  // 清除重连计时器
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  // 关闭连接
  if (eventSource) {
    try {
      eventSource.close();
      eventSource = null;
      if (showNotification) {
        showUserNotification("连接已断开", "info");
      }
    } catch (err) {
      console.error("关闭SSE连接时出错:", err);
    }
  }

  // 重置上下文
  if (sseContext) {
    sseContext.onStatusChange?.("closed");
    sseContext = null;
  }
}

/**
 * 获取当前连接状态
 */
export function getConnectionStatus(): AGUI.SSEConnectionStatus {
  if (!eventSource) {
    return "closed";
  }
  
  // EventSource.readyState: 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
  switch (eventSource.readyState) {
    case EventSource.CONNECTING:
      return "connecting";
    case EventSource.OPEN:
      return "open";
    case EventSource.CLOSED:
      return "closed";
    default:
      return "closed";
  }
}
