from sqlalchemy.orm import Session
from datetime import datetime
from agent.models.db import Task
from agent.models.agui import FileUploadCompleteData


def create_task(db: Session, file_data: FileUploadCompleteData) -> Task:
    """创建任务"""
    db_task = Task(
        file_id=file_data.fileId,
        file_name=file_data.fileName,
        file_path=file_data.storagePath,
        file_size=file_data.fileSize,
        agent_state="idle"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_task_by_process_id(db: Session, process_id: str) -> Task:
    """通过process_id获取任务"""
    return db.query(Task).filter(Task.process_id == process_id).first()


def update_task_state(db: Session, process_id: str, state: str, total_progress: int = None) -> Task:
    """更新任务状态"""
    db_task = get_task_by_process_id(db, process_id)
    if not db_task:
        return None

    db_task.agent_state = state
    if total_progress is not None:
        db_task.total_progress = total_progress
    db_task.updated_at = datetime.utcnow()

    # 如果任务完成，计算总耗时
    if state == "completed" and db_task.start_time:
        db_task.total_duration = int((datetime.utcnow() - db_task.start_time).total_seconds() * 1000)

    db.commit()
    db.refresh(db_task)
    return db_task


def update_task_progress(db: Session, process_id: str, total_progress: int) -> Task:
    """更新任务进度"""
    return update_task_state(db, process_id, state=None, total_progress=total_progress)


def delete_task(db: Session, process_id: str) -> bool:
    """删除任务"""
    db_task = get_task_by_process_id(db, process_id)
    if not db_task:
        return False

    db.delete(db_task)
    db.commit()
    return True