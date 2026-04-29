from typing import Dict, Any
from langgraph.graph import StateGraph
from agent.langgraph.state import AgentState
from agent.service.file_service import file_service
from agent.service.db_service import db_service
from agent.models.agui import (
    FileUploadStartData, FileUploadProgressData, FileUploadCompleteData, FileUploadErrorData,
    FileProcessStartData, FileProcessProgressData, AGUIEvent
)
from agent.utils.logger import logger
from agent.utils.sse import sse_manager
from agent.utils.error import ErrorCode
from sqlalchemy.orm import Session
from datetime import datetime


class FileNode:
    """文件上传节点（处理《数据契约与状态机.docx》文件上传流程）"""

    def __init__(self, db: Session):
        self.db = db

    async def start_file_upload(self, state: AgentState) -> Dict[str, Any]:
        """
        节点1：开始文件上传（推送"file.upload.start"事件）
        """
        try:
            # 生成文件ID（UUID简化）
            file_id = f"file-{state.process_id.split('-')[1]}" if "-" in state.process_id else f"file-{state.process_id[:8]}"

            # 推送文件上传开始事件（文档1.文件上传开始）
            start_data = FileUploadStartData(
                fileId=file_id,
                fileName=state.file_info.fileName if state.file_info else "unknown",
                fileType=state.file_info.fileType if state.file_info else "application/octet-stream",
                fileSize=state.file_info.fileSize if state.file_info else 0,
                status="init"
            )
            # 创建AGUIEvent对象
            start_event = AGUIEvent(
                type="file.upload.start",
                data=start_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=start_event
                )
                if success:
                    logger.info(f"文件上传开始事件发送成功", extra={"processId": state.process_id, "fileId": file_id})
                else:
                    logger.warning(f"文件上传开始事件发送失败", extra={"processId": state.process_id, "fileId": file_id})
            except Exception as e:
                logger.error(f"发送文件上传开始事件异常: {str(e)}", extra={"processId": state.process_id, "fileId": file_id}, exc_info=True)

            logger.info(
                f"文件上传开始: fileId={file_id}, fileName={start_event.fileName}",
                extra={"processId": state.process_id, "algorithmTaskId": ""}
            )

            return {
                "file_id": file_id,
                "agent_state": "processing",
                "file_info": start_event
            }

        except Exception as e:
            error_msg = f"文件上传开始节点异常: {str(e)}"
            logger.error(
                error_msg,
                extra={"processId": state.process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.FILE_UPLOAD_ERROR.name,
                "error_msg": error_msg,
                "failed_stage": "file.upload"
            }

    async def handle_file_upload_complete(self, state: AgentState) -> Dict[str, Any]:
        """
        节点2：文件上传完成（保存文件→创建任务→推送完成事件）
        """
        try:
            if not state.file_info:
                error_msg = "文件信息缺失，无法完成上传"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": ErrorCode.FILE_UPLOAD_ERROR.name,
                    "error_msg": error_msg,
                    "failed_stage": "file.upload"
                }

            # 1. 保存文件到本地
            file_data, file_error = await file_service.save_upload_file(
                file=state.file_info,  # 实际场景需传入UploadFile对象，此处简化
                file_id=state.file_id
            )
            if file_error:
                error_msg = f"文件保存失败: {file_error.message}"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": ""}
                )
                # 推送文件上传失败事件（文档4.文件上传失败）
                error_data = FileUploadErrorData(
                    fileId=state.file_id,
                    fileName=state.file_info.fileName,
                    errorCode=file_error.name,
                    errorMsg=error_msg,
                    failed="上传失败"
                )
                error_event = AGUIEvent(
                    type="file.upload.error",
                    data=error_data
                )
                try:
                    success = await sse_manager.send_event(
                        process_id=state.process_id,
                        event=error_event
                    )
                    if success:
                        logger.info(f"文件上传失败事件发送成功", extra={"processId": state.process_id, "fileId": state.file_id})
                    else:
                        logger.warning(f"文件上传失败事件发送失败", extra={"processId": state.process_id, "fileId": state.file_id})
                except Exception as e:
                    logger.error(f"发送文件上传失败事件异常: {str(e)}", extra={"processId": state.process_id, "fileId": state.file_id}, exc_info=True)
                return {
                    "agent_state": "failed",
                    "error_code": file_error.name,
                    "error_msg": error_msg,
                    "failed_stage": "file.upload"
                }

            # 2. 创建数据库任务
            process_id, db_error = db_service.create_task_from_file(
                db=self.db,
                file_data=file_data
            )
            if db_error:
                error_msg = f"任务创建失败: {db_error.message}"
                logger.error(
                    error_msg,
                    extra={"processId": state.process_id, "algorithmTaskId": ""}
                )
                return {
                    "agent_state": "failed",
                    "error_code": db_error.name,
                    "error_msg": error_msg,
                    "failed_stage": "file.upload"
                }

            # 3. 推送文件上传完成事件（文档3.文件上传完成）
            complete_event = AGUIEvent(
                type="file.upload.complete",
                data=file_data
            )
            try:
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=complete_event
                )
                if success:
                    logger.info(f"文件上传完成事件发送成功", extra={"processId": state.process_id, "fileId": file_data.fileId})
                else:
                    logger.warning(f"文件上传完成事件发送失败", extra={"processId": state.process_id, "fileId": file_data.fileId})
                
                # 4. 推送文件处理开始事件
                process_data = FileProcessStartData(
                    processId=state.process_id,
                    fileId=file_data.fileId,
                    startTime=int(datetime.now().timestamp() * 1000)
                )
                process_event = AGUIEvent(
                    type="file.process.start",
                    data=process_data
                )
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=process_event
                )
                if success:
                    logger.info(f"文件处理开始事件发送成功", extra={"processId": state.process_id, "fileId": file_data.fileId})
                else:
                    logger.warning(f"文件处理开始事件发送失败", extra={"processId": state.process_id, "fileId": file_data.fileId})
                
                # 5. 推送文件处理进度事件
                progress_data = FileProcessProgressData(
                    processId=state.process_id,
                    fileId=file_data.fileId,
                    progress=20,
                    stage="文件预处理"
                )
                progress_event = AGUIEvent(
                    type="file.process.progress",
                    data=progress_data
                )
                success = await sse_manager.send_event(
                    process_id=state.process_id,
                    event=progress_event
                )
                if success:
                    logger.info(f"文件处理进度事件发送成功", extra={"processId": state.process_id, "fileId": file_data.fileId})
                else:
                    logger.warning(f"文件处理进度事件发送失败", extra={"processId": state.process_id, "fileId": file_data.fileId})
            except Exception as e:
                logger.error(f"发送文件完成/处理事件异常: {str(e)}", extra={"processId": state.process_id, "fileId": file_data.fileId}, exc_info=True)

            logger.info(
                f"文件上传完成: process_id={state.process_id}, fileId={file_data.fileId}",
                extra={"processId": state.process_id, "algorithmTaskId": ""}
            )

            return {
                "process_id": process_id,
                "file_id": file_data.fileId,
                "file_info": file_data,
                "agent_state": "processing"
            }

        except Exception as e:
            error_msg = f"文件上传完成节点异常: {str(e)}"
            logger.error(
                error_msg,
                extra={"processId": state.process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return {
                "agent_state": "failed",
                "error_code": ErrorCode.SYSTEM_ERROR.name,
                "error_msg": error_msg,
                "failed_stage": "file.upload"
            }