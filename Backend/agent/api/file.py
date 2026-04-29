from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime
import os
import asyncio
from agent.db.session import get_db
# 注释掉LangGraph相关导入，避免依赖问题
# from agent.langgraph.graph import build_agent_graph
# from agent.langgraph.state import AgentState
from agent.utils.logger import logger
from agent.utils.error import ErrorCode, get_error_info
from agent.utils.auth import get_current_user
from agent.utils.sse import sse_manager
from agent.models.agui import (
    AGUIEvent,
    FileUploadStartData,
    FileUploadProgressData,
    FileUploadCompleteData,
    FileProcessStartData,
    FileProcessProgressData,
    FileProcessCompleteData,
    TaskErrorData,
    ConnectData
)
from sqlalchemy.orm import Session

# 初始化路由（对齐《通信机制文档.pdf》"文件上传事件"接口）
router = APIRouter(prefix="/api/file", tags=["文件操作"])

@router.post("/upload", summary="文件上传接口")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """
    文件上传接口（遵循《通信机制文档.pdf》"文件上传事件"定义）
    步骤：1. 接收文件 2. 启动智能体工作流 3. 返回任务标识
    """
    try:
        # 1. 验证文件类型（仅支持PDF/图片，测试阶段暂时允许txt文件）
        allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/svg+xml", "text/plain"]
        allowed_extensions = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml", ".txt": "text/plain"}
        
        # 获取文件扩展名
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        # 确定使用的MIME类型
        mime_type = file.content_type
        
        # 先尝试通过Content-Type验证
        if file.content_type not in allowed_types:
            # 如果Content-Type验证失败，尝试通过文件扩展名判断
            if file_extension not in allowed_extensions:
                logger.error(
                    f"文件类型不支持: Content-Type={file.content_type}, 扩展名={file_extension}",
                    extra={"processId": "", "algorithmTaskId": "", "userId": current_user.get("sub")}
                )
                raise HTTPException(
                    status_code=400,
                    detail=get_error_info(ErrorCode.FILE_TYPE_INVALID)
                )
            else:
                # 使用扩展名对应的MIME类型
                mime_type = allowed_extensions[file_extension]
                logger.warning(
                    f"通过文件扩展名修正Content-Type: {file_extension} -> {mime_type}",
                    extra={"processId": "", "algorithmTaskId": "", "userId": current_user.get("sub")}
                )

        # 2. 生成唯一的process_id
        import uuid
        process_id = f"proc-{file.filename.split('.')[0]}-{str(uuid.uuid4())[:8]}"
        
        # 3. 生成文件ID
        file_id = str(uuid.uuid4())
        
        # 先获取文件内容以确定大小
        content = await file.read()
        file_size = len(content)
        
        # 重置文件指针
        await file.seek(0)
        
        # 5. 创建SSE队列并建立连接
        await sse_manager.create_queue(process_id)
        
        # 5.1 发送连接建立事件
        connect_data = ConnectData(
            processId=process_id,
            sseUrl=f"/api/agent/stream?processId={process_id}"
        )
        connect_event = AGUIEvent(
            type="connect",
            data=connect_data,
            timestamp=int(datetime.now().timestamp() * 1000),
            source="backend"
        )
        await sse_manager.send_event(process_id=process_id, event=connect_event)
        
        # 5.2 创建并发送文件上传开始事件
        start_data = FileUploadStartData(
            fileId=file_id,
            fileName=file.filename,
            fileType=mime_type,
            fileSize=file_size
        )
        start_event = AGUIEvent(
            type="file.upload.start",
            data=start_data,
            timestamp=int(datetime.now().timestamp() * 1000),
            source="backend"
        )
        await sse_manager.send_event(process_id=process_id, event=start_event)
        
        # 3. 初始化智能体状态（暂时注释掉，因为移除了LangGraph依赖）
        # initial_state = AgentState(
        #     process_id=process_id,
        #     file_id=file_id,
        #     agent_state="processing",
        #     file_info=None  # 将在文件保存后设置
        # )

        # 6. 保存上传的文件
        from agent.config import settings
        import hashlib
        
        # 确保上传目录存在
        upload_path = settings.upload_dir / process_id
        upload_path.mkdir(exist_ok=True, parents=True)
        
        # 保存文件
        file_path = upload_path / file.filename
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 计算文件MD5
        md5_hash = hashlib.md5(content).hexdigest()
        
        # 5. 发送文件上传进度事件
        content_length = len(content)
        progress_data = FileUploadProgressData(
            fileId=file_id,
            progress=50,
            uploadedSize=content_length // 2,
            totalSize=content_length
        )
        progress_event = AGUIEvent(
            type="file.upload.progress",
            data=progress_data,
            source="backend"
        )
        try:
            success = await sse_manager.send_event(process_id=process_id, event=progress_event)
            if success:
                logger.info(f"文件上传进度事件发送成功: {progress_data.progress}%", extra={"processId": process_id, "fileId": file_id})
            else:
                logger.warning(f"文件上传进度事件发送失败", extra={"processId": process_id, "fileId": file_id})
        except Exception as e:
            logger.error(f"发送文件上传进度事件异常: {str(e)}", extra={"processId": process_id, "fileId": file_id}, exc_info=True)
        
        # 5. 构建并启动文档处理流程
        # 调用算法服务进行实际的文档处理
        try:
            # 导入算法服务客户端
            from agent.service.algorithm_client import AlgorithmClient
            
            # 创建算法服务客户端
            algo_client = AlgorithmClient()
            
            # 异步启动文档处理任务
            async def process_document():
                try:
                    # 调用算法服务进行文档处理
                    logger.info(
                        f"开始调用算法服务处理文档: {file.filename}",
                        extra={"processId": process_id, "fileId": file_id}
                    )
                    
                    # 发送进度更新事件
                    progress_data = FileProcessProgressData(
                        processId=process_id,
                        fileId=file_id,
                        progress=30,
                        stage="文档解析中"
                    )
                    progress_event = AGUIEvent(
                        type="file.process.progress",
                        data=progress_data,
                        source="backend"
                    )
                    await sse_manager.send_event(process_id=process_id, event=progress_event)
                    
                    # 调用算法服务处理文件
                    result = await algo_client.process_document(
                        file_path=str(file_path),
                        file_type=mime_type,
                        process_id=process_id
                    )
                    
                    # 发送处理完成事件
                    complete_data = FileProcessCompleteData(
                        processId=process_id,
                        fileId=file_id,
                        succeed=True,
                        message="文档处理成功",
                        timestamp=int(datetime.now().timestamp() * 1000)
                    )
                    complete_event = AGUIEvent(
                        type="file.process.complete",
                        data=complete_data,
                        source="backend"
                    )
                    await sse_manager.send_event(process_id=process_id, event=complete_event)
                    
                    logger.info(
                        f"文档处理完成",
                        extra={"processId": process_id, "fileId": file_id}
                    )
                    
                except Exception as e:
                    logger.error(
                        f"文档处理失败: {str(e)}",
                        extra={"processId": process_id, "fileId": file_id},
                        exc_info=True
                    )
                    
                    # 发送错误事件
                    error_data = TaskErrorData(
                        processId=process_id,
                        failedStage="file.process",
                        errorCode="PROCESS_ERROR",
                        errorMsg=f"文档处理失败: {str(e)}"
                    )
                    error_event = AGUIEvent(
                        type="task.error",
                        data=error_data,
                        source="backend"
                    )
                    await sse_manager.send_event(process_id=process_id, event=error_event)
            
            # 启动异步处理任务
            asyncio.create_task(process_document())
            
            logger.info(
                f"文档处理任务已启动",
                extra={"processId": process_id, "algorithmTaskId": "", "userId": current_user.get("sub")}
            )
            
        except Exception as e:
            logger.error(
                f"启动文档处理任务失败: {str(e)}",
                extra={"processId": process_id, "algorithmTaskId": "", "userId": current_user.get("sub")},
                exc_info=True
            )
            # 即使工作流启动失败，也返回成功响应，让前端通过SSE获取后续状态
        
        # 7. 发送文件上传完成事件
        complete_data = FileUploadCompleteData(
            fileId=file_id,
            fileName=file.filename,
            storagePath=str(file_path),
            md5=md5_hash,
            finishTime=int(datetime.now().timestamp() * 1000),
            fileSize=file_size,
            fileType=mime_type
        )
        complete_event = AGUIEvent(
            type="file.upload.complete",
            data=complete_data,
            source="backend"
        )
        try:
            success = await sse_manager.send_event(process_id=process_id, event=complete_event)
            if success:
                logger.info(f"文件上传完成事件发送成功", extra={"processId": process_id, "fileId": file_id})
            else:
                logger.warning(f"文件上传完成事件发送失败", extra={"processId": process_id, "fileId": file_id})
        except Exception as e:
            logger.error(f"发送文件上传完成事件异常: {str(e)}", extra={"processId": process_id, "fileId": file_id}, exc_info=True)
        
        # 8. 发送文件处理开始事件
        process_data = FileProcessStartData(
            processId=process_id,
            fileId=file_id,
            startTime=int(datetime.now().timestamp() * 1000)
        )
        process_event = AGUIEvent(
            type="file.process.start",
            data=process_data,
            source="backend"
        )
        try:
            success = await sse_manager.send_event(process_id=process_id, event=process_event)
            if success:
                logger.info(f"文件处理开始事件发送成功", extra={"processId": process_id, "fileId": file_id})
            else:
                logger.warning(f"文件处理开始事件发送失败", extra={"processId": process_id, "fileId": file_id})
        except Exception as e:
            logger.error(f"发送文件处理开始事件异常: {str(e)}", extra={"processId": process_id, "fileId": file_id}, exc_info=True)
        
        # 9. 返回任务标识（供前端订阅SSE）
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": "文件上传受理成功",
                "data": {
                    "processId": process_id,
                    "fileId": file_id,
                    "sseUrl": f"/api/agent/stream?processId={process_id}"  # SSE订阅地址
                }
            }
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
                f"文件上传接口异常: {str(e)}",
                extra={"processId": "", "algorithmTaskId": "", "userId": current_user.get("sub")},
                exc_info=True
            )
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )