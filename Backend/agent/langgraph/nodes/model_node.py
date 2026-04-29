from typing import Dict, Any
from agent.langgraph.state import AgentState
from agent.service.algorithm_service import AlgorithmService
from agent.service.db_service import db_service
from agent.models.agui import (
    ModelDispatchStartData, ModelProcessProgressData, ModelExtractCompleteData,
    ToolCallStartData, ToolCallCompleteData, FieldDetail
)
from agent.models.algorithm_data import AlgorithmCallbackSuccessData
from agent.utils.logger import logger
from agent.utils.sse import sse_manager
from agent.utils.error import ErrorCode
from sqlalchemy.orm import Session
from datetime import datetime


class ModelNode:
    """模型调度节点（处理《数据契约与状态机.docx》模型调度流程）"""

    def __init__(self, db: Session):
        self.db = db
        self.algorithm_service = AlgorithmService()

    async def dispatch_model(self, state: AgentState) -> Dict[str, Any]:
        """
        节点3：调度算法模型（调用算法服务 → 推送调度事件）
        """
        try:
            if not state.file_id or not state.file_info:
                error_msg = "文件信息缺失，无法调度模型"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": ErrorCode.DATA_MISSING.name,
                    "error_msg": error_msg,
                    "failed_stage": "model.dispatch"
                }

            # 构建文件信息
            file_info = {
                "fileId": state.file_id,
                "storagePath": state.file_info.storagePath,
                "fileType": state.file_info.fileName.split(".")[-1].lower() if "." in state.file_info.fileName else "pdf",
                "fileSize": state.file_info.fileSize if hasattr(state.file_info, "fileSize") else 0
            }

            # 构建回调URL（简化处理，实际应从配置中获取）
            callback_url = f"http://localhost:8000/api/algorithm/callback"

            # 推送模型调度开始事件（文档5.模型调度开始）
            dispatch_start_data = ModelDispatchStartData(
                processId=state.process_id,
                modelId=self.algorithm_service.default_model_params.modelId,
                modelName=self.algorithm_service.default_model_params.modelName,
                targetFields=self.algorithm_service.default_model_params.targetFields,
                startTime=int(datetime.now().timestamp() * 1000)
            )
            # 创建AGUIEvent对象
            from agent.models.agui import AGUIEvent
            dispatch_event = AGUIEvent(
                type="model.dispatch.start",
                data=dispatch_start_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=dispatch_event
                )
                if success:
                    logger.info(f"模型调度开始事件发送成功", extra={"processId": state.process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"模型调度开始事件发送失败", extra={"processId": state.process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送模型调度开始事件异常: {str(e)}", extra={"processId": state.process_id, "algorithmTaskId": ""}, exc_info=True)

            # 调用算法服务
            algorithm_response, error = await self.algorithm_service.call_algorithm_api(
                process_id=state.process_id,
                file_info=file_info,
                callback_url=callback_url,
                need_validation=True
            )

            if error:
                error_msg = f"算法调用失败: {error.name}"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": error.name,
                    "error_msg": error_msg,
                    "failed_stage": "model.dispatch"
                }

            logger.info(
                f"模型调度成功: process_id={state.process_id}, algorithmTaskId={algorithm_response.algorithmTaskId}",
                extra={"processId": state.process_id, "algorithmTaskId": algorithm_response.algorithmTaskId}
            )

            return {
                "algorithm_task_id": algorithm_response.algorithmTaskId,
                "algorithm_initial_response": algorithm_response,
                "agent_state": "processing"
            }

        except Exception as e:
            error_msg = f"模型调度节点异常: {str(e)}"
            logger.error(
                error_msg,
                extra={"processId": state.process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.MODEL_DISPATCH_ERROR.name,
                "error_msg": error_msg,
                "failed_stage": "model.dispatch"
            }

    async def handle_algorithm_result(self, state: AgentState) -> Dict[str, Any]:
        """
        节点4：处理算法结果（从数据库读取结果 → 转换字段 → 推送完成事件）
        """
        try:
            # 从数据库读取算法结果，而不是依赖state.algorithm_result
            from agent.service.db_service import db_service
            
            # 查询数据库获取算法结果
            algorithm_result = await db_service.get_algorithm_result_async(self.db, state.process_id)
            
            if not algorithm_result:
                error_msg = "算法结果缺失，无法处理（数据库中未找到结果）"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": ErrorCode.ALGORITHM_RESULT_MISSING.name,
                    "error_msg": error_msg,
                    "failed_stage": "model.result"
                }

            # 转换算法结果为AG-UI格式
            extracted_fields = []
            for field in algorithm_result.extractedFields:
                # 创建FieldDetail对象而不是字典
                # 注意：position现在是字符串类型
                field_detail = FieldDetail(
                    fieldName=field.fieldName,
                    fieldValue=field.fieldValue,
                    confidence=field.confidence,
                    position=str(field.position) if field.position is not None else ''
                )
                extracted_fields.append(field_detail)

            # 推送模型提取完成事件（文档7.模型提取完成）
            extract_complete_data = ModelExtractCompleteData(
                processId=state.process_id,
                modelId=algorithm_result.modelId,
                extractedFields=extracted_fields,
                endTime=algorithm_result.endTime
            )
            # 创建AGUIEvent对象
            from agent.models.agui import AGUIEvent
            extract_event = AGUIEvent(
                type="model.extract.complete",
                data=extract_complete_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=extract_event
                )
                if success:
                    logger.info(f"模型提取完成事件发送成功", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""})
                else:
                    logger.warning(f"模型提取完成事件发送失败", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""})
            except Exception as e:
                logger.error(f"发送模型提取完成事件异常: {str(e)}", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""}, exc_info=True)

            # 更新数据库任务状态
            db_service.update_task_algorithm_result(
                db=self.db,
                process_id=state.process_id,
                algorithm_result=algorithm_result
            )

            logger.info(
                f"算法结果处理完成: process_id={state.process_id}, field_count={len(extracted_fields)}",
                extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id}
            )

            return {
                "algorithm_result": algorithm_result,  # 使用从数据库读取的结果
                "agent_state": "processing"
            }

        except Exception as e:
            error_msg = f"算法结果处理节点异常: {str(e)}"
            logger.error(
                error_msg,
                extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""},
                exc_info=True
            )
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.ALGORITHM_RESULT_PROCESS_ERROR.name,
                "error_msg": error_msg,
                "failed_stage": "model.result"
            }