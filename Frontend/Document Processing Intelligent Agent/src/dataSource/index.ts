// src/datasource/index.ts
export type StreamHandle = { close: () => void };
export type OnEvent = (e: any) => void;

export interface DataSource {
  key: 'mock' | 'backend' | 'hybrid';
  start: (opts: {
    taskId: string;
    onEvent: OnEvent;
    onOpen?: () => void;
    onError?: (e: unknown) => void;
  }) => StreamHandle;

  // 现在显式返回后端的事件响应体
  sendAction: (a: import('../api/http').UserAction) => Promise<import('../api/http').ActionResponse>;
}
