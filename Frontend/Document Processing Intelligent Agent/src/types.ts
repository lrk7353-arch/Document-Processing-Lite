export type EventType =
| "RUN_STARTED"
| "STATE_DELTA"
| "STEP_STARTED"
| "TOOL_CALL_START"
| "TOOL_CALL_END"
| "STEP_FINISHED"
| "RUN_FINISHED"
| "RUN_ERROR";

// 风险级别
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;

// 风险警报
export interface RiskAlert {
  alertId: string;
  alertType: string;
  riskLevel: RiskLevel;
  ruleId: string;
  ruleName: string;
  description: string;
  recommendation?: string;
  confidence?: number;
  timestamp?: number;
}

// 规则结果（增强版，包含严重性和风险级别）
export interface RuleResultEnhanced {
  ruleId?: string;
  ruleName?: string;
  result: string;
  pass?: boolean;
  reason?: string;
  severity?: 'LOW' | 'MEDIUM' | 'HIGH' | string;
  riskLevel?: RiskLevel;
}

// 合规检查结果（增强版）
export interface ComplianceResultEnhanced {
  overallResult: string;
  overallRiskLevel?: RiskLevel;
  riskAlerts?: RiskAlert[];
  ruleResults: RuleResultEnhanced[];
  riskCount?: {
    high: number;
    medium: number;
    low: number;
  };
}


export interface EventEnvelope<T = any> {
event: string; // e.g. "file.upload.progress"
type: EventType;
timestamp: number; // ms
eventId?: string;
data: T & {
fileId?: string;
processId?: string;
fileName?: string;
status?: string; // uploading / processing / ...
progress?: number; // 0-100
uploadedSize?: number;
totalSize?: number;
errorCode?: string;
errorMsg?: string;
// 风险相关字段
complianceResult?: ComplianceResultEnhanced;
overallRiskLevel?: RiskLevel;
riskAlerts?: RiskAlert[];
riskCount?: {
  high: number;
  medium: number;
  low: number;
};
// 结果汇总字段
totalExtractedFields?: number;
passedRules?: number;
failedRules?: number;
[k: string]: any;
};
}


export type Stage =
| "idle"
| "upload"
| "parse"
| "extract"
| "compliance"
| "completed"
| "failed";


export type StageStatus = "idle" | "running" | "success" | "error";


export interface StageState {
name: Stage;
status: StageStatus;
progress: number; // 0-100（阶段内）
meta?: Record<string, any>;
}


export type StagesState = Record<Stage, StageState>;


export interface TaskState {
id: string; // processId || fileId
fileName?: string;
stages: StagesState;
overallProgress: number; // 0-100（加权合成）
result?: {
fields?: Record<string, { value: any; confidence?: number }>;
compliance?: { passed: boolean; violations?: any[] };
};
// 风险相关字段
complianceResult?: ComplianceResultEnhanced;
overallRiskLevel?: RiskLevel;
riskAlerts?: RiskAlert[];
riskCount?: {
  high: number;
  medium: number;
  low: number;
};
lastEventAt?: number;
events?: EventEnvelope[]; // 可选：用于时间线
}