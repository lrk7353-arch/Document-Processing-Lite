from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from agent.models.agui import (
    FileUploadCompleteData, ModelExtractCompleteData, ComplianceCheckCompleteData,
    TaskCompleteData, TaskErrorData
)
from agent.models.algorithm_data import AlgorithmInitialResponse, AlgorithmCallbackSuccessData


class AgentState(BaseModel):
    """
    LangGraph智能体全局状态（严格对齐《数据契约与状态机.docx》状态机设计）
    状态流转：idle → processing → (validation_passed/validation_failed) → completed/failed
    """
    # 基础标识
    process_id: str = Field(description="任务唯一标识")
    file_id: Optional[str] = Field(None, description="文件ID")
    agent_state: str = Field(default="idle", description="智能体状态：idle/processing/awaiting_input/completed/failed/canceled/paused/draft")

    # 文件信息
    file_info: Optional[FileUploadCompleteData] = Field(None, description="文件上传完成数据")

    # 算法相关
    algorithm_task_id: Optional[str] = Field(None, description="算法任务ID")
    algorithm_initial_response: Optional[AlgorithmInitialResponse] = Field(None, description="算法初始响应")
    algorithm_result: Optional[AlgorithmCallbackSuccessData] = Field(None, description="算法处理结果")

    # 合规相关
    compliance_result: Optional[ComplianceCheckCompleteData] = Field(None, description="合规检查结果")

    # 错误信息
    error_code: Optional[str] = Field(None, description="错误码")
    error_msg: Optional[str] = Field(None, description="错误描述")
    failed_stage: Optional[str] = Field(None, description="失败阶段")

    # 最终结果
    final_result: Optional[TaskCompleteData] = Field(None, description="任务最终结果")
    total_duration: Optional[int] = Field(None, description="总耗时（毫秒）")

    class Config:
        arbitrary_types_allowed = True