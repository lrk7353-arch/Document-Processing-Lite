// src/api/http.ts
// 使用基础路径，配合Vite代理
export async function postJSON<T>(path: string, body: unknown, init?: RequestInit) {
  const res = await fetch(`/api${path.startsWith('/') ? '' : '/'}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    credentials: 'include',
    body: JSON.stringify(body),
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} ${text}`);
  }
  return (await res.json()) as T;
}

/** —— 前端与后端约定：动作请求 —— */
export type UserAction =
  | { processId: string; actionType: 'confirm_result'; actionData?: object }
  | { processId: string; actionType: 'modify_field'; actionData: Record<string, any> }
  | { processId: string; actionType: 'cancel'; actionData?: object };

/** —— 后端返回的“事件响应体”最小形状：可直接喂给时间线 —— */
export type ActionResponse = {
  event: string;               // 例如 'action.result' | 'task.updated' ...
  type?: string;               // 例如 'ACK' | 'RESULT'
  timestamp?: number | string; // 可选
  progress?: number;           // 可选
  eventId?: string;            // 可选
  eventType?: string;          // 可选
  data?: Record<string, any>;  // 事件负载
};

/** —— 发起动作：返回“事件响应体” —— */
export function sendAction(a: UserAction) {
  return postJSON<ActionResponse>('/agent/action', a);
}
