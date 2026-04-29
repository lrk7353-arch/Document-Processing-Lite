from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
from agent.db.session import get_db
from agent.service.algorithm_service import algorithm_service
from agent.models.algorithm_data import AlgorithmCallbackSuccessData, AlgorithmCallbackErrorData
from agent.utils.logger import logger
from agent.utils.error import ErrorCode

router = APIRouter(prefix="/api/algorithm", tags=["算法服务"])


@router.post("/callback", summary="算法结果回调接口")
async def algorithm_callback(
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    接收算法服务的回调结果
    支持成功和失败两种回调类型
    """
    try:
        # 获取请求体
        callback_data = await request.json()
        logger.info(f"收到算法回调请求: {callback_data}")
        
        # 验证必需字段
        if "processId" not in callback_data or "algorithmTaskId" not in callback_data:
            raise HTTPException(status_code=400, detail="缺少必要的回调参数")
        
        # 根据回调类型处理
        if "status" in callback_data and callback_data["status"] == "success":
            # 处理成功回调
            success_data = AlgorithmCallbackSuccessData(**callback_data)
            result = await algorithm_service.handle_algorithm_callback(success_data, db)
        else:
            # 处理失败回调
            error_data = AlgorithmCallbackErrorData(**callback_data)
            result = await algorithm_service.handle_algorithm_callback(error_data, db)
        
        logger.info(
            f"算法回调处理完成: {callback_data['algorithmTaskId']}",
            extra={"processId": callback_data.get("processId", ""), "algorithmTaskId": callback_data["algorithmTaskId"]}
        )
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "回调处理成功"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"算法回调处理异常: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "回调处理失败", "error": str(e)}
        )