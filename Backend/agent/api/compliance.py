from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session
from agent.db.session import get_db
from agent.service.compliance_service import compliance_service
from agent.utils.logger import logger
from agent.utils.error import ErrorCode, get_error_info
from agent.utils.sse import sse_manager
from agent.models.agui import (
    AGUIEvent,
    ComplianceCheckCompleteData,
    FinalResultGenerateData,
    TaskErrorData
)
from agent.models.algorithm_data import ValidationResult

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class ComplianceCallbackData(BaseModel):
    """合规检查回调数据模型"""
    processId: str
    validateResults: List[ValidationResult]
    succeed: bool
    message: str = ""
    timestamp: int


@router.post("/callback", response_model=Dict[str, Any])
async def receive_compliance_callback(
    callback_data: ComplianceCallbackData,
    db: Session = Depends(get_db)
):
    """合规检查回调接口
    
    接收合规检查服务处理完成后的回调结果，更新任务状态并通知前端
    """
    try:
        # 日志记录
        logger.info(
            f"收到合规检查回调请求",
            extra={
                "processId": callback_data.processId,
                "succeed": callback_data.succeed,
                "resultCount": len(callback_data.validateResults)
            }
        )

        # 调用原有服务处理回调
        result = await compliance_service.handle_compliance_callback(callback_data, db)

        # 发送合规检查完成事件
        check_complete_data = ComplianceCheckCompleteData(
            processId=callback_data.processId,
            validateResults=callback_data.validateResults,
            endTime=callback_data.timestamp
        )
        check_complete_event = AGUIEvent(
            type="compliance.check.complete",
            data=check_complete_data,
            timestamp=int(datetime.now().timestamp() * 1000)
        )
        await sse_manager.send_event(
            process_id=callback_data.processId,
            event=check_complete_event
        )

        # 如果合规检查失败，发送错误事件
        if not callback_data.succeed:
            error_event = AGUIEvent(
                type="task.error",
                data=TaskErrorData(
                    processId=callback_data.processId,
                    errorCode="COMPLIANCE_CHECK_FAILED",
                    errorMsg=callback_data.message or "合规检查失败",
                    timestamp=int(datetime.now().timestamp() * 1000)
                ),
                timestamp=int(datetime.now().timestamp() * 1000)
            )
            await sse_manager.send_event(
                process_id=callback_data.processId,
                event=error_event
            )
            
            return {"status": "error", "message": callback_data.message}

        return {"status": "success", "message": "合规检查回调处理成功"}

    except Exception as e:
        logger.error(
            f"处理合规检查回调异常: {str(e)}",
            extra={"processId": callback_data.processId},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )