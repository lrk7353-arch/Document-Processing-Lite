from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from agent.db.session import get_db
from agent.db.crud.task import get_task_by_process_id, update_task_state
from agent.utils.logger import logger
from agent.utils.error import ErrorCode, get_error_info
from agent.utils.sse import sse_manager
from agent.utils.auth import get_current_user
from agent.models.agui import AGUIEvent, TaskTotalProgressData
from agent.models.db import UserAction

# 初始化路由（严格遵循AG-UI协议的Action处理）
router = APIRouter(prefix="/api/agent", tags=["用户操作处理"])


# Action请求模型
class ActionRequest(BaseModel):
    """用户操作请求模型"""
    processId: str = Field(..., description="任务唯一标识")
    actionType: str = Field(..., description="操作类型: confirm_result/retry_process/modify_field/cancel_task/pause_task/resume_task/download_result/export_report/share_result/save_draft")
    actionData: Dict[str, Any] = Field(..., description="操作数据")
    userId: Optional[str] = Field(None, description="用户ID")


# 支持的操作类型
SUPPORTED_ACTIONS = ["confirm_result", "retry_process", "modify_field", "cancel_task", "pause_task", "resume_task", "download_result", "export_report", "share_result", "save_draft"]


@router.post("/action", summary="接收前端用户操作")
async def handle_user_action(
    action_request: ActionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """
    接收并处理前端用户操作（AG-UI协议扩展）
    功能：接收用户确认结果、重试处理、修改字段等操作，并更新任务状态
    """
    try:
        process_id = action_request.processId
        action_type = action_request.actionType
        action_data = action_request.actionData
        user_id = action_request.userId or current_user.get("sub", "anonymous")
        
        # 1. 验证操作类型
        if action_type not in SUPPORTED_ACTIONS:
            logger.error(
                f"用户操作失败：不支持的操作类型: action_type={action_type}",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
            raise HTTPException(
                status_code=400,
                detail=get_error_info(ErrorCode.AGENT_ACTION_NOT_SUPPORTED)
            )
            
        # 2. 验证任务存在性，必须进行数据库验证
        try:
            db_task = get_task_by_process_id(db=db, process_id=process_id)
            if not db_task:
                logger.error(
                    f"任务不存在: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=404,
                    detail=get_error_info(ErrorCode.TASK_NOT_FOUND)
                )
        except HTTPException:
            raise
        except Exception as db_error:
            logger.error(
                f"数据库查询失败: {str(db_error)}",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
            raise HTTPException(
                status_code=500,
                detail=get_error_info(ErrorCode.DATABASE_ERROR)
            )
        
        # 3. 生成操作ID
        action_id = str(uuid.uuid4())
        
        # 4. 记录用户操作到数据库，必须确保成功
        try:
            user_action = UserAction(
                action_id=action_id,
                process_id=process_id,
                action_type=action_type,
                action_data=action_data,
                user_id=user_id,
                action_time=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db.add(user_action)
            logger.info(
                f"用户操作已记录到数据库: action_id={action_id}, action_type={action_type}",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
        except Exception as db_error:
            logger.error(
                f"数据库记录操作失败: {str(db_error)}",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
            raise HTTPException(
                status_code=500,
                detail=get_error_info(ErrorCode.DATABASE_ERROR)
            )
        
        # 5. 根据操作类型执行相应处理
        response_message = ""
        if action_type == "confirm_result":
            # 确认结果：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="completed")
                logger.info(
                    f"任务状态已更新为完成: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "结果已确认"
            
            # 推送任务完成事件
            task_progress = TaskTotalProgressData(
                processId=process_id,
                progress=100,
                currentStage="completed",
                stageProgress=100,
                message="用户已确认结果，任务完成"
            )
            progress_event = AGUIEvent(
                type="task.total.progress",
                data=task_progress
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=progress_event
                )
                if success:
                    logger.info(f"任务完成进度事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"任务完成进度事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送任务完成进度事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "retry_process":
            # 重试处理：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="processing")
                logger.info(
                    f"任务状态已更新为处理中: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "任务已重新开始处理"
            
            # 推送任务重试事件
            task_progress = TaskTotalProgressData(
                processId=process_id,
                progress=0,
                currentStage="retry",
                stageProgress=0,
                message="用户请求重试处理"
            )
            progress_event = AGUIEvent(
                type="task.total.progress",
                data=task_progress
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=progress_event
                )
                if success:
                    logger.info(f"任务重试进度事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"任务重试进度事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送任务重试进度事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
            # 这里可以添加重新触发工作流的逻辑
            # 例如调用状态机的相应节点
            
        elif action_type == "modify_field":
            # 修改字段：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="awaiting_input")
                logger.info(
                    f"任务状态已更新为等待输入: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "字段已修改"
            
            # 推送字段修改事件
            event_data = {
                "processId": process_id,
                "modifiedFields": action_data,
                "userId": user_id
            }
            modify_event = AGUIEvent(
                type="user.action.modify_field",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=modify_event
                )
                if success:
                    logger.info(f"字段修改事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"字段修改事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送字段修改事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "cancel_task":
            # 取消任务：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="canceled")
                logger.info(
                    f"任务状态已更新为已取消: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "任务已取消"
            
            # 推送任务取消事件
            task_progress = TaskTotalProgressData(
                processId=process_id,
                progress=0,
                currentStage="canceled",
                stageProgress=0,
                message="用户已取消任务"
            )
            progress_event = AGUIEvent(
                type="task.total.progress",
                data=task_progress
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=progress_event
                )
                if success:
                    logger.info(f"任务取消进度事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"任务取消进度事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送任务取消进度事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "pause_task":
            # 暂停任务：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="paused")
                logger.info(
                    f"任务状态已更新为已暂停: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "任务已暂停"
            
            # 推送任务暂停事件
            event_data = {
                "processId": process_id,
                "userId": user_id
            }
            pause_event = AGUIEvent(
                type="user.action.pause_task",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=pause_event
                )
                if success:
                    logger.info(f"任务暂停事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"任务暂停事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送任务暂停事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "resume_task":
            # 恢复任务：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="processing")
                logger.info(
                    f"任务状态已更新为处理中: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "任务已恢复"
            
            # 推送任务恢复事件
            event_data = {
                "processId": process_id,
                "userId": user_id
            }
            resume_event = AGUIEvent(
                type="user.action.resume_task",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=resume_event
                )
                if success:
                    logger.info(f"任务恢复事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"任务恢复事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送任务恢复事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "download_result":
            # 下载结果：记录操作但不改变任务状态
            response_message = "下载请求已记录"
            
            # 推送下载请求事件
            event_data = {
                "processId": process_id,
                "userId": user_id,
                "downloadOptions": action_data.get("options", {})
            }
            download_event = AGUIEvent(
                type="user.action.download_result",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=download_event
                )
                if success:
                    logger.info(f"下载请求事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"下载请求事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送下载请求事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "export_report":
            # 导出报告：记录操作但不改变任务状态
            response_message = "报告导出请求已记录"
            
            # 推送导出报告事件
            event_data = {
                "processId": process_id,
                "userId": user_id,
                "reportType": action_data.get("reportType", "pdf"),
                "reportOptions": action_data.get("options", {})
            }
            export_event = AGUIEvent(
                type="user.action.export_report",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=export_event
                )
                if success:
                    logger.info(f"导出报告事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"导出报告事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送导出报告事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "share_result":
            # 分享结果：记录操作但不改变任务状态
            response_message = "结果分享请求已记录"
            
            # 推送分享结果事件
            event_data = {
                "processId": process_id,
                "userId": user_id,
                "shareTargets": action_data.get("shareTargets", []),
                "shareOptions": action_data.get("options", {})
            }
            share_event = AGUIEvent(
                type="user.action.share_result",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=share_event
                )
                if success:
                    logger.info(f"分享结果事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"分享结果事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送分享结果事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
            
        elif action_type == "save_draft":
            # 保存草稿：必须更新任务状态
            try:
                update_task_state(db=db, process_id=process_id, state="draft")
                logger.info(
                    f"任务状态已更新为草稿: process_id={process_id}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
            except Exception as db_error:
                logger.error(
                    f"数据库更新状态失败: {str(db_error)}",
                    extra={"processId": process_id, "algorithmTaskId": ""}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.DATABASE_ERROR)
                )
                
            response_message = "草稿已保存"
            
            # 推送保存草稿事件
            event_data = {
                "processId": process_id,
                "userId": user_id,
                "draftContent": action_data.get("content", {})
            }
            save_event = AGUIEvent(
                type="user.action.save_draft",
                data=event_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=process_id,
                    event=save_event
                )
                if success:
                    logger.info(f"保存草稿事件发送成功", extra={"processId": process_id, "algorithmTaskId": ""})
                else:
                    logger.warning(f"保存草稿事件发送失败", extra={"processId": process_id, "algorithmTaskId": ""})
            except Exception as e:
                logger.error(f"发送保存草稿事件异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
        
        # 必须提交数据库事务，确保操作成功
        try:
            db.commit()
            logger.info(
                f"用户操作处理成功: action_type={action_type}, process_id={process_id}",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
        except Exception as db_error:
            logger.error(
                f"数据库提交失败: {str(db_error)}",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=get_error_info(ErrorCode.DATABASE_ERROR)
            )
        
        # 5. 返回成功响应
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": response_message,
                "data": {
                    "processId": process_id,
                    "actionId": action_id,
                    "actionType": action_type,
                    "timestamp": int(datetime.now().timestamp() * 1000)
                }
            }
        )
        
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        logger.error(
            f"用户操作处理异常: {str(e)}",
            extra={"processId": action_request.processId if hasattr(action_request, 'processId') else "", "algorithmTaskId": ""},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )

@router.get("/actions", summary="获取任务操作历史")
async def get_task_actions(
    process_id: str = Query(..., description="任务唯一标识"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """
    获取指定任务的所有用户操作历史
    """
    try:
        # 验证任务存在性
        db_task = get_task_by_process_id(db=db, process_id=process_id)
        if not db_task:
            raise HTTPException(
                status_code=404,
                detail={"errorCode": "TASK_NOT_FOUND", "errorMsg": "任务不存在"}
            )
        
        # 查询操作历史
        actions = db.query(UserAction).filter(
            UserAction.process_id == process_id
        ).order_by(UserAction.action_time.desc()).all()
        
        # 格式化返回数据
        action_history = [
            {
                "actionId": action.action_id,
                "actionType": action.action_type,
                "actionData": action.action_data,
                "userId": action.user_id,
                "actionTime": action.action_time.isoformat(),
                "createdAt": action.created_at.isoformat()
            }
            for action in actions
        ]
        
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": "操作历史获取成功",
                "data": {
                    "processId": process_id,
                    "actions": action_history,
                    "total": len(action_history)
                }
            }
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            f"获取操作历史异常: {str(e)}",
            extra={"processId": process_id, "algorithmTaskId": ""},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )