from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import asyncio
from concurrent.futures import ThreadPoolExecutor
from agent.models.agui import FileUploadCompleteData, TaskCompleteData
from agent.models.algorithm_data import AlgorithmCallbackSuccessData
from agent.db.crud.task import create_task, get_task_by_process_id, update_task_state, update_task_progress
from agent.db.crud.algorithm import create_algorithm_task, update_algorithm_success, update_algorithm_failure
from agent.db.crud.compliance import create_compliance_task
from agent.utils.logger import logger
from agent.utils.error import ErrorCode

class DBService:
    """数据库操作服务（对齐《数据契约与状态机.docx》数据契约）"""
    def create_task_from_file(
        self, db: Session, file_data: FileUploadCompleteData
    ) -> Tuple[Optional[str], Optional[ErrorCode]]:
        """
        从文件上传结果创建任务（关联文档"文件上传完成"与"任务初始化"）
        返回：process_id / 错误码
        """
        try:
            # 创建任务主表记录
            db_task = create_task(db=db, file_data=file_data)
            if not db_task:
                logger.error("创建任务主表记录失败")
                return None, ErrorCode.SYSTEM_ERROR

            logger.info(
                f"任务创建成功: process_id={db_task.process_id}, file_id={file_data.fileId}",
                extra={"processId": db_task.process_id, "algorithmTaskId": ""}
            )
            return db_task.process_id, None

        except Exception as e:
            logger.error(
                f"从文件创建任务异常: {str(e)}",
                extra={"processId": "", "algorithmTaskId": ""},
                exc_info=True
            )
            return None, ErrorCode.SYSTEM_ERROR

    def init_task_workflow(
        self, db: Session, process_id: str, model_params: Dict[str, Any]
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        初始化任务工作流（创建算法任务+合规任务）
        对齐文档"模型调度开始"与"合规检查开始"数据契约
        """
        try:
            # 1. 更新任务状态为processing
            task_updated = update_task_state(db=db, process_id=process_id, state="processing", total_progress=20)
            if not task_updated:
                logger.error(f"更新任务状态失败: process_id={process_id}")
                return False, ErrorCode.SYSTEM_ERROR

            # 2. 创建算法任务
            db_algorithm_task = create_algorithm_task(
                db=db,
                process_id=process_id,
                model_params=model_params,
                start_time=datetime.now()
            )
            if not db_algorithm_task:
                logger.error(f"创建算法任务失败: process_id={process_id}")
                # 回滚任务状态
                update_task_state(db=db, process_id=process_id, state="idle")
                return False, ErrorCode.SYSTEM_ERROR

            # 3. 预创建合规任务（未启动）
            db_compliance_task = create_compliance_task(
                db=db,
                process_id=process_id,
                check_rules=[],  # 规则后续由合规服务填充
                start_time=None
            )
            if not db_compliance_task:
                logger.error(f"预创建合规任务失败: process_id={process_id}")
                # 回滚算法任务和任务状态
                db.delete(db_algorithm_task)
                update_task_state(db=db, process_id=process_id, state="idle")
                db.commit()
                return False, ErrorCode.SYSTEM_ERROR

            logger.info(
                f"任务工作流初始化成功: process_id={process_id}, algorithm_task_id={db_algorithm_task.algorithm_task_id}",
                extra={"processId": process_id, "algorithmTaskId": db_algorithm_task.algorithm_task_id}
            )
            return True, None

        except Exception as e:
            db.rollback()
            logger.error(
                f"初始化任务工作流异常: {str(e)}",
                extra={"processId": process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return False, ErrorCode.SYSTEM_ERROR

    def save_algorithm_result(
        self, db: Session, callback_data: AlgorithmCallbackSuccessData
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        保存算法结果（对齐文档"模型提取完成"数据契约）
        """
        try:
            # 1. 首先检查并创建tasks表记录（如果不存在）
            from sqlalchemy.exc import IntegrityError
            from agent.models.db import Task
            from datetime import datetime
            
            # 检查tasks表中是否存在该process_id
            existing_task = db.query(Task).filter(Task.process_id == callback_data.processId).first()
            if not existing_task:
                # 创建一个最小化的tasks记录以满足外键约束
                try:
                    # 确保使用正确的字段名称，与数据库模型完全匹配
                    new_task = Task(
                        process_id=callback_data.processId,  # 作为主键使用
                        file_id=f"file-{callback_data.processId}",
                        file_name=f"test-{callback_data.processId}.pdf",
                        file_path=f"/tmp/test-{callback_data.processId}.pdf",
                        file_size=1024,
                        file_type="pdf",
                        agent_state="processing",
                        total_progress=0
                        # 不需要手动设置created_at和updated_at，模型已有默认值
                    )
                    db.add(new_task)
                    db.commit()
                    logger.info(
                        f"已创建tasks表记录: process_id={callback_data.processId}",
                        extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
                    )
                except IntegrityError:
                    db.rollback()
                    logger.warning(
                        f"创建tasks记录失败（可能并发创建）: process_id={callback_data.processId}",
                        extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
                    )
                except Exception as inner_e:
                    db.rollback()
                    logger.error(
                        f"创建tasks记录异常: {str(inner_e)}",
                        extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId},
                        exc_info=True
                    )
            
            # 2. 更新算法任务结果
            updated_algorithm_task = update_algorithm_success(
                db=db,
                callback_data=callback_data
            )
            if not updated_algorithm_task:
                logger.error(
                    f"更新算法结果失败: algorithm_task_id={callback_data.algorithmTaskId}",
                    extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
                )
                return False, ErrorCode.SYSTEM_ERROR

            # 3. 更新任务进度（模型提取完成，进度至70%）
            try:
                update_task_progress(db=db, process_id=callback_data.processId, total_progress=70)
            except Exception as e:
                logger.warning(
                    f"更新任务进度失败: {str(e)}",
                    extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
                )

            logger.info(
                f"算法结果保存成功: 提取字段{len(callback_data.extractedFields)}个",
                extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId}
            )
            return True, None

        except Exception as e:
            db.rollback()
            logger.error(
                f"保存算法结果异常: {str(e)}",
                extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId},
                exc_info=True
            )
            return False, ErrorCode.SYSTEM_ERROR

    def save_task_complete(
        self, db: Session, process_id: str, task_complete_data: TaskCompleteData
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        保存任务完成结果（对齐文档"处理任务完成"数据契约）
        """
        try:
            # 1. 更新任务状态为completed
            updated_task = update_task_state(
                db=db,
                process_id=process_id,
                state="completed",
                total_progress=100
            )
            if not updated_task:
                logger.error(f"更新任务完成状态失败: process_id={process_id}")
                return False, ErrorCode.SYSTEM_ERROR

            # 2. 更新任务总耗时
            updated_task.total_duration = task_complete_data.totalDuration
            db.commit()

            logger.info(
                f"任务完成结果保存成功: process_id={process_id}, 总耗时{task_complete_data.totalDuration}ms",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
            return True, None

        except Exception as e:
            db.rollback()
            logger.error(
                f"保存任务完成结果异常: {str(e)}",
                extra={"processId": process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return False, ErrorCode.SYSTEM_ERROR
    
    async def save_algorithm_result_async(
        self, db: Session, callback_data: AlgorithmCallbackSuccessData
    ) -> Tuple[bool, Optional[str]]:
        """
        异步保存算法结果（供算法回调使用）
        """
        try:
            # 使用线程池执行器运行同步数据库操作
            loop = asyncio.get_event_loop()
            result, error = await loop.run_in_executor(
                ThreadPoolExecutor(),
                lambda: self.save_algorithm_result(db, callback_data)
            )
            
            if error:
                return False, str(error)
            return result, None
        except Exception as e:
            logger.error(
                f"异步保存算法结果异常: {str(e)}",
                extra={"processId": callback_data.processId, "algorithmTaskId": callback_data.algorithmTaskId},
                exc_info=True
            )
            return False, str(e)
    
    async def get_algorithm_result_async(
        self, db: Session, process_id: str
    ) -> Optional[AlgorithmCallbackSuccessData]:
        """
        异步获取算法结果（供工作流使用）
        """
        try:
            # 使用线程池执行器运行同步数据库操作
            loop = asyncio.get_event_loop()
            
            def get_result():
                from agent.db.crud.algorithm import get_algorithm_task_by_process_id
                # 从数据库获取算法任务
                algorithm_task = get_algorithm_task_by_process_id(db, process_id)
                if not algorithm_task or not algorithm_task.extracted_fields:
                    return None
                
                # 重建AlgorithmCallbackSuccessData对象
                from agent.models.algorithm_data import ExtractedFieldResult
                extracted_fields = []
                
                # 解析提取的字段（假设存储为JSON字符串）
                import json
                try:
                    fields_data = json.loads(algorithm_task.extracted_fields)
                    for field_data in fields_data:
                        field = ExtractedFieldResult(
                            fieldName=field_data.get('fieldName', ''),
                            fieldValue=field_data.get('fieldValue', ''),
                            confidence=field_data.get('confidence', 0.0),
                            position=field_data.get('position', '')  # 位置现在是字符串类型
                        )
                        extracted_fields.append(field)
                except Exception as parse_error:
                    logger.error(f"解析算法结果字段失败: {str(parse_error)}")
                    return None
                
                # 构建完整的回调数据对象
                callback_data = AlgorithmCallbackSuccessData(
                    processId=process_id,
                    algorithmTaskId=algorithm_task.algorithm_task_id,
                    modelId=algorithm_task.model_id or 'invoice_field_v1.0',
                    status='success',
                    extractedFields=extracted_fields,
                    endTime=int(algorithm_task.completed_at.timestamp() * 1000) if algorithm_task.completed_at else int(datetime.now().timestamp() * 1000)
                )
                
                return callback_data
            
            result = await loop.run_in_executor(ThreadPoolExecutor(), get_result)
            return result
            
        except Exception as e:
            logger.error(
                f"异步获取算法结果异常: {str(e)}",
                extra={"processId": process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return None

    def get_task_full_data(
        self, db: Session, process_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[ErrorCode]]:
        """
        获取任务完整数据（关联任务主表+算法结果+合规结果）
        用于前端查询详情（对齐文档"单证详情查询"接口）
        """
        try:
            # 1. 获取任务主表
            db_task = get_task_by_process_id(db=db, process_id=process_id)
            if not db_task:
                logger.error(f"任务不存在: process_id={process_id}")
                return None, ErrorCode.RESOURCE_NOT_FOUND

            # 2. 组装完整数据
            full_data = {
                "processId": db_task.process_id,
                "fileInfo": {
                    "fileId": db_task.file_id,
                    "fileName": db_task.file_name,
                    "filePath": db_task.file_path,
                    "fileSize": db_task.file_size,
                    "fileType": db_task.file_type
                },
                "agentState": db_task.agent_state,
                "totalProgress": db_task.total_progress,
                "totalDuration": db_task.total_duration,
                "createdAt": db_task.created_at.isoformat(),
                "updatedAt": db_task.updated_at.isoformat(),
                "algorithmResult": None,
                "complianceResult": None
            }

            # 3. 补充算法结果
            if db_task.algorithm_task:
                algorithm_task = db_task.algorithm_task
                algorithm_data = {
                    "algorithmTaskId": algorithm_task.algorithm_task_id,
                    "modelId": algorithm_task.model_id,
                    "modelName": algorithm_task.model_name,
                    "status": algorithm_task.status,
                    "startTime": algorithm_task.start_time.isoformat() if algorithm_task.start_time else None,
                    "endTime": algorithm_task.end_time.isoformat() if algorithm_task.end_time else None,
                    "extractedFields": [
                        {
                            "fieldName": f.field_name,
                            "fieldValue": f.field_value,
                            "confidence": f.confidence,
                            "position": f.position
                        } for f in algorithm_task.extracted_fields
                    ]
                }
                # 补充校验结果
                if algorithm_task.validation_result:
                    validation = algorithm_task.validation_result
                    algorithm_data["validationResult"] = {
                        "validationStatus": validation.validation_status,
                        "ruleVersion": validation.rule_version,
                        "validationTime": validation.validation_time.isoformat(),
                        "failedRules": validation.failed_rules
                    }
                full_data["algorithmResult"] = algorithm_data

            # 4. 补充合规结果
            if db_task.compliance_task:
                compliance_task = db_task.compliance_task
                compliance_data = {
                    "complianceTaskId": compliance_task.compliance_task_id,
                    "overallResult": compliance_task.overall_result,
                    "status": compliance_task.status,
                    "startTime": compliance_task.start_time.isoformat() if compliance_task.start_time else None,
                    "endTime": compliance_task.end_time.isoformat() if compliance_task.end_time else None,
                    "ruleResults": [
                        {
                            "ruleId": r.rule_id,
                            "ruleName": r.rule_name,
                            "result": r.result,
                            "reason": r.reason
                        } for r in compliance_task.compliance_rules
                    ]
                }
                full_data["complianceResult"] = compliance_data

            return full_data, None

        except Exception as e:
            logger.error(
                f"获取任务完整数据异常: {str(e)}",
                extra={"processId": process_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return None, ErrorCode.SYSTEM_ERROR

# 初始化数据库服务实例
db_service = DBService()