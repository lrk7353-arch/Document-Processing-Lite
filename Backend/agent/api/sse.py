from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response, JSONResponse
import asyncio
import json
import time
from agent.utils.logger import logger
from agent.utils.auth import get_current_user
from agent.db.session import get_db
from agent.utils.sse import sse_manager
from agent.models.agui import AGUIEvent, ConnectData
from typing import Dict, Any, Optional

# 初始化路由（严格遵循《通信机制文档.pdf》SSE端点定义）
router = APIRouter(prefix="/api/agent", tags=["AG-UI事件流"])

@router.get("/stream", summary="SSE事件流端点")
async def sse_stream(
    processId: str = Query(..., alias="processId", description="任务唯一标识")
) -> Response:
    """
    SSE事件流端点
    支持实时数据推送，无需认证（仅用于测试）
    直接使用SSEManager提供的事件生成器功能
    """
    logger.info(f"接收到SSE连接请求 - processId: {processId}")
    
    try:
        # 直接使用SSEManager的create_sse_response方法创建响应
        response = sse_manager.create_sse_response(processId)
        
        # 添加跨域支持头信息
        response.headers["Access-Control-Allow-Origin"] = "*"
        # 移除 Access-Control-Allow-Credentials 以避免与通配符 Origin 冲突
        
        # 发送初始连接成功事件
        connect_data = ConnectData(
            processId=processId,
            sseUrl=f"/api/agent/stream?processId={processId}"
        )
        connect_event = AGUIEvent(
            type="connect",
            data=connect_data,
            timestamp=int(time.time() * 1000),
            source="backend"
        )
        await sse_manager.send_event(processId, connect_event)
        
        return response
    except asyncio.TimeoutError:
        logger.error(f"SSE连接超时: processId={processId}")
        return JSONResponse(
            status_code=504,
            content={"error": "SSE连接超时，请重试"}
        )
    except ValueError as e:
        logger.error(f"SSE参数错误: {str(e)}, processId={processId}")
        return JSONResponse(
            status_code=400,
            content={"error": f"参数错误: {str(e)}"}
        )
    except RuntimeError as e:
        logger.error(f"SSE运行时错误: {str(e)}, processId={processId}")
        return JSONResponse(
            status_code=500,
            content={"error": "服务器内部错误，请稍后重试"}
        )
    except Exception as e:
        logger.error(f"SSE连接未知异常: {str(e)}, processId={processId}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "SSE连接失败，请稍后重试"}
        )