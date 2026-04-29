from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from agent.db.session import get_db
from agent.db.crud.task import get_task_by_process_id
from agent.utils.logger import logger
from agent.utils.auth import get_current_user
from agent.utils.error import ErrorCode, get_error_info

# 初始化路由
router = APIRouter(prefix="/api/task", tags=["任务管理"])

@router.get("/{process_id}", summary="获取任务详情")
async def get_task_detail(
    process_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    根据process_id获取任务详情
    
    Args:
        process_id: 任务处理ID
        db: 数据库会话
        current_user: 当前用户信息
    
    Returns:
        任务详情信息
    
    Raises:
        HTTPException: 任务不存在时抛出404异常
    """
    try:
        logger.info(f"查询任务详情: process_id={process_id}", extra={"processId": process_id, "algorithmTaskId": ""})
        
        # 查询任务
        task = get_task_by_process_id(db, process_id)
        
        if not task:
            logger.error(f"任务不存在: process_id={process_id}", extra={"processId": process_id, "algorithmTaskId": ""})
            raise HTTPException(
                status_code=404,
                detail=get_error_info(ErrorCode.TASK_NOT_FOUND)
            )
        
        # 构建任务详情响应
        task_detail = {
            "processId": task.process_id,
            "status": task.status,
            "fileId": task.file_id,
            "fileName": task.file_name,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
            "algorithmTaskId": task.algorithm_task_id,
            "errorCode": task.error_code,
            "errorMessage": task.error_message
        }
        
        return task_detail
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情异常: {str(e)}", extra={"processId": process_id, "algorithmTaskId": ""}, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )

@router.get("/", summary="查询任务列表")
async def get_tasks(
    status: Optional[str] = Query(None, description="任务状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    查询任务列表，支持状态筛选和分页
    
    Args:
        status: 任务状态筛选条件
        page: 页码
        pageSize: 每页数量
        db: 数据库会话
        current_user: 当前用户信息
    
    Returns:
        任务列表和分页信息
    """
    try:
        logger.info(f"查询任务列表: status={status}, page={page}, pageSize={pageSize}", 
                   extra={"processId": "", "algorithmTaskId": ""})
        
        # 这里应该从数据库查询任务列表
        # 简化实现，返回空列表
        tasks = []
        total = 0
        
        return {
            "tasks": tasks,
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "total": total,
                "totalPages": (total + pageSize - 1) // pageSize
            }
        }
        
    except Exception as e:
        logger.error(f"查询任务列表异常: {str(e)}", extra={"processId": "", "algorithmTaskId": ""}, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )