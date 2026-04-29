from typing import Dict, Any, List
from agent.langgraph.state import AgentState
from agent.service.algorithm_service import AlgorithmService
from agent.service.db_service import db_service
from agent.models.agui import (
    ComplianceCheckStartData, ComplianceCheckCompleteData, FinalResultGenerateData
)
from agent.models.algorithm_data import AlgorithmCallbackSuccessData, ValidationRuleResult, ValidationResult
from agent.utils.logger import logger
from agent.utils.sse import sse_manager
from agent.utils.error import ErrorCode
from sqlalchemy.orm import Session
from datetime import datetime


class ComplianceNode:
    """合规检查节点（处理《数据契约与状态机.docx》合规检查流程）"""

    def __init__(self, db: Session):
        self.db = db
        self.algorithm_service = AlgorithmService()

    async def run_compliance_check(self, state: AgentState) -> Dict[str, Any]:
        """
        节点5：合规检查（执行校验规则 → 推送检查事件）
        """
        try:
            if not state.algorithm_result:
                error_msg = "算法结果缺失，无法进行合规检查"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": ErrorCode.ALGORITHM_RESULT_MISSING.name,
                    "error_msg": error_msg,
                    "failed_stage": "compliance.check"
                }

            # 推送合规检查开始事件（文档8.合规检查开始）
            check_start = ComplianceCheckStartData(
                processId=state.process_id,
                ruleCount=len(self.algorithm_service.default_model_params.validateRules) if hasattr(self.algorithm_service.default_model_params, 'validateRules') else 0,
                startTime=int(datetime.now().timestamp() * 1000)
            )
            # 创建AGUIEvent对象
            from agent.models.agui import AGUIEvent
            start_event = AGUIEvent(
                type="compliance.check.start",
                data=check_start
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=start_event
                )
                if success:
                    logger.info(f"合规检查开始事件发送成功", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""})
                else:
                    logger.warning(f"合规检查开始事件发送失败", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""})
            except Exception as e:
                logger.error(f"发送合规检查开始事件异常: {str(e)}", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""}, exc_info=True)

            # 执行合规检查（简化实现，实际应根据业务规则执行更复杂的校验）
            check_results = await self._perform_compliance_check(state.algorithm_result.extractedFields)

            # 推送合规检查完成事件（文档9.合规检查完成）
            check_complete = ComplianceCheckCompleteData(
                processId=state.process_id,
                validateResults=check_results,
                endTime=int(datetime.now().timestamp() * 1000)
            )
            # 创建AGUIEvent对象
            from agent.models.agui import AGUIEvent
            complete_event = AGUIEvent(
                type="compliance.check.complete",
                data=check_complete
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=complete_event
                )
                if success:
                    logger.info(f"合规检查完成事件发送成功", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id})
                else:
                    logger.warning(f"合规检查完成事件发送失败", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id})
            except Exception as e:
                logger.error(f"发送合规检查完成事件异常: {str(e)}", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id}, exc_info=True)

            # 更新数据库任务状态
            db_service.update_task_compliance_result(
                db=self.db,
                process_id=state.process_id,
                compliance_results=check_results
            )

            logger.info(
                f"合规检查完成: process_id={state.process_id}, result_count={len(check_results)}",
                extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id}
            )

            return {
                "compliance_results": check_results,
                "agent_state": "processing"
            }

        except Exception as e:
            error_msg = f"合规检查节点异常: {str(e)}"
            logger.error(
                error_msg,
                extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""},
                exc_info=True
            )
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.COMPLIANCE_CHECK_ERROR.name,
                "error_msg": error_msg,
                "failed_stage": "compliance.check"
            }

    async def generate_final_result(self, state: AgentState) -> Dict[str, Any]:
        """
        节点6：生成最终结果（汇总所有数据 → 推送最终结果事件）
        """
        try:
            if not state.algorithm_result:
                error_msg = "算法结果缺失，无法生成最终结果"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": ErrorCode.ALGORITHM_RESULT_MISSING.name,
                    "error_msg": error_msg,
                    "failed_stage": "result.generate"
                }

            # 构建最终结果数据
            final_result = FinalResultGenerateData(
                processId=state.process_id,
                fileInfo={
                    "fileId": state.file_id,
                    "fileName": state.file_info.fileName if state.file_info else "",
                    "fileType": state.file_info.fileName.split(".")[-1].lower() if state.file_info and "." in state.file_info.fileName else "pdf",
                    "fileSize": state.file_info.fileSize if state.file_info and hasattr(state.file_info, "fileSize") else 0
                },
                modelResult={
                    "modelId": state.algorithm_result.modelId,
                    "extractedFields": [
                        {
                            "fieldName": field.fieldName,
                            "fieldValue": field.fieldValue,
                            "confidence": field.confidence,
                            "position": field.position
                        }
                        for field in state.algorithm_result.extractedFields
                    ],
                    "startTime": state.algorithm_result.startTime,
                    "endTime": state.algorithm_result.endTime
                },
                complianceResult=state.compliance_results or [],
                totalTime=int(datetime.now().timestamp() * 1000) - state.start_time if hasattr(state, 'start_time') else 0,
                endTime=int(datetime.now().timestamp() * 1000)
            )

            # 推送最终结果生成事件（文档10.最终结果生成）
            # 创建AGUIEvent对象
            from agent.models.agui import AGUIEvent
            final_event = AGUIEvent(
                type="result.final.generate",
                data=final_result
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=final_event
                )
                if success:
                    logger.info(f"最终结果生成事件发送成功", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id})
                else:
                    logger.warning(f"最终结果生成事件发送失败", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id})
            except Exception as e:
                logger.error(f"发送最终结果生成事件异常: {str(e)}", extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id}, exc_info=True)

            # 更新数据库任务状态为完成
            db_service.update_task_status(
                db=self.db,
                process_id=state.process_id,
                status="completed",
                final_result=final_result
            )

            logger.info(
                f"最终结果生成完成: process_id={state.process_id}, status=completed",
                extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id}
            )

            return {
                "final_result": final_result,
                "agent_state": "completed"
            }

        except Exception as e:
            error_msg = f"最终结果生成节点异常: {str(e)}"
            logger.error(
                error_msg,
                extra={"processId": state.process_id, "algorithmTaskId": state.algorithm_task_id or ""},
                exc_info=True
            )
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.FINAL_RESULT_GENERATE_ERROR.name,
                "error_msg": error_msg,
                "failed_stage": "result.generate"
            }

    async def _perform_compliance_check(self, extracted_fields: List[Any]) -> List[ValidationResult]:
        """
        执行合规检查规则（示例实现）
        """
        check_results = []
        
        # 构建字段值映射
        field_values = {field.fieldName: field.fieldValue for field in extracted_fields}
        
        # 1. 必填字段检查
        required_fields = ["发票号码", "开票日期", "金额"]
        for field_name in required_fields:
            if field_name not in field_values or not field_values[field_name]:
                check_results.append(ValidateResult(
                    fieldName=field_name,
                    validateType="required",
                    isPassed=False,
                    message=f"必填字段{field_name}缺失"
                ))
            else:
                check_results.append(ValidateResult(
                    fieldName=field_name,
                    validateType="required",
                    isPassed=True,
                    message=""
                ))
        
        # 2. 发票号码格式检查（示例：10-20位数字）
        if "发票号码" in field_values and field_values["发票号码"]:
            invoice_number = field_values["发票号码"]
            if not isinstance(invoice_number, str) or not (10 <= len(invoice_number) <= 20) or not invoice_number.isdigit():
                check_results.append(ValidateResult(
                    fieldName="发票号码",
                    validateType="format",
                    isPassed=False,
                    message="发票号码格式不正确，应为10-20位数字"
                ))
            else:
                check_results.append(ValidateResult(
                    fieldName="发票号码",
                    validateType="format",
                    isPassed=True,
                    message=""
                ))
        
        # 3. 金额格式检查
        if "金额" in field_values and field_values["金额"]:
            amount = field_values["金额"]
            try:
                # 尝试转换为数字
                float(amount)
                check_results.append(ValidateResult(
                    fieldName="金额",
                    validateType="format",
                    isPassed=True,
                    message=""
                ))
            except (ValueError, TypeError):
                check_results.append(ValidateResult(
                    fieldName="金额",
                    validateType="format",
                    isPassed=False,
                    message="金额格式不正确，应为数字"
                ))
        
        return check_results