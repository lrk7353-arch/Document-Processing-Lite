from sqlalchemy.orm import Session
from datetime import datetime
from agent.models.db import ComplianceTask, ComplianceRuleResult
from agent.models.agui import ComplianceCheckCompleteData, RuleResult


def create_compliance_task(
        db: Session,
        process_id: str,
        check_rules: list,
        start_time: datetime = None
) -> ComplianceTask:
    """创建合规任务"""
    db_compliance_task = ComplianceTask(
        process_id=process_id,
        check_rules=check_rules,
        status="pending",
        start_time=start_time or datetime.utcnow()
    )
    db.add(db_compliance_task)
    db.commit()
    db.refresh(db_compliance_task)
    return db_compliance_task


def get_compliance_task_by_process_id(db: Session, process_id: str) -> ComplianceTask:
    """通过process_id获取合规任务"""
    return db.query(ComplianceTask).filter(ComplianceTask.process_id == process_id).first()


def update_compliance_success(
        db: Session,
        process_id: str,
        compliance_result: ComplianceCheckCompleteData
) -> ComplianceTask:
    """更新合规任务成功结果"""
    db_compliance_task = get_compliance_task_by_process_id(db, process_id)
    if not db_compliance_task:
        return None

    # 更新合规任务基本信息
    db_compliance_task.status = "success"
    db_compliance_task.overall_result = compliance_result.overallResult
    db_compliance_task.end_time = datetime.fromtimestamp(compliance_result.endTime / 1000)
    db_compliance_task.updated_at = datetime.utcnow()

    # 保存规则结果
    for rule in compliance_result.ruleResults:
        db_rule_result = ComplianceRuleResult(
            compliance_task_id=db_compliance_task.compliance_task_id,
            rule_id=rule.ruleId,
            rule_name=rule.ruleName,
            result=rule.result,
            reason=rule.reason
        )
        db.add(db_rule_result)

    db.commit()
    db.refresh(db_compliance_task)
    return db_compliance_task


def update_compliance_failure(
        db: Session,
        process_id: str,
        error_code: str,
        error_msg: str,
        fail_time: int
) -> ComplianceTask:
    """更新合规任务失败结果"""
    db_compliance_task = get_compliance_task_by_process_id(db, process_id)
    if not db_compliance_task:
        return None

    db_compliance_task.status = "fail"
    db_compliance_task.error_code = error_code
    db_compliance_task.error_msg = error_msg
    db_compliance_task.end_time = datetime.fromtimestamp(fail_time / 1000)
    db_compliance_task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_compliance_task)
    return db_compliance_task