from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

# 基础模型
Base = declarative_base()


def generate_uuid() -> str:
    """生成UUID字符串"""
    return str(uuid.uuid4())


class Task(Base):
    """任务主表（单证处理全流程）"""
    __tablename__ = "tasks"

    process_id = Column(String(64), primary_key=True, default=generate_uuid, comment="任务唯一标识")
    file_id = Column(String(64), comment="文件ID")
    file_name = Column(String(255), comment="文件名")
    file_path = Column(Text, comment="文件存储路径")
    file_size = Column(Integer, comment="文件大小（字节）")
    file_type = Column(String(64), comment="文件类型")
    agent_state = Column(String(32), default="idle", comment="智能体状态：idle/processing/awaiting_input/completed/failed/canceled/paused/draft")
    total_progress = Column(Integer, default=0, comment="总进度（0-100）")
    total_duration = Column(Integer, comment="总耗时（毫秒）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联关系
    algorithm_task = relationship("AlgorithmTask", back_populates="task", uselist=False, cascade="all, delete-orphan")
    compliance_task = relationship("ComplianceTask", back_populates="task", uselist=False, cascade="all, delete-orphan")
    user_actions = relationship("UserAction", back_populates="task", cascade="all, delete-orphan")


class AlgorithmTask(Base):
    """算法调用任务表"""
    __tablename__ = "algorithm_tasks"

    algorithm_task_id = Column(String(64), primary_key=True, default=generate_uuid, comment="算法任务ID")
    process_id = Column(String(64), ForeignKey("tasks.process_id", ondelete="CASCADE"), comment="关联任务ID")
    model_id = Column(String(64), comment="模型ID")
    model_name = Column(String(128), comment="模型名称")
    target_fields = Column(JSON, comment="目标字段列表")
    status = Column(String(32), default="pending", comment="算法任务状态：pending/running/success/fail")
    error_code = Column(String(64), nullable=True, comment="错误码")
    error_msg = Column(Text, nullable=True, comment="错误描述")
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联关系
    task = relationship("Task", back_populates="algorithm_task")
    extracted_fields = relationship("ExtractedField", back_populates="algorithm_task", cascade="all, delete-orphan")
    validation_result = relationship("ValidationResult", back_populates="algorithm_task", uselist=False,
                                     cascade="all, delete-orphan")


class ExtractedField(Base):
    """字段提取结果表"""
    __tablename__ = "extracted_fields"

    field_id = Column(String(64), primary_key=True, default=generate_uuid, comment="字段ID")
    algorithm_task_id = Column(String(64), ForeignKey("algorithm_tasks.algorithm_task_id", ondelete="CASCADE"),
                               comment="关联算法任务ID")
    field_name = Column(String(64), comment="字段名")
    field_value = Column(Text, comment="字段值")
    confidence = Column(Float, comment="提取置信度")
    position = Column(JSON, nullable=True, comment="字段位置")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关联关系
    algorithm_task = relationship("AlgorithmTask", back_populates="extracted_fields")


class ValidationResult(Base):
    """校验结果表"""
    __tablename__ = "validation_results"

    validation_id = Column(String(64), primary_key=True, default=generate_uuid, comment="校验结果ID")
    algorithm_task_id = Column(String(64), ForeignKey("algorithm_tasks.algorithm_task_id", ondelete="CASCADE"),
                               comment="关联算法任务ID")
    validation_status = Column(String(32), comment="校验状态：passed/failed/skipped")
    rule_version = Column(String(32), comment="规则版本")
    validation_time = Column(DateTime, comment="校验时间")
    failed_rules = Column(JSON, nullable=True, comment="失败规则列表")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关联关系
    algorithm_task = relationship("AlgorithmTask", back_populates="validation_result")


class ComplianceTask(Base):
    """合规检查任务表"""
    __tablename__ = "compliance_tasks"

    compliance_task_id = Column(String(64), primary_key=True, default=generate_uuid, comment="合规任务ID")
    process_id = Column(String(64), ForeignKey("tasks.process_id", ondelete="CASCADE"), comment="关联任务ID")
    check_rules = Column(JSON, comment="检查规则列表")
    overall_result = Column(String(16), comment="总体结果：pass/fail")
    status = Column(String(32), default="pending", comment="合规任务状态：pending/running/success/fail")
    error_code = Column(String(64), nullable=True, comment="错误码")
    error_msg = Column(Text, nullable=True, comment="错误描述")
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关联关系
    task = relationship("Task", back_populates="compliance_task")
    compliance_rules = relationship("ComplianceRuleResult", back_populates="compliance_task",
                                    cascade="all, delete-orphan")


class ComplianceRuleResult(Base):
    """合规规则检查结果表"""
    __tablename__ = "compliance_rule_results"

    rule_result_id = Column(String(64), primary_key=True, default=generate_uuid, comment="规则结果ID")
    compliance_task_id = Column(String(64), ForeignKey("compliance_tasks.compliance_task_id", ondelete="CASCADE"),
                                comment="关联合规任务ID")
    rule_id = Column(String(64), comment="规则ID")
    rule_name = Column(String(128), comment="规则名称")
    result = Column(String(16), comment="结果：pass/fail")
    reason = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关联关系
    compliance_task = relationship("ComplianceTask", back_populates="compliance_rules")


class UserAction(Base):
    """用户操作表"""
    __tablename__ = "user_actions"

    action_id = Column(String(64), primary_key=True, default=generate_uuid, comment="操作ID")
    process_id = Column(String(64), ForeignKey("tasks.process_id", ondelete="CASCADE"), comment="关联任务ID")
    action_type = Column(String(64), comment="操作类型：confirm_result/retry_process/modify_field")
    action_data = Column(JSON, comment="操作数据")
    user_id = Column(String(64), nullable=True, comment="用户ID")
    action_time = Column(DateTime, default=datetime.utcnow, comment="操作时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关联关系
    task = relationship("Task", back_populates="user_actions")


class SSESession(Base):
    """SSE会话表"""
    __tablename__ = "sse_sessions"

    session_id = Column(String(64), primary_key=True, default=generate_uuid, comment="会话ID")
    process_id = Column(String(64), ForeignKey("tasks.process_id", ondelete="CASCADE"), comment="关联任务ID")
    user_id = Column(String(64), nullable=True, comment="用户ID")
    last_event_id = Column(String(64), nullable=True, comment="最后事件ID")
    connected_at = Column(DateTime, default=datetime.utcnow, comment="连接时间")
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后活跃时间")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    session_id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    message_id = Column(String(64), primary_key=True, default=generate_uuid)
    session_id = Column(String(64), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"))
    role = Column(String(16))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)