// src/types/agui.d.ts
// ================================
// 基于 AG-UI 协议的智能体系统事件定义
// 用于前端类型约束与事件派发
// ================================

/** ========== 通用结构 ========== */
export interface AgUiBaseEvent<T = any> {
  /** 协议必选：事件唯一 ID */
  eventId: string;
  /** 协议必选：事件类型，如 file.upload.start */
  eventType: string;
  /** 协议必选：事件触发时间 */
  timestamp: number;
  /** 协议必选：事件载荷（与具体类型绑定） */
  data: T;
  /** 协议选填：事件状态，如 "success" / "progress" / "error" */
  status?: string;
}

/** ========== 文件上传事件 ========== */
export interface FileUploadStartData {
  fileId: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  status: "init";
}
export type FileUploadStartEvent = AgUiBaseEvent<FileUploadStartData>;

export interface FileUploadProgressData {
  fileId: string;
  progress: number;
  uploadedSize: number;
  totalSize: number;
  status: "uploading";
}
export type FileUploadProgressEvent = AgUiBaseEvent<FileUploadProgressData>;

export interface FileUploadCompleteData {
  fileId: string;
  fileName: string;
  storagePath: string;
  md5: string;
  finishTime: number;
  status: "file_received" | "upload_verifying";
}
export type FileUploadCompleteEvent = AgUiBaseEvent<FileUploadCompleteData>;

export interface FileUploadErrorData {
  fileId?: string;
  fileName: string;
  errorCode: string;
  errorMsg: string;
  status: "upload_failed";
}
export type FileUploadErrorEvent = AgUiBaseEvent<FileUploadErrorData>;

/** ========== 文件处理与模型调度事件 ========== */
export interface FileProcessStartData {
  processId: string;
  fileId: string;
  startTime: number;
}
export type FileProcessStartEvent = AgUiBaseEvent<FileProcessStartData>;

export interface FileProcessProgressData {
  processId: string;
  fileId: string;
  progress: number;
  status: "file_parsing";
}
export type FileProcessProgressEvent = AgUiBaseEvent<FileProcessProgressData>;

export interface ModelDispatchStartData {
  processId: string;
  modelId: string;
  modelName: string;
  targetFields: string[];
  startTime: number;
}
export type ModelDispatchStartEvent = AgUiBaseEvent<ModelDispatchStartData>;

export interface ModelProcessProgressData {
  processId: string;
  modelId: string;
  progress: number;
  processedFields: number;
  totalFields: number;
  currentField?: string;
  status: "model_extracting";
}
export type ModelProcessProgressEvent = AgUiBaseEvent<ModelProcessProgressData>;

export interface ModelExtractCompleteData {
  processId: string;
  modelId: string;
  extractedFields: {
    fieldName: string;
    fieldValue: string | number;
    confidence: number;
    position?: string;
  }[];
  endTime: number;
}
export type ModelExtractCompleteEvent = AgUiBaseEvent<ModelExtractCompleteData>;

export interface ModelCallErrorData {
  processId: string;
  modelId: string;
  errorCode: string;
  errorMsg: string;
  status: "model_failed";
}
export type ModelCallErrorEvent = AgUiBaseEvent<ModelCallErrorData>;

/** ========== 合规检查事件 ========== */
export interface ComplianceCheckStartData {
  processId: string;
  checkRules: string[];
  startTime: number;
}
export type ComplianceCheckStartEvent = AgUiBaseEvent<ComplianceCheckStartData>;

export interface ComplianceCheckProgressData {
  processId: string;
  progress: number;
  checkedRules: number;
  totalRules: number;
  currentRule?: string;
  status: "compliance_checking";
}
export type ComplianceCheckProgressEvent = AgUiBaseEvent<ComplianceCheckProgressData>;

export interface ComplianceCheckCompleteData {
  processId: string;
  overallResult: "pass" | "fail";
  ruleResults: {
    ruleName: string;
    result: "pass" | "fail";
    reason?: string;
  }[];
  endTime: number;
  status: "compliance_passed" | "compliance_failed";
}
export type ComplianceCheckCompleteEvent = AgUiBaseEvent<ComplianceCheckCompleteData>;

export interface ComplianceCheckErrorData {
  processId: string;
  errorCode: string;
  errorMsg: string;
  status: "compliance_failed";
}
export type ComplianceCheckErrorEvent = AgUiBaseEvent<ComplianceCheckErrorData>;

/** ========== 任务进度与结果事件 ========== */
export interface TaskTotalProgressData {
  processId: string;
  currentStage: string;
  progress?: number;
}
export type TaskTotalProgressEvent = AgUiBaseEvent<TaskTotalProgressData>;

export interface TaskCompleteData {
  processId: string;
  fileId: string;
  extractedFields: any[];
  complianceResult: any;
  totalDuration: number;
  status: "agent_success" | "result_generating";
}
export type TaskCompleteEvent = AgUiBaseEvent<TaskCompleteData>;

export interface TaskErrorData {
  processId: string;
  failedStage: string;
  errorCode: string;
  errorMsg: string;
  status: "task_failed";
}
export type TaskErrorEvent = AgUiBaseEvent<TaskErrorData>;


/** ========== 类型聚合导出 ========== */
export type AgUiEvent =
  | FileUploadStartEvent
  | FileUploadProgressEvent
  | FileUploadCompleteEvent
  | FileUploadErrorEvent
  | FileProcessStartEvent
  | FileProcessProgressEvent
  | ModelDispatchStartEvent
  | ModelProcessProgressEvent
  | ModelExtractCompleteEvent
  | ModelCallErrorEvent
  | ComplianceCheckStartEvent
  | ComplianceCheckProgressEvent
  | ComplianceCheckCompleteEvent
  | ComplianceCheckErrorEvent
  | TaskTotalProgressEvent
  | TaskCompleteEvent
  | TaskErrorEvent
/** ------------------------- 扩展部分：状态机与通信机制 ------------------------- */

declare namespace AGUI {
  /** 状态机：任务状态 */
  type TaskStatus =
    | "idle"
    | "uploading"
    | "processing"
    | "analyzing"
    | "checking"
    | "success"
    | "error";

  /** 状态机：任务状态模型 */
  interface TaskState {
    taskId: string;
    status: TaskStatus;
    progress: number;
    currentStep: string;
    logs: string[];
    data?: Record<string, any>;
  }

  /** 通信机制：SSE 消息包装结构 */
  interface SSEMessage {
    id?: string;
    event?: string;
    data: string; // JSON 字符串，包含 BaseEvent
  }

  /** 通信机制：连接状态 */
  type SSEConnectionStatus = "connecting" | "open" | "closed" | "error";
}
/** -------------------- 前端兼容扩展 -------------------- */
declare namespace AGUI {
  export type Event<T = any> = AgUiBaseEvent<T>;

  export interface SSEMessage {
    id?: string;
    event?: string;
    data: string;
  }

  export type SSEConnectionStatus = "connecting" | "open" | "closed" | "error";
}
