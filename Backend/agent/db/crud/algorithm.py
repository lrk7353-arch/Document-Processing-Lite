from sqlalchemy.orm import Session
from datetime import datetime
from agent.models.db import AlgorithmTask, ExtractedField, ValidationResult
from agent.models.algorithm_data import (
    ModelParams, AlgorithmCallbackSuccessData, ValidationResult as AlgorithmValidationResult
)


def create_algorithm_task(
        db: Session,
        process_id: str,
        model_params: ModelParams,
        start_time: datetime = None
) -> AlgorithmTask:
    """创建算法任务"""
    db_algorithm_task = AlgorithmTask(
        process_id=process_id,
        model_id=model_params.modelId,
        model_name=model_params.modelName,
        target_fields=model_params.targetFields,
        status="pending",
        start_time=start_time or datetime.utcnow()
    )
    db.add(db_algorithm_task)
    db.commit()
    db.refresh(db_algorithm_task)
    return db_algorithm_task


def get_algorithm_task_by_id(db: Session, algorithm_task_id: str) -> AlgorithmTask:
    """通过算法任务ID获取任务"""
    return db.query(AlgorithmTask).filter(AlgorithmTask.algorithm_task_id == algorithm_task_id).first()


def get_algorithm_task_by_process_id(db: Session, process_id: str) -> AlgorithmTask:
    """通过process_id获取算法任务"""
    return db.query(AlgorithmTask).filter(AlgorithmTask.process_id == process_id).first()


def update_algorithm_success(
        db: Session,
        callback_data: AlgorithmCallbackSuccessData
) -> AlgorithmTask:
    """更新算法任务成功结果"""
    # 先尝试通过algorithmTaskId查找
    db_algorithm_task = get_algorithm_task_by_id(db, callback_data.algorithmTaskId)
    
    # 如果找不到，尝试通过processId查找（可能是新创建的任务）
    if not db_algorithm_task:
        db_algorithm_task = get_algorithm_task_by_process_id(db, callback_data.processId)
        
    # 如果还是找不到，创建一个新的算法任务
    if not db_algorithm_task:
        from agent.models.db import AlgorithmTask
        from datetime import datetime
        db_algorithm_task = AlgorithmTask(
            algorithm_task_id=callback_data.algorithmTaskId,
            process_id=callback_data.processId,
            model_id=getattr(callback_data, 'modelId', 'unknown'),
            status='success'
        )
        db.add(db_algorithm_task)

    # 更新算法任务基本信息
    db_algorithm_task.status = "success"
    db_algorithm_task.end_time = datetime.fromtimestamp(callback_data.endTime / 1000)
    db_algorithm_task.updated_at = datetime.utcnow()

    # 保存提取字段
    for field in callback_data.extractedFields:
        db_field = ExtractedField(
            algorithm_task_id=db_algorithm_task.algorithm_task_id,
            field_name=field.fieldName,
            field_value=str(field.fieldValue),
            confidence=field.confidence,
            position=field.position
        )
        db.add(db_field)

    # 保存校验结果
    if callback_data.validationResult:
        validation_data = callback_data.validationResult
        db_validation = ValidationResult(
            algorithm_task_id=db_algorithm_task.algorithm_task_id,
            validation_status=validation_data.validationStatus,
            rule_version=validation_data.ruleVersion,
            validation_time=datetime.fromtimestamp(validation_data.validationTime / 1000),
            failed_rules=[rule.dict() for rule in validation_data.failedRules] if validation_data.failedRules else None
        )
        db.add(db_validation)

    db.commit()
    db.refresh(db_algorithm_task)
    return db_algorithm_task


def update_algorithm_failure(
        db: Session,
        algorithm_task_id: str,
        error_code: str,
        error_msg: str,
        fail_time: int
) -> AlgorithmTask:
    """更新算法任务失败结果"""
    db_algorithm_task = get_algorithm_task_by_id(db, algorithm_task_id)
    if not db_algorithm_task:
        return None

    db_algorithm_task.status = "fail"
    db_algorithm_task.error_code = error_code
    db_algorithm_task.error_msg = error_msg
    db_algorithm_task.end_time = datetime.fromtimestamp(fail_time / 1000)
    db_algorithm_task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_algorithm_task)
    return db_algorithm_task