from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Union, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session
from agent.db.session import get_db
from agent.service.db_service import db_service
from agent.utils.logger import logger
from agent.utils.error import ErrorCode, get_error_info
from agent.utils.sse import sse_manager
from agent.models.agui import (
    AGUIEvent,
    ModelProcessProgressData,
    ModelExtractCompleteData,
    FieldDetail,
    TaskErrorData
)
from agent.models.algorithm_data import (
    AlgorithmCallbackSuccessData, 
    AlgorithmCallbackErrorData,
    AlgorithmRequest,
    AlgorithmResponse,
    FileInfo,
    ModelParams,
    ValidationParams
)
from agent.service.algorithm_service import algorithm_service
from agent.config import settings
from agent.db.crud.algorithm import get_algorithm_task_by_process_id

router = APIRouter(prefix="/api/algorithm", tags=["算法回调"])  # 修改路由前缀以匹配文档

class AlgorithmProcessRequest(BaseModel):
    """算法处理请求模型"""
    fileInfo: FileInfo
    modelParams: ModelParams
    processId: Optional[str] = None
    validationParams: Optional[ValidationParams] = None

@router.post("/process", summary="处理文档的主接口", response_model=AlgorithmResponse)
async def process_document(
    request_data: AlgorithmProcessRequest
):
    """处理文档的主接口"""
    try:
        # 记录请求日志
        logger.info(
            f"收到文档处理请求",
            extra={
                "fileId": request_data.fileInfo.fileId,
                "modelId": request_data.modelParams.modelId,
                "processId": request_data.processId
            }
        )
        
        # 准备调用算法服务的参数
        file_info_dict = {
            "fileId": request_data.fileInfo.fileId,
            "storagePath": request_data.fileInfo.storagePath,
            "fileType": request_data.fileInfo.fileType,
            "fileSize": request_data.fileInfo.fileSize
        }
        
        callback_url = f"{settings.callback_base}/api/algorithm/callback"
        need_validation = request_data.validationParams.needValidation if request_data.validationParams else False
        
        # 调用算法服务
        try:
            logger.info(
                f"准备调用算法服务",
                extra={
                    "process_id": request_data.processId,
                    "file_info": file_info_dict,
                    "callback_url": callback_url,
                    "need_validation": need_validation
                }
            )
            
            algorithm_response, error_code = await algorithm_service.call_algorithm_api(
                process_id=request_data.processId,
                file_info=file_info_dict,
                callback_url=callback_url,
                need_validation=need_validation
            )
            
            logger.info(
                f"算法服务调用完成",
                extra={
                    "algorithm_response": algorithm_response,
                    "error_code": error_code
                }
            )
            
            # 构建响应
            if error_code:
                logger.error(
                    f"算法服务返回错误码",
                    extra={"error_code": error_code}
                )
                raise HTTPException(
                    status_code=500,
                    detail=get_error_info(ErrorCode.SYSTEM_ERROR)
                )
                
        except Exception as e:
            logger.error(
                f"调用算法服务过程中发生异常: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail=get_error_info(ErrorCode.SYSTEM_ERROR)
            )
        
        # 构建AlgorithmResponse对象直接返回
        return algorithm_response
        
    except Exception as e:
        logger.error(
            f"处理文档请求失败: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )

class FieldExtract(BaseModel):
    """字段提取结果模型"""
    fieldName: str
    fieldValue: str
    confidence: float = Field(default=0.0)
    position: Optional[str] = Field(default="", description="字段位置")

@router.post("/callback", summary="接收算法组回调结果", response_model=Dict[str, Any])
async def receive_algorithm_callback(
    callback_data: Union[AlgorithmCallbackSuccessData, AlgorithmCallbackErrorData],
    db: Session = Depends(get_db)
):
    """算法回调接口
    
    接收算法服务处理完成后的回调结果，更新任务状态并通知前端
    """
    try:
        # 日志记录
        logger.info(
            f"收到算法回调请求",
            extra={
                "processId": callback_data.processId,
                "algorithmTaskId": callback_data.algorithmTaskId,
                "taskType": "callback"
            }
        )

        # 根据回调类型处理
        if isinstance(callback_data, AlgorithmCallbackErrorData):
            # 处理错误情况
            logger.error(
                f"算法处理失败: {callback_data.errorMsg}",
                extra={
                    "processId": callback_data.processId,
                    "algorithmTaskId": callback_data.algorithmTaskId,
                    "errorCode": callback_data.errorCode
                }
            )
            
            # 简化处理：只记录日志，不更新数据库
            logger.info(
                f"处理失败回调: processId={callback_data.processId}, algorithmTaskId={callback_data.algorithmTaskId}",
                extra={
                    "processId": callback_data.processId,
                    "algorithmTaskId": callback_data.algorithmTaskId,
                    "errorCode": callback_data.errorCode,
                    "errorMsg": callback_data.errorMsg
                }
            )
            
            # 尝试发送错误事件给前端
            try:
                failed_stage = "model.process"
                try:
                    if getattr(callback_data, "errorCode", "") == "VALIDATION_FAILED" or (
                        "校验" in str(getattr(callback_data, "errorMsg", ""))
                    ):
                        failed_stage = "compliance.check"
                except Exception:
                    failed_stage = "model.process"

                error_event = AGUIEvent(
                    type="task.error",
                    data=TaskErrorData(
                        processId=callback_data.processId,
                        failedStage=failed_stage,
                        errorCode=callback_data.errorCode,
                        errorMsg=callback_data.errorMsg
                    ),
                    timestamp=int(datetime.now().timestamp() * 1000)
                )
                await sse_manager.send_event(
                    process_id=callback_data.processId,
                    event=error_event
                )
            except Exception as sse_error:
                logger.warning(f"SSE通知发送失败，但不影响回调处理: {str(sse_error)}")
            
            return {"status": "error", "message": callback_data.errorMsg}
        
        else:
            # 处理成功情况
            logger.info(
                f"算法处理成功，提取字段数: {len(callback_data.extractedFields)}",
                extra={
                    "processId": callback_data.processId,
                    "algorithmTaskId": callback_data.algorithmTaskId
                }
            )
            
            # 保存算法结果到数据库，供工作流使用
            save_result, error = await db_service.save_algorithm_result_async(db, callback_data)
            if save_result:
                logger.info(
                    f"处理成功回调并保存结果: processId={callback_data.processId}, algorithmTaskId={callback_data.algorithmTaskId}",
                    extra={
                        "processId": callback_data.processId,
                        "algorithmTaskId": callback_data.algorithmTaskId,
                        "extractedFieldsCount": len(callback_data.extractedFields)
                    }
                )
            else:
                logger.error(
                    f"保存算法结果失败: {error}",
                    extra={
                        "processId": callback_data.processId,
                        "algorithmTaskId": callback_data.algorithmTaskId
                    }
                )
            
            # 转换为前端需要的格式
            field_details = []
            for field in callback_data.extractedFields:
                # 检查field是否为字典，如果是则使用get方法，否则直接访问属性
                if isinstance(field, dict):
                    field_detail = FieldDetail(
                        fieldName=field.get("fieldName", ""),
                        fieldValue=field.get("fieldValue", ""),
                        confidence=field.get("confidence", 0.0),
                        position=field.get("position", {})
                    )
                else:
                    field_detail = FieldDetail(
                        fieldName=field.fieldName,
                        fieldValue=field.fieldValue,
                        confidence=field.confidence,
                        position=field.position
                    )
                field_details.append(field_detail)
            
            # 尝试发送模型提取完成事件
            try:
                extract_complete_data = ModelExtractCompleteData(
                    processId=callback_data.processId,
                    modelId=callback_data.modelId,
                    extractedFields=field_details,
                    endTime=callback_data.endTime
                )
                extract_complete_event = AGUIEvent(
                    type="model.extract.complete",
                    data=extract_complete_data,
                    timestamp=int(datetime.now().timestamp() * 1000)
                )
                await sse_manager.send_event(
                    process_id=callback_data.processId,
                    event=extract_complete_event
                )
            except Exception as sse_error:
                logger.warning(f"SSE通知发送失败，但不影响回调处理: {str(sse_error)}")
            
            # 触发合规检查流程并推送相关事件
            try:
                from agent.service.compliance_service import compliance_service
                complete_result, comp_err = await compliance_service.start_compliance_check(
                    db=db,
                    process_id=callback_data.processId,
                    extracted_fields=callback_data.extractedFields
                )
                if comp_err:
                    logger.error(
                        f"合规检查失败: {comp_err}",
                        extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
                    )
            except Exception as check_error:
                logger.warning(
                    f"合规检查触发异常，但不影响回调处理: {str(check_error)}",
                    extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
                )
            
            return {"status": "success", "message": "算法回调处理成功"}
    
    except HTTPException as http_exc:
        # 如果是422错误，记录详细的验证错误信息
        if http_exc.status_code == 422:
            logger.error(
                f"算法回调数据验证失败 (422): 可能是字段类型不匹配，详细信息: {str(http_exc.detail)}",
                exc_info=True
            )
        raise
    except ValueError as val_err:
        logger.error(
            f"算法回调数据值错误: {str(val_err)}",
            extra={"processId": getattr(callback_data, 'processId', 'unknown')}, 
            exc_info=True
        )
        # 返回成功响应，避免算法服务反复重试
        return {"status": "success", "message": "回调已接收"}
    except Exception as e:
        logger.error(
            f"处理算法回调异常: {str(e)}",
            extra={"processId": getattr(callback_data, 'processId', 'unknown'), 
                  "algorithmTaskId": getattr(callback_data, 'algorithmTaskId', 'unknown')},
            exc_info=True
        )
        # 返回成功响应，避免算法服务反复重试
        return {"status": "success", "message": "回调已接收"}

@router.post("/progress", response_model=Dict[str, Any])
async def algorithm_progress(
    progress_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """算法处理进度回调接口
    
    接收算法服务处理过程中的进度更新
    """
    try:
        process_id = progress_data.get("processId")
        algorithm_task_id = progress_data.get("algorithmTaskId")
        progress = progress_data.get("progress", 0)
        current_stage = progress_data.get("stage", "")
        
        logger.info(
            f"收到算法进度更新: {progress}%",
            extra={
                "processId": process_id,
                "algorithmTaskId": algorithm_task_id,
                "progress": progress,
                "stage": current_stage
            }
        )
        
        algorithm_task = None
        if process_id:
            try:
                algorithm_task = get_algorithm_task_by_process_id(db, process_id)
            except Exception:
                algorithm_task = None

        model_id = (progress_data.get("modelId")
                    or (algorithm_task.model_id if algorithm_task and algorithm_task.model_id else None)
                    or "unknown")
        total_fields = (progress_data.get("totalFields")
                        or (len(algorithm_task.target_fields) if algorithm_task and algorithm_task.target_fields else None)
                        or 8)
        processed_fields = (progress_data.get("processedFields")
                            or (len(algorithm_task.extracted_fields) if algorithm_task and algorithm_task.extracted_fields else 0))

        progress_event = AGUIEvent(
            type="model.process.progress",
            data=ModelProcessProgressData(
                processId=process_id,
                modelId=model_id,
                progress=int(progress),
                processedFields=int(processed_fields),
                totalFields=int(total_fields),
                stage=str(current_stage)
            ),
            timestamp=int(datetime.now().timestamp() * 1000)
        )
        await sse_manager.send_event(
            process_id=process_id,
            event=progress_event
        )
        
        return {"status": "success", "message": "进度更新接收成功"}
    
    except Exception as e:
        logger.error(
            f"处理算法进度更新异常: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=get_error_info(ErrorCode.SYSTEM_ERROR)
        )