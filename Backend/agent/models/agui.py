from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Union, Dict, Any
from datetime import datetime


# 基础模型
class FieldDetail(BaseModel):
    """字段提取详情模型"""
    fieldName: str
    fieldValue: Union[str, int, float, datetime]
    confidence: float = Field(ge=0, le=1, description="提取置信度（0-1）")
    position: Optional[Dict[str, Any]] = Field(None, description="字段在文件中的位置（可选，JSON对象）")


class RuleResult(BaseModel):
    ruleName: str
    ruleId: str
    result: Literal["pass", "fail"]
    reason: Optional[str] = Field(None, description="失败原因（仅失败时必填）")

    @field_validator('reason')
    def reason_required_if_fail(cls, v, info):
        data = getattr(info, 'data', {})
        if data.get('result') == 'fail' and v is None:
            raise ValueError('当检查结果为"fail"时，reason不能为空')
        return v


# 一、文件上传相关事件
class FileUploadStartData(BaseModel):
    fileId: str = Field(description="文件唯一标识")
    fileName: str = Field(description="原始文件名")
    fileType: str = Field(description="文件类型（如application/pdf）")
    fileSize: int = Field(gt=0, description="文件总大小（字节）")
    status: Literal["init"] = "init"


class FileUploadProgressData(BaseModel):
    fileId: str = Field(description="关联的文件ID")
    progress: int = Field(ge=0, le=100, description="上传进度（0-100）")
    uploadedSize: int = Field(ge=0, description="已上传字节数")
    totalSize: int = Field(gt=0, description="文件总字节数")
    status: Literal["uploading"] = "uploading"


class FileUploadCompleteData(BaseModel):
    fileId: str = Field(description="关联的文件ID")
    fileName: str = Field(description="原始文件名")
    storagePath: str = Field(description="文件在服务器的存储路径")
    md5: str = Field(description="文件校验码")
    finishTime: int = Field(gt=0, description="上传完成时间戳（毫秒）")
    fileSize: int = Field(gt=0, description="文件总大小（字节）")
    succeed: Literal["上传成功"] = "上传成功"




class FileUploadErrorData(BaseModel):
    fileId: Optional[str] = Field(None, description="关联的文件ID（若已生成）")
    fileName: str = Field(description="原始文件名")
    errorCode: str = Field(description="错误编码（如FILE_TYPE_INVALID）")
    errorMsg: str = Field(description="错误描述")
    failed: Literal["上传失败"] = "上传失败"


# 二、文件处理与模型调度事件
class FileProcessStartData(BaseModel):
    processId: str = Field(description="处理任务唯一标识")
    fileId: str = Field(description="关联的文件ID")
    startTime: int = Field(gt=0, description="处理开始时间戳（毫秒）")


class FileProcessProgressData(BaseModel):
    processId: str = Field(description="处理任务ID")
    fileId: str = Field(description="关联的文件ID")
    progress: int = Field(ge=0, le=100, description="处理进度（0-100）")
    stage: str = Field(description="当前阶段（如OCR识别中）")


class FileProcessCompleteData(BaseModel):
    processId: str = Field(description="处理任务ID")
    fileId: str = Field(description="关联的文件ID")
    succeed: bool = Field(description="处理是否成功")
    message: str = Field(default="", description="处理结果消息")
    timestamp: int = Field(description="完成时间戳（毫秒）")


class ModelDispatchStartData(BaseModel):
    processId: str = Field(description="处理任务ID")
    modelId: str = Field(description="调用的模型ID")
    modelName: str = Field(description="模型名称")
    targetFields: List[str] = Field(description="需提取的字段列表")
    startTime: int = Field(gt=0, description="模型调度开始时间戳（毫秒）")


class ModelProcessProgressData(BaseModel):
    processId: str = Field(description="处理任务ID")
    modelId: str = Field(description="模型ID")
    progress: int = Field(ge=0, le=100, description="模型处理进度（0-100）")
    processedFields: int = Field(ge=0, description="已提取的字段数量")
    totalFields: int = Field(gt=0, description="需提取的总字段数量")
    currentField: Optional[str] = Field(None, description="当前正在提取的字段（可选）")


class ModelExtractCompleteData(BaseModel):
    processId: str = Field(description="处理任务ID")
    modelId: str = Field(description="模型ID")
    extractedFields: List[FieldDetail] = Field(description="提取的字段详情列表")
    endTime: int = Field(gt=0, description="模型处理完成时间戳（毫秒）")


class ModelCallErrorData(BaseModel):
    processId: str = Field(description="处理任务ID")
    modelId: str = Field(description="模型ID")
    errorCode: str = Field(description="错误编码（如MODEL_TIMEOUT）")
    errorMsg: str = Field(description="错误描述")


# 三、合规判断相关事件
class ComplianceCheckStartData(BaseModel):
    processId: str = Field(description="处理任务ID")
    checkRules: List[str] = Field(description="需检查的合规规则列表")
    startTime: int = Field(gt=0, description="合规检查开始时间戳（毫秒）")


class ComplianceCheckProgressData(BaseModel):
    processId: str = Field(description="处理任务ID")
    progress: int = Field(ge=0, le=100, description="检查进度（0-100）")
    checkedRules: int = Field(ge=0, description="已检查的规则数量")
    totalRules: int = Field(gt=0, description="需检查的总规则数量")
    currentRule: Optional[str] = Field(None, description="当前检查的规则（可选）")


class RiskAlert(BaseModel):
    """风险提示模型"""
    type: str = Field(description="风险类型")
    level: Literal["high", "medium", "low", "info"] = Field(description="风险等级")
    message: str = Field(description="风险提示消息")
    details: List[str] = Field(default_factory=list, description="风险详情列表")
    recommendation: str = Field(description="建议操作")


class RuleResult(BaseModel):
    ruleName: str
    ruleId: str
    result: Literal["pass", "fail"]
    reason: Optional[str] = Field(None, description="失败原因（仅失败时必填）")
    severity: Optional[Literal["high", "medium", "low"]] = Field(default="medium", description="规则严重程度")
    riskLevel: Optional[Literal["high", "medium", "low"]] = Field(default="low", description="风险等级")

    @field_validator('reason')
    def reason_required_if_fail(cls, v, info):
        data = getattr(info, 'data', {})
        if data.get('result') == 'fail' and v is None:
            raise ValueError('当检查结果为"fail"时，reason不能为空')
        return v


class ComplianceCheckCompleteData(BaseModel):
    processId: str = Field(description="处理任务ID")
    overallResult: Literal["pass", "fail"] = Field(description="总体合规结果")
    ruleResults: List[RuleResult] = Field(description="每条规则的检查结果")
    endTime: int = Field(gt=0, description="合规检查完成时间戳（毫秒）")
    # 增强字段
    overallRiskLevel: Optional[Literal["high", "medium", "low"]] = Field(default="low", description="整体风险等级")
    highRiskCount: Optional[int] = Field(default=0, description="高风险问题数量")
    mediumRiskCount: Optional[int] = Field(default=0, description="中风险问题数量")
    lowRiskCount: Optional[int] = Field(default=0, description="低风险问题数量")
    riskAlerts: Optional[List[RiskAlert]] = Field(default_factory=list, description="风险提示列表")


class ComplianceCheckErrorData(BaseModel):
    processId: str = Field(description="处理任务ID")
    errorCode: str = Field(description="错误编码（如RULE_CONFIG_INVALID）")
    errorMsg: str = Field(description="错误描述")


# 四、任务总进度与结果事件
class TaskTotalProgressData(BaseModel):
    processId: str = Field(description="处理任务ID")
    currentStage: str = Field(description="当前所处阶段（如文件上传中）")
    progress: int = Field(ge=0, le=100, description="总进度（0-100）")


class TaskCompleteData(BaseModel):
    processId: str = Field(description="处理任务ID")
    fileId: str = Field(description="关联的文件ID")
    photo: Optional[str] = Field(None, description="预览图URL（替代二进制）")
    extractedFields: List[FieldDetail] = Field(description="最终提取结果")
    complianceResult: ComplianceCheckCompleteData = Field(description="最终合规结果")
    totalDuration: int = Field(gt=0, description="总耗时（毫秒）")


class TaskErrorData(BaseModel):
    processId: str = Field(description="处理任务ID")
    failedStage: Literal[
        "file.upload", "file.process", "model.dispatch",
        "model.process", "compliance.check", "system"
    ] = Field(description="失败的阶段")
    errorCode: str = Field(description="失败环节的错误编码")
    errorMsg: str = Field(description="失败环节的错误描述")


# 五、工具调用事件（AG-UI协议扩展）
class ToolCallStartData(BaseModel):
    processId: str = Field(description="处理任务ID")
    toolName: str = Field(description="工具名称")
    toolParams: Dict[str, Any] = Field(description="工具调用参数")
    startTime: int = Field(gt=0, description="工具调用开始时间戳（毫秒）")


# 六、用户操作事件（AG-UI协议扩展）
class UserActionModifyFieldData(BaseModel):
    """用户修改字段事件数据"""
    processId: str = Field(description="处理任务ID")
    modifiedFields: Dict[str, Any] = Field(description="修改的字段数据")
    userId: str = Field(description="操作用户ID")


class ToolCallCompleteData(BaseModel):
    processId: str = Field(description="处理任务ID")
    toolName: str = Field(description="工具名称")
    toolResult: Dict[str, Any] = Field(description="工具调用结果")
    endTime: int = Field(gt=0, description="工具调用完成时间戳（毫秒）")


class FinalResultGenerateData(BaseModel):
    """最终结果生成数据"""
    processId: str = Field(description="处理任务ID")
    fileId: str = Field(description="文件ID")
    extractedFields: List[FieldDetail] = Field(description="提取的字段详情列表")
    complianceResult: ComplianceCheckCompleteData = Field(description="合规检查结果")
    generateTime: int = Field(gt=0, description="结果生成时间戳（毫秒）")


class ErrorEventData(BaseModel):
    """错误事件数据"""
    processId: str = Field(description="处理任务ID")
    errorCode: str = Field(description="错误编码")
    errorMsg: str = Field(description="错误描述")
    failedStage: str = Field(description="失败的阶段")


class HeartbeatData(BaseModel):
    """心跳事件数据"""
    timestamp: int = Field(description="时间戳")
    message: str = Field(default="Connection active", description="心跳消息")
    status: Literal["active"] = "active"
    queueSize: int = Field(default=0, description="队列大小")


class ConnectData(BaseModel):
    """连接建立事件数据"""
    status: Literal["connected"] = "connected"
    processId: str = Field(description="处理任务ID")
    sseUrl: Optional[str] = Field(None, description="SSE连接URL")


class ResultSummaryData(BaseModel):
    """结果汇总数据（增强版）"""
    processId: str = Field(description="处理任务ID")
    fileId: str = Field(description="文件ID")
    extractedFields: List[FieldDetail] = Field(description="提取的字段详情列表")
    complianceResult: ComplianceCheckCompleteData = Field(description="合规检查结果")
    # 增强字段
    riskSummary: Dict[str, Any] = Field(description="风险摘要信息")
    confidenceStats: Dict[str, float] = Field(description="字段置信度统计")
    totalProcessingTime: int = Field(description="总处理时间（毫秒）")
    stageDurations: Dict[str, int] = Field(description="各阶段耗时")
    recommendation: str = Field(description="总体建议")


# 事件模型统一封装
class AGUIEvent(BaseModel):
    """AG-UI事件统一模型（增强版）"""
    type: Literal[
        # 基础连接事件
        "connect", "heartbeat", "system", "thinking.step", "thinking.final",
        # 文件上传事件
        "file.upload.start", "file.upload.progress", "file.upload.complete", "file.upload.error",
        # 文件处理事件
        "file.process.start", "file.process.progress", "file.process.complete",
        # 模型调度事件
        "model.dispatch.start", "model.process.progress", "model.extract.complete", "model.call.error",
        # 合规检查事件
        "compliance.check.start", "compliance.check.progress", "compliance.check.complete", "compliance.check.error",
        # 任务总进度事件
        "task.total.progress", "task.complete", "task.error",
        # 工具调用事件
        "tool.call.start", "tool.call.complete",
        # 用户操作事件
        "user.action.modify_field",
        # 结果汇总事件
        "result.summary", "result.final"
    ] = Field(description="AG-UI事件类型")
    data: Union[
        # 基础连接相关
        HeartbeatData, ConnectData,
        # 文件上传相关
        FileUploadStartData, FileUploadProgressData, FileUploadCompleteData, FileUploadErrorData,
        # 文件处理相关
        FileProcessStartData, FileProcessProgressData, FileProcessCompleteData,
        # 模型调度相关
        ModelDispatchStartData, ModelProcessProgressData, ModelExtractCompleteData, ModelCallErrorData,
        # 合规检查相关
        ComplianceCheckStartData, ComplianceCheckProgressData, ComplianceCheckCompleteData, ComplianceCheckErrorData,
        # 任务总进度相关
        TaskTotalProgressData, TaskCompleteData, TaskErrorData,
        # 工具调用相关
        ToolCallStartData, ToolCallCompleteData,
        # 用户操作相关
        UserActionModifyFieldData,
        # 最终结果相关
        FinalResultGenerateData, ResultSummaryData,
        # 错误事件相关
        ErrorEventData,
        # 通用数据
        Dict[str, Any]
    ] = Field(description="AG-UI事件数据")
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000), description="事件时间戳（毫秒）")
    # 扩展字段
    eventId: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="事件唯一标识")
    source: Literal["backend", "frontend", "algorithm"] = Field(default="backend", description="事件来源")
    retry: Optional[int] = Field(None, description="重试次数")


# 添加必要的导入
import uuid