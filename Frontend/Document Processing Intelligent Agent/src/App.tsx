// src/App.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

// 组件
import ChatInterface from "./components/ChatInterface";
import type { StageKey } from "./components/StageStepper";

// 工具与API
import api from "./axiosInstance";
import { resolveSseUrl, IS_DEV, CONFIG } from "./config";
import { ChatMessage } from "./types/chat"; // 引入我们新建的类型

// ----------------------------------------------------------------------------
// 工具函数 (保持不变)
// ----------------------------------------------------------------------------
const clamp = (n: number) => Math.max(0, Math.min(100, n));
const lastBy = <T,>(arr: T[], pred: (t: T) => boolean): T | undefined =>
  [...arr].reverse().find(pred);
const t = (ts: number) => new Date(ts).toLocaleTimeString();

function parseSseRaw(raw: any) {
  if (typeof raw !== 'string') return { event: 'unknown', raw: '', timestamp: Date.now(), data: {} };
  const lines = raw.split('\n');
  let evt = 'message';
  const dataParts: string[] = [];
  for (const line of lines) {
    if (line.startsWith('event:')) evt = line.replace(/^event:\s?/, '').trim();
    else if (line.startsWith('data:')) dataParts.push(line.replace(/^data:\s?/, ''));
  }
  const dataStr = dataParts.join('');
  let payload: any = {};
  try { payload = JSON.parse(dataStr); } catch { payload = { raw: dataStr }; }
  if (!payload.event) payload.event = evt;
  if (!payload.timestamp) payload.timestamp = Date.now();
  return payload;
}

// ... adaptAguiEvent 函数保持不变，为了节省篇幅，这里假设你保留原来的 adaptAguiEvent ...
// ... normalizeIncoming 函数保持不变 ...
// (请确保 adaptAguiEvent 和 normalizeIncoming 函数在你的代码中存在，这部分逻辑完全复用原来的即可)

function adaptAguiEvent(payload: any): { event: string; raw: string; data: any } {
  const rawName =
    payload?.raw ||
    payload?.event ||
    payload?.action ||
    payload?.actionName ||
    payload?.name ||
    payload?.type ||
    "unknown";

  const rawStr = String(rawName);
  const s = rawStr.toLowerCase().replace(/\s+/g, "");
  const d = { ...(payload?.data || {}) };
  if (!d.extractedFields) {
    const aliases = (payload?.extractedFields || d.extracted_fields || d.fields || d.results || []);
    if (Array.isArray(aliases)) d.extractedFields = aliases;
  }
  if (!d.processId) d.processId = payload?.processId || d.process_id || d.pid;
  if (!d.ruleResults && (payload?.ruleResults || d.rules)) d.ruleResults = payload?.ruleResults || d.rules;
  if (!d.overallResult && (payload?.overallResult || d.result)) d.overallResult = payload?.overallResult || d.result;
  const prog = d.progress ?? payload?.progress ?? payload?.percent ?? payload?.ratio ?? undefined;
  if (prog != null) d.progress = Math.max(0, Math.min(100, Number(prog)));

  const has = (kw: string) => s.includes(kw);

  if (payload?.type === 'system') {
    if (d?.final) return { event: 'thinking.final', raw: 'THINKING/FINAL', data: d };
    if (d?.step) return { event: 'thinking.step', raw: `THINKING/${String(d.step).toUpperCase()}`, data: d };
  }

  if (s === "heartbeat" || has("heartbeat")) {
    return { event: "heartbeat", raw: "HEARTBEAT", data: d };
  }
  if (has("run") && (has("start") || has("begin"))) {
    return { event: "file.upload.start", raw: "RUN/START", data: d };
  }
  if (has("upload")) {
    if (has("progress")) return { event: "file.upload.progress", raw: "UPLOAD/PROGRESS", data: d };
    if (has("complete") || has("done") || has("finish")) return { event: "file.upload.complete", raw: "UPLOAD/COMPLETE", data: d };
    if (has("start") || has("begin")) return { event: "file.upload.start", raw: "UPLOAD/START", data: d };
  }
  if (has("parse") || (has("process") && has("file"))) {
    if (has("progress")) return { event: "file.process.progress", raw: "PARSE/PROGRESS", data: d };
    if (has("complete") || has("done") || has("finish")) return { event: "file.process.complete", raw: "PARSE/COMPLETE", data: d };
    if (has("start") || has("begin")) return { event: "file.process.start", raw: "PARSE/START", data: d };
  }
  if (has("model")) {
    if (has("progress")) return { event: "model.process.progress", raw: "MODEL/PROGRESS", data: d };
    if (has("extract") && (has("complete") || has("done") || has("finish"))) return { event: "model.extract.complete", raw: "MODEL/COMPLETE", data: d };
    if (has("complete") || has("done") || has("finish")) return { event: "model.process.complete", raw: "MODEL/COMPLETE", data: d };
    if (has("start") || has("begin")) return { event: "model.process.start", raw: "MODEL/START", data: d };
  }
  if (has("compliance") || has("check")) {
    if (has("progress")) return { event: "compliance.check.progress", raw: "COMPLIANCE/PROGRESS", data: d };
    if (has("complete") || has("done") || has("finish")) return { event: "compliance.check.complete", raw: "COMPLIANCE/COMPLETE", data: d };
    if (has("start") || has("begin")) return { event: "compliance.check.start", raw: "COMPLIANCE/START", data: d };
  }
  if (has("task") && (has("complete") || has("done") || has("finish"))) {
    return { event: "task.complete", raw: "TASK/COMPLETE", data: d };
  }
  if (has("connect") || has("connection") || s === "connection_error") {
    if (has("error") || has("fail") || s === "connection_error") return { event: "connection.error", raw: "CONNECT/ERROR", data: d };
    if (has("start") || has("init") || has("established")) return { event: "connection.established", raw: "CONNECT/ESTABLISHED", data: d };
    if (has("close") || has("end")) return { event: "connection.closed", raw: "CONNECT/CLOSED", data: d };
    return { event: "connection.connected", raw: "CONNECT/CONNECTED", data: d };
  }
  if (d.progress != null) {
    if (has("upload")) return { event: "file.upload.progress", raw: "UPLOAD/PROGRESS", data: d };
    if (has("parse") || (has("process") && has("file"))) return { event: "file.process.progress", raw: "PARSE/PROGRESS", data: d };
    if (has("model")) return { event: "model.process.progress", raw: "MODEL/PROGRESS", data: d };
    if (has("compliance") || has("check")) return { event: "compliance.check.progress", raw: "COMPLIANCE/PROGRESS", data: d };
    const cs = String(d.currentStage || "").toLowerCase();
    if (cs.includes("upload")) return { event: "file.upload.progress", raw: "UPLOAD/PROGRESS", data: d };
    if (cs.includes("parse") || cs.includes("process")) return { event: "file.process.progress", raw: "PARSE/PROGRESS", data: d };
    if (cs.includes("model") || cs.includes("extract")) return { event: "model.process.progress", raw: "MODEL/PROGRESS", data: d };
    if (cs.includes("compliance") || cs.includes("check")) return { event: "compliance.check.progress", raw: "COMPLIANCE/PROGRESS", data: d };
    return { event: "progress", raw: "PROGRESS", data: d };
  }
  return { event: "unknown", raw: rawStr.toUpperCase(), data: d };
}

function aguiLabelFor(internalEvent: string): string {
  if (internalEvent.startsWith("connection.")) {
    if (internalEvent.endsWith(".established")) return "CONNECT/ESTABLISHED";
    if (internalEvent.endsWith(".error")) return "CONNECT/ERROR";
    if (internalEvent.endsWith(".closed")) return "CONNECT/CLOSED";
    if (internalEvent.endsWith(".connected")) return "CONNECT/CONNECTED";
  }
  if (internalEvent.startsWith("file.upload.")) {
    if (internalEvent.endsWith(".start")) return "UPLOAD/START";
    if (internalEvent.endsWith(".progress")) return "UPLOAD/PROGRESS";
    if (internalEvent.endsWith(".complete")) return "UPLOAD/COMPLETE";
  }
  if (internalEvent.startsWith("file.process.")) {
    if (internalEvent.endsWith(".start")) return "PARSE/START";
    if (internalEvent.endsWith(".progress")) return "PARSE/PROGRESS";
    if (internalEvent.endsWith(".complete")) return "PARSE/COMPLETE";
  }
  if (internalEvent.startsWith("model.")) {
    if (internalEvent.endsWith(".start")) return "MODEL/START";
    if (internalEvent.endsWith(".progress")) return "MODEL/PROGRESS";
    if (internalEvent.includes("extract.complete")) return "MODEL/COMPLETE";
    if (internalEvent.endsWith(".complete")) return "MODEL/COMPLETE";
  }
  if (internalEvent.startsWith("compliance.check.")) {
    if (internalEvent.endsWith(".start")) return "COMPLIANCE/START";
    if (internalEvent.endsWith(".progress")) return "COMPLIANCE/PROGRESS";
    if (internalEvent.endsWith(".complete")) return "COMPLIANCE/COMPLETE";
  }
  if (internalEvent === "task.complete") return "TASK/COMPLETE";
  return internalEvent.toUpperCase();
}

const normalizeIncoming = (payload: any): EventData => {
  const { event, raw, data } = adaptAguiEvent(payload);
  return {
    event,
    raw,
    type: payload?.type ?? payload?.status ?? "progress",
    timestamp: typeof payload?.timestamp === "number" ? payload.timestamp : Date.now(),
    data,
  };
};

export interface EventData {
    event: string;
    raw?: string;
    type: string;
    timestamp: number;
    data: any;
}


export default function App() {
  const navigate = useNavigate();
  
  /** ===== 状态管理 ===== */
  const [events, setEvents] = useState<EventData[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  
  // SSE 控制
  const sseCtl = useRef<{ abort?: () => void } | null>(null);

  // 上传文件引用 (用于结果展示)
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | undefined>();

  // 核心：聊天消息列表
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "init-1",
      role: "assistant",
      type: "text",
      content: "👋 你好！我是 DocSmart 智能单证分析 Agent。\n\n请上传您的 **外贸合同、发票或装箱单**，我将为您执行：\n1. OCR 智能结构化提取\n2. 贸易合规性风险审查\n3. 生成专业分析报告",
      timestamp: Date.now()
    }
  ]);

  // 进度控制
  const [displayStage, setDisplayStage] = useState<StageKey>('idle');
  const [displayPercent, setDisplayPercent] = useState<number>(0);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [lastEventAt, setLastEventAt] = useState<number>(Date.now());
  const [pendingText, setPendingText] = useState<string>("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  /** ===== 数据计算 (复用原有逻辑) ===== */
  const extracted = useMemo(
    () =>
      (lastBy(events, (e) => e.event === "model.extract.complete")?.data?.extractedFields ||
        lastBy(events, (e) => e.event === "task.complete")?.data?.extractedFields ||
        []) as any[],
    [events]
  );

  const complianceForPanel = useMemo(() => {
    const e =
      lastBy(events, (x) => x.event === "result.final") ||
      lastBy(events, (x) => x.event === "result.summary") ||
      lastBy(events, (x) => x.event === "compliance.check.complete") ||
      lastBy(events, (x) => x.event === "task.complete");

    if (!e) return undefined;
    
    // ... 这里复用你原来的 complianceForPanel 逻辑，提取 overallResult, items 等 ...
    // 为了代码简洁，这里做简化映射，请确保你原来的逻辑在这里
    return {
        overallResult: e.data?.overallResult || e.data?.complianceResult?.overallResult,
        items: e.data?.ruleResults || [], // 简化处理，实际请用你原来的 map 逻辑
        overallRiskLevel: e.data?.overallRiskLevel,
        riskAlerts: e.data?.riskAlerts
    };
  }, [events]);

  const lastFileMeta = useMemo(() => {
    const anyFileEvt = lastBy(events, (e) => e.event.startsWith("file."))?.data || {};
    return anyFileEvt;
  }, [events]);

  // 预览图处理
  useEffect(() => {
    if (currentFile) {
      const url = URL.createObjectURL(currentFile);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [currentFile]);

  /** ===== 核心逻辑：监听事件并驱动 Chat UI 更新 ===== */
  useEffect(() => {
    // 1. 根据 events 计算 displayStage 和 displayPercent (复用你原来的 switch case 逻辑)
    if (events.length > 0) {
      const lastEvent = events[events.length - 1];
      // ... 请保留你原来 useEffect 中 switch (lastEvent.event) 更新 displayStage 的所有逻辑 ...
      // 简单示例：
      if (lastEvent.event === 'file.upload.start') { setDisplayStage('uploading'); setDisplayPercent(20); }
      if (lastEvent.event === 'file.upload.complete') { setDisplayStage('uploaded'); setDisplayPercent(100); }
      if (lastEvent.event === 'file.process.start') { setDisplayStage('parsing'); setDisplayPercent(30); }
      if (lastEvent.event === 'model.extract.complete') { setDisplayStage('extracting'); setDisplayPercent(75); }
      if (lastEvent.event === 'compliance.check.complete') { setDisplayStage('completed'); setDisplayPercent(100); }
      // ... 等等
    }

    // 2. 同步状态到最后一条 Agent 消息
    setChatMessages(prev => {
      const lastMsg = prev[prev.length - 1];
      // 只有当最后一条是 Agent 且是 "agent-result" 类型时才更新
      if (lastMsg?.role === "assistant" && lastMsg.type === "agent-result") {
        
        const isCompleted = displayStage === "completed";
        
        // 如果已完成，构建结果数据
        let resultData = undefined;
        if (isCompleted) {
           resultData = {
             fileName: currentFile?.name || "未知文件",
             fileType: currentFile?.type || "unknown",
             fileSize: currentFile?.size,
             storagePath: lastFileMeta?.storagePath,
             md5: lastFileMeta?.md5,
             previewUrl: previewUrl,
             extractedFields: extracted,
             compliance: complianceForPanel,
           };
        }

        // 返回新的消息数组 (替换最后一条)
        const updatedMsg: ChatMessage = {
          ...lastMsg,
          agentState: {
            isThinking: !isCompleted,
            logs: logs.slice(-15), // 取最近日志
            progress: displayPercent,
            stage: displayStage
          },
          resultData: resultData || lastMsg.resultData // 如果算出来了就存进去
        };

        return [...prev.slice(0, -1), updatedMsg];
      }
      return prev;
    });
    if (events.length > 0) setLastEventAt(events[events.length - 1].timestamp || Date.now());
  }, [events, displayStage, displayPercent, logs, extracted, complianceForPanel, currentFile, previewUrl, lastFileMeta]);


  /** ===== 处理上传 ===== */
  async function handleFileUpload(f: File) {
    // 1. UI 立即响应：添加用户消息 + Agent 思考消息
    setCurrentFile(f);
    setEvents([]); 
    setLogs([]);
    setDisplayStage('uploading');
    setDisplayPercent(0);

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      type: "file-upload",
      content: "",
      timestamp: Date.now(),
      fileMeta: { name: f.name, size: f.size, type: f.type }
    };

    const agentMsg: ChatMessage = {
      id: "agent-" + Date.now(),
      role: "assistant",
      type: "agent-result",
      content: "",
      timestamp: Date.now(),
      agentState: {
        isThinking: true,
        logs: ["开始接收文件流...", "正在建立 SSE 实时通道..."],
        progress: 5,
        stage: "uploading"
      }
    };

    setChatMessages(prev => [...prev, userMsg, agentMsg]);

    // 2. 开始真实上传 (复用你原来的逻辑，删减UI状态设置，因为上面已经设置了)
    try {
      const token = await getAuthToken(); // 复用你原来的 getAuthToken
      if (!token) throw new Error("无法获取 Auth Token");

      const form = new FormData();
      form.append("file", f);
      form.append("docType", "invoice");

      setLogs(p => [...p, `${t(Date.now())} | NET | 开始上传文件...`]);
      
      const response = await api.post("/api/file/upload", form, {
        headers: { Authorization: `Bearer ${token}` },
      });

      const responseData = response || {} as any;
      const processId = responseData.data?.processId || responseData.processId;
      
      if (processId) {
        startSSE(String(processId), token); // 复用你原来的 startSSE
      } else {
        throw new Error("未返回 Process ID");
      }

    } catch (err: any) {
      setLogs(p => [...p, `${t(Date.now())} | ERROR | ${err.message}`]);
      // 可以在这里插入一条错误消息给 Agent
    }
  }

  async function handleSendText(text: string) {
    const now = Date.now();
    const userMsg: ChatMessage = { id: String(now), role: 'user', type: 'text', content: text, timestamp: now };
    const agentMsg: ChatMessage = { id: 'agent-' + now, role: 'assistant', type: 'agent-result', content: '', timestamp: now, agentState: { isThinking: true, logs: ["THINKING/RECEIVE | running", "THINKING/REASONING | running"], progress: 5, stage: 'idle' } };
    setChatMessages(prev => prev.concat([userMsg, agentMsg]));
    const sid = chatSessionId || `chat-${now}`;
    if (!chatSessionId) setChatSessionId(sid);
    const token = await getAuthToken();
    startSSE(sid, token || undefined);
    try {
      await api.post('/api/chat/send', { sessionId: sid, userText: text }, { headers: token ? { Authorization: `Bearer ${token}` } : undefined });
    } catch (e: any) {
      setLogs(p => p.concat([t(Date.now()) + ' | THINKING/ERROR | ' + (e?.message || String(e))]));
      setChatMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant' && last.type === 'agent-result') {
          const updated: ChatMessage = { ...last, agentState: { isThinking: false, logs: (last.agentState?.logs || []).concat(['THINKING/GENERATE | failed']), progress: 0, stage: 'idle' } };
          return prev.slice(0, -1).concat([updated]);
        }
        return prev;
      });
    }
  }

  function queueFiles(files: File[]) {
    setPendingFiles(prev => prev.concat(files));
  }

  function onSendAll() {
    const text = pendingText.trim();
    const files = [...pendingFiles];
    setPendingText("");
    setPendingFiles([]);
    if (text) handleSendText(text);
    files.forEach(f => handleFileUpload(f));
  }

  async function getAuthToken() {
    try {
      setLogs((p) => [...p, `${t(Date.now())} | AUTH/REQUEST | 开始请求访问令牌`]);
      if (IS_DEV) {
        setLogs((p) => [...p, `${t(Date.now())} | AUTH/DEV_MODE | 开发环境：使用开发令牌`]);
        const devToken = CONFIG.bearerToken || 'dev-token-for-testing';
        localStorage.setItem("accessToken", devToken);
        setLogs((p) => [...p, `${t(Date.now())} | AUTH/SAVE | 成功保存开发令牌`]);
        return devToken;
      }
      setLogs((p) => [...p, `${t(Date.now())} | AUTH/PROD_MODE | 生产环境：尝试获取令牌`]);
      return null;
    } catch (err: any) {
      const errorMsg = err.response ? `HTTP ${err.response.status}: ${JSON.stringify(err.response.data)}` : err.message;
      setLogs((p) => [...p, `${t(Date.now())} | AUTH/ERROR | 获取令牌失败: ${errorMsg}`]);
      return null;
    }
  }

  function startSSE(processId: string, token?: string) {
    stopSSE();
    var url = resolveSseUrl(processId, { docType: 'invoice' });
    setLogs(prev => [...prev, `${t(Date.now())} | SSE/INIT | 初始化SSE连接，processId: ${processId}`]);
    setLogs(prev => [...prev, `${t(Date.now())} | SSE/CONNECT | ${url}`]);
    sseCtl.current = { abort: function() { if (es) try { es.close(); } catch {} } } as any;

    const maxRetries = 5;
    let retryCount = 0;
    let reconnectTimeout: number | null = null;
    let es: EventSource | null = null;

    const reconnect = () => {
      if (!sseCtl.current) {
        setLogs(function(p) { return p.concat([t(Date.now()) + ' | SSE/RECONNECT/CANCELLED | SSE已停止，取消重连']); });
        return;
      }
      if (retryCount < maxRetries) {
        retryCount++;
        const baseDelay = 1000 * Math.pow(2, retryCount);
        const jitter = Math.random() * 1000;
        const delay = Math.min(baseDelay + jitter, 15000);
        setLogs(function(p) { return p.concat([t(Date.now()) + ` | SSE/RECONNECT/SCHEDULED | 将在 ${(delay/1000).toFixed(1)} 秒后进行第 ${retryCount} 次重连`]); });
        reconnectTimeout = window.setTimeout(() => {
          if (!sseCtl.current) return;
          setLogs(function(p) { return p.concat([t(Date.now()) + ' | SSE/RECONNECT/ATTEMPT | 尝试第 ' + retryCount + ' 次重连']); });
          try { executeSSEConnection(); } catch { reconnect(); }
        }, delay);
      } else {
        setLogs(function(p) { return p.concat([t(Date.now()) + ' | SSE/RECONNECT/FAILED | 达到最大重连次数 ' + maxRetries + '，放弃重连']); });
        const errorEvent = { event: "connection.error", raw: "CONNECT/ERROR", type: "error", timestamp: Date.now(), data: { status: "SSE重连失败", error: `达到最大重连次数 ${maxRetries}` } } as EventData;
        setEvents(prev => [...prev, errorEvent]);
      }
    };

    const executeSSEConnection = async () => {
      const eventTypes = ['connect','heartbeat','progress','file.upload.start','file.upload.progress','file.upload.complete','file.process.start','file.process.progress','file.process.complete','model.process.start','model.process.progress','model.extract.complete','compliance.check.start','compliance.check.progress','compliance.check.complete','task.complete'];
      eventTypes.push('system');
      eventTypes.push('thinking.step');
      eventTypes.push('thinking.final');
      try {
        if (!url || typeof url !== 'string' || !url.startsWith('http')) throw new Error(`无效的SSE URL: ${url}`);
        var headers: Record<string, string> = { 'Accept': 'text/event-stream', 'Cache-Control': 'no-cache' };
        const authToken = (token && typeof token === 'string') ? token.trim() : (CONFIG.bearerToken || 'dev-token-for-testing');
        headers['Authorization'] = 'Bearer ' + authToken;
        es = new EventSource(url);
        setEvents(prev => [...prev, { event: "connection.established", raw: "CONNECT/ESTABLISHED", type: "connection", timestamp: Date.now(), data: { status: "connected" } }]);
        es.onmessage = (e: MessageEvent) => {
          const rawData: any = (e && typeof (e as any).data === 'string') ? (e as any).data : '';
          let payload: any;
          try { payload = JSON.parse(rawData); } catch { payload = parseSseRaw(rawData); }
          const evt = normalizeIncoming(payload);
          setEvents(p => p.concat([evt]));
          const label = evt.raw || aguiLabelFor(evt.event);
          if (evt.event !== 'heartbeat') setLogs(p => p.concat([t(evt.timestamp) + ' | ' + label + ' | ' + evt.event]));
          if (evt.event === 'thinking.step') {
            setChatMessages(prev => {
              const last = prev[prev.length - 1];
              if (last?.role === 'assistant' && last.type === 'agent-result') {
                const st = String(evt.data?.status || 'running');
                const stepLabel = String(evt.data?.step || 'step').toUpperCase();
                const updated: ChatMessage = { ...last, agentState: { isThinking: st === 'running', logs: (last.agentState?.logs || []).concat([`THINKING/${stepLabel} | ${st}`]), progress: displayPercent, stage: displayStage } };
                return prev.slice(0, -1).concat([updated]);
              }
              return prev;
            });
          }
          if (evt.event === 'thinking.final') {
            setChatMessages(prev => {
              const last = prev[prev.length - 1];
              if (last?.role === 'assistant' && last.type === 'agent-result') {
                const logsJoined = (last.agentState?.logs || []).concat(['THINKING/FINAL | success']);
                const updated: ChatMessage = { ...last, type: 'text', content: String(evt.data?.answer || ''), agentState: { isThinking: false, logs: logsJoined, progress: 100, stage: 'completed' } } as any;
                return prev.slice(0, -1).concat([updated]);
              }
              return prev;
            });
          }
        };
        eventTypes.forEach((et) => {
          es!.addEventListener(et, (e: MessageEvent) => {
            const rawData: any = (e && typeof (e as any).data === 'string') ? (e as any).data : '';
            let payload: any;
            try { payload = JSON.parse(rawData); } catch { payload = parseSseRaw(rawData); }
            payload.event = payload.event || et;
            const evt = normalizeIncoming(payload);
            setEvents(p => p.concat([evt]));
            const label = evt.raw || aguiLabelFor(evt.event);
            if (evt.event !== 'heartbeat') setLogs(p => p.concat([t(evt.timestamp) + ' | ' + label + ' | ' + evt.event]));
            if (evt.event === 'task.error' || evt.event === 'model.call.error' || evt.event === 'compliance.check.error' || evt.type === 'error') {
              setChatMessages(prev => {
                const last = prev[prev.length - 1];
                if (last?.role === 'assistant' && last.type === 'agent-result') {
                  const code = String(evt.data?.errorCode || 'ERROR');
                  const msg = String(evt.data?.errorMsg || evt.data?.status || '处理失败');
                  const stage = String(evt.data?.failedStage || displayStage);
                  const updated: ChatMessage = { ...last, agentState: { isThinking: false, logs: (last.agentState?.logs || []).concat([`FAILED/${stage} | ${code}: ${msg}`]), progress: displayPercent, stage: 'idle' } };
                  return prev.slice(0, -1).concat([updated]);
                }
                return prev;
              });
            }
          });
        });
        es.onerror = (e: Event) => {
          const errorMessage = 'SSE连接异常';
          setLogs(p => p.concat([t(Date.now()) + ' | SSE/DISCONNECT | ' + errorMessage]));
          setEvents(p => p.concat([{ event: "connection.error", raw: "ERROR", type: "error", timestamp: Date.now(), data: { status: "SSE连接失败", error: errorMessage } }]));
          try { es?.close(); } catch {}
          if (retryCount < maxRetries) reconnect();
        };
      } catch (e: any) {
        var errorMessage = e && e.message ? e.message : String(e);
        var timestamp = Date.now();
        setLogs(function(p) { return p.concat([t(timestamp) + ' | SSE/DISCONNECT | ' + errorMessage]); });
        setLogs(function(p) { return p.concat([t(timestamp) + ' | SSE/ERROR_DETAIL | ' + JSON.stringify(e)]); });
        var errorEvent = { event: "connection.error", raw: "ERROR", type: "error", timestamp: timestamp, data: { status: "SSE连接失败", error: errorMessage } } as EventData;
        setEvents(function(p) { return p.concat([errorEvent]); });
        if (!e.name || e.name !== 'AbortError') reconnect();
      }
    };

    executeSSEConnection();
    const originalStopSSE = stopSSE;
    const enhancedStopSSE = function() {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      originalStopSSE();
    };
    stopSSE = enhancedStopSSE as any;
  }

  let stopSSE = function() {
    try { sseCtl.current?.abort?.(); } catch {}
    sseCtl.current = null;
  }

  useEffect(() => {
    const initializeAuth = async () => {
      const existingToken = localStorage.getItem("accessToken");
      if (!existingToken) { await getAuthToken(); }
    };
    initializeAuth();
  }, []);

  useEffect(() => () => stopSSE(), []);

  useEffect(() => {
    const timeoutMs = 30000;
    const id = window.setTimeout(() => {
      const inactive = Date.now() - lastEventAt > timeoutMs;
      if (inactive) {
        setChatMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && last.type === 'agent-result' && last.agentState?.isThinking) {
            const updated: ChatMessage = { ...last, agentState: { isThinking: false, logs: (last.agentState?.logs || []).concat(['THINKING/TIMEOUT | failed']), progress: last.agentState?.progress || 0, stage: 'idle' } };
            return prev.slice(0, -1).concat([updated]);
          }
          return prev;
        });
      }
    }, timeoutMs);
    return () => clearTimeout(id);
  }, [lastEventAt]);


  /** ===== 渲染界面 ===== */
  return (
    <div className="h-screen w-full flex overflow-hidden">
      {/* 左侧边栏 (极简风格) */}
      <aside className="w-64 bg-slate-900 text-slate-300 hidden md:flex flex-col border-r border-slate-800">
        <div className="p-5 border-b border-slate-800">
           <div className="flex items-center gap-2 text-white font-bold text-xl">
             <div className="w-6 h-6 bg-indigo-500 rounded-md"></div>
             DocSmart
           </div>
           <div className="text-xs text-slate-500 mt-1">AI Agent Powered</div>
        </div>
        
        <div className="flex-1 p-3 space-y-2 overflow-y-auto">
           <div className="text-xs font-semibold text-slate-500 px-3 py-2 uppercase tracking-wider">Today</div>
           <button className="w-full text-left px-3 py-2 bg-slate-800/50 text-indigo-300 rounded-lg text-sm border border-slate-700/50">
             📄 {currentFile?.name || "新会话"}
           </button>
        </div>

        <div className="p-4 border-t border-slate-800 text-xs text-slate-500 text-center">
          v2.0.1 (SSE Enabled)
        </div>
      </aside>

      {/* 右侧主区域 */}
      <main className="flex-1 flex flex-col bg-white relative">
         <header className="h-14 border-b flex items-center px-6 justify-between md:hidden">
            <span className="font-bold text-gray-800">DocSmart AI</span>
         </header>

         {/* 聊天界面 */}
         <div className="flex-1 overflow-hidden relative">
            <ChatInterface 
              messages={chatMessages}
              pendingText={pendingText}
              pendingFiles={pendingFiles}
              onQueueFiles={queueFiles}
              onChangeText={setPendingText}
              onSend={onSendAll}
              isProcessing={displayStage !== 'idle' && displayStage !== 'completed'}
            />
         </div>
      </main>
    </div>
  );
}