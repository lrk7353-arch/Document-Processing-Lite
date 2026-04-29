from typing import Dict, Any
from agent.langgraph.state import AgentState
from agent.db.crud.task import update_task_state
from agent.models.agui import ErrorEventData, TaskErrorData, AGUIEvent
from agent.utils.logger import logger
from agent.utils.sse import sse_manager
from agent.utils.error import ErrorCode
from sqlalchemy.orm import Session
from datetime import datetime


class ErrorNode:
    """错误处理节点（处理《数据契约与状态机.docx》中的错误流程）"""

    def __init__(self, db: Session):
        self.db = db

    async def handle_error(self, state: AgentState, error_code: str, error_message: str, failed_stage: str) -> Dict[str, Any]:
        """
        统一错误处理节点
        
        Args:
            state: 当前状态机状态
            error_code: 错误码
            error_message: 错误消息
            failed_stage: 失败阶段
            
        Returns:
            包含错误信息的状态更新字典
        """
        # 确保failed_stage是有效值，如果不是则使用默认值'file.process'
        valid_stages = ['file.upload', 'file.process', 'model.dispatch', 'model.process', 'compliance.check', 'system']
        if failed_stage not in valid_stages:
            logger.warning(f"无效的failed_stage值: {failed_stage}，使用默认值'file.process'", extra={"processId": state.process_id, "algorithmTaskId": ""})
            failed_stage = 'file.process'
        try:
            # 推送错误事件（文档4.任务处理错误）
            error_data = TaskErrorData(
                processId=state.process_id,
                failedStage=failed_stage,
                errorCode=error_code,
                errorMsg=error_message
            )
            error_event = AGUIEvent(
                type="task.error",
                data=error_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=error_event
                )
                if success:
                    logger.info(f"任务错误事件发送成功", extra={"processId": state.process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"任务错误事件发送失败", extra={"processId": state.process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送任务错误事件异常: {str(e)}", extra={"processId": state.process_id, "algorithmTaskId": ""}, exc_info=True)

            # 更新数据库任务状态为失败
            update_task_state(
                db=self.db,
                process_id=state.process_id,
                state="failed",
                total_progress=100
            )

            logger.error(
                f"任务处理失败: process_id={state.process_id}, error_code={error_code}, stage={failed_stage}",
                extra={
                    "processId": state.process_id,
                    "errorCode": error_code,
                    "failedStage": failed_stage,
                    "errorMessage": error_message
                }
            )

            return {
                "agent_state": "failed",
                "error_code": error_code,
                "error_message": error_message,
                "failed_stage": failed_stage
            }

        except Exception as e:
            # 记录错误处理节点自身的异常
            logger.critical(
                f"错误处理节点异常: process_id={state.process_id}, original_error={error_code}",
                extra={
                    "processId": state.process_id,
                    "originalErrorCode": error_code,
                    "nodeException": str(e)
                },
                exc_info=True
            )

            # 即使错误处理节点自身失败，也要返回一个失败状态
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.ERROR_HANDLER_ERROR.name,
                "error_message": f"任务处理失败，且错误处理节点异常: {str(e)}",
                "failed_stage": failed_stage
            }

    async def handle_file_upload_error(self, state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        处理文件上传错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.FILE_UPLOAD_ERROR.name,
            error_message=error_message,
            failed_stage="file.upload"
        )

    async def handle_model_dispatch_error(self, state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        处理模型调度错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.MODEL_DISPATCH_ERROR.name,
            error_message=error_message,
            failed_stage="model.dispatch"
        )

    async def handle_algorithm_result_error(self, state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        处理算法结果处理错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.ALGORITHM_RESULT_PROCESS_ERROR.name,
            error_message=error_message,
            failed_stage="model.result"
        )

    async def handle_compliance_check_error(self, state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        处理合规检查错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.COMPLIANCE_CHECK_ERROR.name,
            error_message=error_message,
            failed_stage="compliance.check"
        )

    async def handle_result_generate_error(self, state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        处理最终结果生成错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.FINAL_RESULT_GENERATE_ERROR.name,
            error_message=error_message,
            failed_stage="result.generate"
        )

    async def handle_timeout_error(self, state: AgentState, stage: str) -> Dict[str, Any]:
        """
        处理超时错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.PROCESS_TIMEOUT.name,
            error_message=f"{stage}阶段处理超时",
            failed_stage=stage
        )

    async def handle_validation_error(self, state: AgentState, field_name: str, error_message: str) -> Dict[str, Any]:
        """
        处理数据验证错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.DATA_VALIDATION_ERROR.name,
            error_message=f"字段验证失败: {field_name} - {error_message}",
            failed_stage="data.validation"
        )

    async def handle_system_error(self, state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        处理系统内部错误
        """
        return await self.handle_error(
            state=state,
            error_code=ErrorCode.SYSTEM_ERROR.name,
            error_message=error_message,
            failed_stage="system"
        )
    
    async def langgraph_error_handler(self, state: AgentState) -> AgentState:
        """LangGraph兼容的错误处理节点
        
        这个方法只接受state参数，符合LangGraph节点的要求
        尝试从state中获取错误信息，处理可能的属性不存在情况
        作为异步函数，正确等待handle_system_error的结果
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        # 安全地获取错误信息，处理AgentState可能没有error_message属性的情况
        error_message = "系统处理过程中出现错误"
        try:
            if hasattr(state, 'error_message') and state.error_message:
                error_message = state.error_message
        except Exception:
            pass
        
        # 正确等待异步的handle_system_error方法
        return await self.handle_system_error(state, error_message)