from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Any, Union
from uuid import UUID, uuid4


# 一、算法接口请求模型
class FileInfo(BaseModel):
    """文件信息模型"""
    fileId: str = Field(description="文件唯一标识")
    storagePath: str = Field(description="文件存储路径")
    fileType: str = Field(description="文件类型")
    fileSize: int = Field(gt=0, description="文件大小（字节）")


class ModelParams(BaseModel):
    """模型调用参数"""
    modelId: str = Field(description="模型ID")
    modelName: str = Field(description="模型名称")
    targetFields: List[str] = Field(description="需提取的字段列表",
                                    default=["invoiceNo", "issueDate", "sellerName", "buyerName",
                                             "goodsDesc", "quantity", "unitPrice", "amount"])
    confidenceThreshold: float = Field(ge=0, le=1, default=0.8, description="置信度阈值")


class ValidationParams(BaseModel):
    """逻辑校验工具参数"""
    needValidation: bool = Field(description="是否启用逻辑校验")
    ruleIds: List[str] = Field(description="需执行的校验规则ID",
                               default=["INV_FORMAT_001", "AMOUNT_LOGIC_002", "DATE_VALID_003"])
    ruleVersion: Optional[str] = Field(default="v1.0", description="校验规则版本")
    skipOnFail: Optional[bool] = Field(default=True, description="校验失败是否终止算法执行")

    @field_validator('ruleIds')
    def rule_ids_required_if_validation_enabled(cls, v, info):
        if info.data.get('needValidation') and not v:
            raise ValueError('当启用校验时，ruleIds不能为空')
        return v


class AlgorithmRequest(BaseModel):
    """算法接口请求模型"""
    processId: str = Field(default_factory=lambda: f"proc-{uuid4()}", description="单证智能体任务ID")
    fileInfo: FileInfo = Field(description="文件信息")
    modelParams: ModelParams = Field(description="模型调用参数")
    callbackUrl: str = Field(description="后端回调地址")
    validationParams: Optional[ValidationParams] = Field(None, description="逻辑校验参数")


# 二、算法接口响应模型
class AlgorithmInitialResponse(BaseModel):
    """算法接口初始响应（任务受理）"""
    code: Literal[200, 400, 401, 500] = Field(description="服务状态码")
    message: str = Field(description="响应描述")
    algorithmTaskId: str = Field(default_factory=lambda: f"alg-task-{uuid4()}", description="算法组内部任务ID")
    status: Literal["pending", "running"] = Field(default="pending", description="初始状态")
    validationTaskStatus: Optional[Literal["pending_validation", "running_validation"]] = Field(None,
                                                                                                description="校验任务初始状态")
    estimatedTime: Optional[int] = Field(None, description="预估总处理时间（秒）")


class ExtractedFieldResult(BaseModel):
    """字段提取结果"""
    fieldName: str = Field(description="字段名")
    fieldValue: Union[str, int, float] = Field(description="字段值")
    confidence: float = Field(ge=0, le=1, description="提取置信度")
    position: Optional[Dict[str, Any]] = Field(None, description="字段位置（JSON对象）")


class ValidationRuleResult(BaseModel):
    """单条校验规则结果"""
    ruleId: str = Field(description="规则ID")
    ruleName: str = Field(description="规则名称")
    errorMsg: Optional[str] = Field(None, description="错误描述")
    field: Optional[str] = Field(None, description="关联字段")


class ValidationResult(BaseModel):
    """校验结果"""
    validationStatus: Literal["passed", "failed", "skipped"] = Field(description="校验状态")
    ruleVersion: str = Field(description="规则版本")
    validationTime: int = Field(description="校验时间戳（毫秒）")
    failedRules: Optional[List[ValidationRuleResult]] = Field(None, description="失败规则列表")


class AlgorithmCallbackSuccessData(BaseModel):
    """算法回调成功数据"""
    algorithmTaskId: str = Field(description="算法任务ID")
    processId: str = Field(description="单证任务ID")
    status: Literal["success"] = "success"
    extractedFields: List[ExtractedFieldResult] = Field(description="提取字段结果")
    validationResult: Optional[ValidationResult] = Field(None, description="校验结果")
    endTime: int = Field(description="处理完成时间戳（毫秒）")
    modelId: str = Field(description="模型ID")
    source_type: str = Field(default="algorithm", description="数据来源类型")
    file_info: Dict[str, Any] = Field(default_factory=dict, description="文件信息")


class AlgorithmCallbackErrorData(BaseModel):
    """算法回调失败数据"""
    algorithmTaskId: str = Field(description="算法任务ID")
    processId: str = Field(description="单证任务ID")
    status: Literal["fail"] = "fail"
    errorCode: str = Field(description="错误码")
    errorMsg: str = Field(description="错误描述")
    validationResult: Optional[ValidationResult] = Field(None, description="校验结果")
    modelId: str = Field(description="模型ID")
    failTime: int = Field(description="失败时间戳（毫秒）")


# 算法回调统一模型
AlgorithmCallbackData = Union[AlgorithmCallbackSuccessData, AlgorithmCallbackErrorData]

class AlgorithmResponse(BaseModel):
    """算法服务统一响应模型 - 与算法服务返回格式完全匹配"""
    code: int = Field(default=200, description="响应状态码")
    message: str = Field(default="任务已受理", description="响应消息")
    algorithmTaskId: str = Field(..., description="算法任务ID")
    status: str = Field(default="pending", description="任务状态")
    estimatedTime: int = Field(default=5, description="估计完成时间（秒）")