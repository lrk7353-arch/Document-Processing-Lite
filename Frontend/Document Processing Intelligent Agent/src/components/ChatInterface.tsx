// src/components/ChatInterface.tsx
import React, { useRef, useEffect } from "react";
import { ChatMessage } from "../types/chat";
import ResultPanel from "./ResultPanel";

interface ChatInterfaceProps {
  messages: ChatMessage[];
  pendingText: string;
  pendingFiles: File[];
  onQueueFiles: (files: File[]) => void;
  onChangeText: (text: string) => void;
  onSend: () => void;
  onRemoveFile?: (idx: number) => void;
  isProcessing: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, pendingText, pendingFiles, onQueueFiles, onChangeText, onSend, onRemoveFile, isProcessing }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 消息更新时自动滚动到底部
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (list && list.length) {
      const files = Array.from(list);
      onQueueFiles(files);
      e.target.value = "";
    }
  };

  // 格式化时间
  const formatTime = (ts: number) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* --- 1. 聊天记录区域 --- */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            
            {/* 头像 */}
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm
               ${msg.role === "user" ? "order-2 ml-3 bg-indigo-600 text-white" : "mr-3 bg-emerald-600 text-white"}
            `}>
              {msg.role === "user" ? "U" : "AI"}
            </div>

            {/* 气泡本体 */}
            <div className={`flex flex-col max-w-[85%] md:max-w-[70%] rounded-2xl p-4 shadow-sm text-sm
              ${msg.role === "user" 
                ? "bg-indigo-600 text-white rounded-tr-none" 
                : "bg-white border border-gray-100 text-gray-800 rounded-tl-none"}
            `}>
              
              {/* === 类型 A: 用户上传文件 === */}
              {msg.type === "file-upload" && (
                <div className="flex items-center gap-3">
                  <div className="bg-white/20 p-2 rounded">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <div className="font-medium">{msg.fileMeta?.name}</div>
                    <div className="text-xs opacity-80">
                      {msg.fileMeta?.size ? (msg.fileMeta.size / 1024).toFixed(1) + " KB" : "Unknown Size"}
                    </div>
                  </div>
                </div>
              )}

              {/* === 类型 B: Agent 思考与结果 === */}
              {msg.type === "agent-result" && (
                <div className="space-y-3 w-full">
                  {/* 1. 状态栏 */}
                  <div className="flex items-center justify-between pb-2 border-b border-gray-100">
                     <div className="flex items-center gap-2 text-indigo-600 font-medium">
                        {msg.agentState?.isThinking ? (
                          <>
                             <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                               <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                               <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                             </svg>
                             <span>正在分析...</span>
                          </>
                        ) : (
                          <>
                             <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                             </svg>
                             <span className="text-gray-600">分析完成</span>
                          </>
                        )}
                     </div>
                     <span className="text-xs text-gray-400">{formatTime(msg.timestamp)}</span>
                  </div>

                  {/* 2. 思维链日志 (Thinking Logs) */}
                  {msg.agentState?.logs && msg.agentState.logs.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-3 text-xs font-mono text-gray-600 border border-gray-100">
                      <div className="mb-1 text-gray-400 uppercase tracking-wider scale-90 origin-left">Thinking Process</div>
                      <div className="space-y-1 max-h-40 overflow-y-auto custom-scrollbar">
                        {msg.agentState.logs.slice(-6).map((log, i) => ( // 只显示最后6条
                           <div key={i} className="truncate flex gap-2">
                             <span className="text-indigo-400 opacity-50">&gt;</span>
                             <span>{log.split('|').pop()?.trim() || log}</span>
                           </div>
                        ))}
                      </div>
                      {/* 进度条 */}
                      {msg.agentState.isThinking && (
                        <div className="mt-2 h-1 bg-gray-200 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-indigo-500 transition-all duration-500 ease-out"
                            style={{ width: `${msg.agentState.progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {/* 3. 最终结果面板 */}
                  {msg.resultData && (
                    <div className="mt-2 animate-fade-in">
                       <ResultPanel result={msg.resultData} />
                    </div>
                  )}
                </div>
              )}

              {/* === 类型 C: 普通文本 === */}
              {msg.type === "text" && (
                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
              )}

            </div>
          </div>
        ))}
        {/* 占位符，用于自动滚动 */}
        <div ref={scrollRef} className="h-2" />
      </div>

      {/* --- 2. 底部输入区域 --- */}
      <div className="bg-white border-t border-gray-100 p-4">
        <div className="max-w-4xl mx-auto">
          <div className={`relative flex items-center gap-2 p-1.5 rounded-full border shadow-sm transition-all
             ${isProcessing ? "bg-gray-50 border-gray-200" : "bg-white border-gray-300 hover:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 focus-within:border-indigo-500"}
          `}>
            
            {/* 上传按钮 */}
            <button 
              onClick={() => fileInputRef.current?.click()}
              disabled={isProcessing}
              className="p-2.5 text-gray-500 hover:bg-gray-100 hover:text-indigo-600 rounded-full transition disabled:opacity-30 disabled:cursor-not-allowed"
              title="上传单证文件"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </button>
            <input 
              type="file" multiple
              ref={fileInputRef} 
              className="hidden" 
              onChange={handleFileSelect}
              accept=".pdf,.jpg,.jpeg,.png,.svg" 
            />

            {/* 文本输入框 */}
            <input
              type="text"
              disabled={isProcessing}
              placeholder={pendingFiles.length ? `待发送文件：${pendingFiles.length} 个` : "输入消息或点击左侧回形针选择文件"}
              className="flex-1 bg-transparent border-none focus:ring-0 text-sm text-gray-700 placeholder-gray-400 px-2"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isProcessing) {
                  onSend();
                }
              }}
              value={pendingText}
              onChange={(e) => onChangeText(e.target.value)}
            />

            {pendingFiles.length > 0 && (
              <div className="hidden md:flex items-center gap-1 mr-2">
                {pendingFiles.slice(0,3).map((f, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs rounded-full border bg-gray-50 text-gray-700">
                    {f.name}
                  </span>
                ))}
                {pendingFiles.length > 3 && (
                  <span className="px-2 py-0.5 text-xs rounded-full border bg-gray-50 text-gray-700">+{pendingFiles.length - 3}</span>
                )}
              </div>
            )}

            {/* 发送按钮 (装饰用) */}
            <button 
               disabled={false} 
               className="p-2 bg-indigo-600 text-white rounded-full" 
               onClick={() => onSend()}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            </button>
          </div>
          
          <div className="text-center mt-2">
            <span className="text-[10px] text-gray-400">DocSmart Agent 2.0 · 支持 PDF/Image 智能解析与合规审计</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;