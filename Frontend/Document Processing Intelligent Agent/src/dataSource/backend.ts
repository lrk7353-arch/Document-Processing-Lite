// src/datasource/backend.ts
import { connectSSE } from '../api/sseClient';
import { sendAction as postAction, type UserAction, type ActionResponse } from '../api/http';

/** —— inline 类型，避免依赖问题 —— */
type StreamHandle = { close: () => void };
type OnEvent = (e: any) => void;
interface DataSource {
  key: 'mock' | 'backend' | 'hybrid';
  start: (opts: {
    taskId: string;
    onEvent: OnEvent;
    onOpen?: () => void;
    onError?: (e: unknown) => void;
  }) => StreamHandle;
  sendAction: (a: UserAction) => Promise<ActionResponse>;
}

// ---- 环境变量兜底 ----
const API_BASE = (import.meta.env.VITE_API_BASE
  ?? import.meta.env.AG_API_BASE
  ?? import.meta.env.REACT_APP_API_BASE
  ?? '') as string;

const SSE_URL = (import.meta.env.VITE_SSE_URL
  ?? import.meta.env.AG_SSE_URL
  ?? (API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/agent/stream` : '/api/agent/stream')) as string;

const SSE_TASK_PARAM = (import.meta.env.VITE_SSE_TASK_PARAM
  ?? import.meta.env.AG_SSE_TASK_PARAM
  ?? 'processId') as string;

const BEARER = (import.meta.env.VITE_BEARER
  ?? import.meta.env.AG_BEARER
  ?? '') as string;

const EXTRA_HEADERS_RAW = (import.meta.env.VITE_EXTRA_HEADERS
  ?? import.meta.env.AG_EXTRA_HEADERS
  ?? '') as string;

function parseExtraHeaders(): Record<string, string> | undefined {
  if (!EXTRA_HEADERS_RAW) return undefined;
  try {
    const obj = JSON.parse(EXTRA_HEADERS_RAW);
    if (obj && typeof obj === 'object') return obj as Record<string, string>;
  } catch {}
  return undefined;
}

function authHeaders(): Record<string, string> | undefined {
  const h: Record<string, string> = {};
  if (BEARER) h['Authorization'] = `Bearer ${BEARER}`;
  const extra = parseExtraHeaders();
  if (extra) Object.assign(h, extra);
  return Object.keys(h).length ? h : undefined;
}

function buildSseUrl(taskId: string): string {
  try {
    const u = new URL(SSE_URL, window.location.origin);
    u.searchParams.set(SSE_TASK_PARAM, taskId);
    return u.toString();
  } catch {
    const sep = SSE_URL.includes('?') ? '&' : '?';
    return `${SSE_URL}${sep}${encodeURIComponent(SSE_TASK_PARAM)}=${encodeURIComponent(taskId)}`;
  }
}

// ---- DataSource 实现 ----
export const backendSource: DataSource = {
  key: 'backend',

  start: (opts) => {
    const { taskId, onEvent, onOpen, onError } = opts;
    const url = buildSseUrl(taskId);

    const handle = connectSSE(
      url,
      (payload: any) => onEvent(payload),
      {
        withCredentials: true,
        headers: authHeaders(),
        onOpen,
        onError,
        retry: { baseMs: 800, maxMs: 8000 },
      } as any
    );

    return { close() { (handle as any)?.close?.(); } };
  },

  // 直接把后端返回的事件响应体透传出去
  sendAction: (a: UserAction) => postAction(a),
};
