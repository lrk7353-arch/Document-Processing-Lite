// src/config.ts
export type SourceKey = 'backend' | 'mock' | 'hybrid';

type PartialConfig = {
  apiBase?: string;
  sseUrl?: string;
  defaultSource?: SourceKey;
  sseTaskParam?: string;
  bearerToken?: string;
  extraHeaders?: Record<string, string>;
};

declare global {
  interface Window { __APP_CONFIG__?: PartialConfig }
}

const env = import.meta.env as Record<string, string | undefined>;

function pick(...keys: string[]): string | undefined {
  for (const k of keys) {
    const v = env[k];
    if (typeof v === 'string' && v.trim()) return v.trim();
  }
  return undefined;
}

function pickBool(...keys: string[]): boolean | undefined {
  const v = pick(...keys);
  if (v == null) return undefined;
  return /^(1|true|yes)$/i.test(v);
}

function trimEndSlash(s?: string | null) {
  return (s ?? '').replace(/\/+$/, '');
}

export const MODE = env.MODE ?? 'development';
export const IS_DEV = MODE === 'development';
export const IS_PROD = MODE === 'production';

export const CONFIG = {
  apiBase: trimEndSlash(
    pick('VITE_API_URL', 'VITE_API_BASE', 'AG_API_BASE', 'REACT_APP_API_BASE', 'API_BASE', 'BACKEND_BASE_URL')
  ) || (IS_DEV ? 'http://localhost:8000' : ''),
  sseUrl: trimEndSlash(
    pick('VITE_SSE_URL', 'AG_SSE_URL', 'REACT_APP_SSE_URL', 'SSE_URL')
  ) || (IS_DEV ? 'http://localhost:8000/api/agent/stream' : ''),
  defaultSource: 'backend',
  sseTaskParam: pick('VITE_SSE_TASK_PARAM', 'AG_SSE_TASK_PARAM', 'SSE_TASK_PARAM') ?? 'processId',
  bearerToken: 'dev-token-for-testing', // 开发环境使用固定token
  extraHeaders: (() => {
    const raw = pick('VITE_EXTRA_HEADERS','AG_EXTRA_HEADERS');
    if (!raw) return undefined;
    try { return JSON.parse(raw) as Record<string,string>; } catch { return undefined; }
  })(),
} as const;

export function resolveApiUrl(path = '') {
  const base = CONFIG.apiBase || '';
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}

export function resolveSseUrl(taskId: string, params?: Record<string, string | number | boolean>) {
  // 与axiosInstance保持一致，使用绝对路径指向后端服务
  const base = IS_DEV ? 'http://localhost:8000/api/agent/stream' : (CONFIG.sseUrl || (CONFIG.apiBase ? `${CONFIG.apiBase}/api/agent/stream` : '/api/agent/stream'));
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
  const u = new URL(base);
  let taskKey = CONFIG.sseTaskParam || 'processId';
  if (typeof window !== 'undefined' && window.__APP_CONFIG__?.sseTaskParam) {
    taskKey = window.__APP_CONFIG__!.sseTaskParam!;
  }
  u.searchParams.set(taskKey, String(taskId));
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      u.searchParams.set(k, typeof v === 'boolean' ? String(v) : String(v));
    }
  }
  return u.toString();
}

export function authHeaders(): Record<string,string> | undefined {
  const hdrs: Record<string,string> = {};
  if (typeof window !== 'undefined') {
    const localStorageToken = localStorage.getItem('accessToken');
    if (localStorageToken) {
      hdrs['Authorization'] = `Bearer ${localStorageToken}`;
    }
  }
  if (!hdrs['Authorization'] && CONFIG.bearerToken) {
    hdrs['Authorization'] = `Bearer ${CONFIG.bearerToken}`;
  }
  if (CONFIG.extraHeaders) Object.assign(hdrs, CONFIG.extraHeaders);
  if (typeof window !== 'undefined' && window.__APP_CONFIG__) {
    const o = window.__APP_CONFIG__!;
    if (o.bearerToken) hdrs['Authorization'] = `Bearer ${o.bearerToken}`;
    if (o.extraHeaders) Object.assign(hdrs, o.extraHeaders);
  }
  return Object.keys(hdrs).length ? hdrs : undefined;
}

export function logConfigSummary() {
  if (!IS_DEV) return;
  console.table({
    MODE,
    apiBase: CONFIG.apiBase,
    sseUrl: CONFIG.sseUrl,
    defaultSource: CONFIG.defaultSource,
    sseTaskParam: CONFIG.sseTaskParam,
    bearerToken: CONFIG.bearerToken ? '*** set ***' : '(empty)',
    extraHeaders: CONFIG.extraHeaders ? JSON.stringify(CONFIG.extraHeaders) : '(none)',
  });
}
