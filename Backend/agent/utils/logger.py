import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
from agent.config import settings


class AgentLogger:
    """智能体日志工具"""

    def __init__(self, name: str = "document_agent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False  # 避免重复日志

        # 日志格式（包含processId和algorithmTaskId）
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "processId:%(processId)s - algorithmTaskId:%(algorithmTaskId)s - "
            "%(message)s"
        )
        formatter = logging.Formatter(log_format)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 文件处理器（按日期分割，保留7天）
        log_file = settings.log_dir / f"agent_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024 * 1024 * 100,  # 100MB
            backupCount=settings.log_retention_days,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 清理过期日志
        self._clean_expired_logs()

    def _clean_expired_logs(self) -> None:
        """清理过期日志（保留指定天数）"""
        expire_date = datetime.now() - timedelta(days=settings.log_retention_days)
        for log_file in settings.log_dir.glob("agent_*.log"):
            try:
                # 从文件名提取日期
                file_date_str = log_file.name.split("_")[1].split(".")[0]
                file_date = datetime.strptime(file_date_str, "%Y%m%d")
                if file_date < expire_date:
                    log_file.unlink()
                    self.info(f"清理过期日志文件: {log_file.name}")
            except Exception as e:
                self.error(f"清理日志文件失败: {str(e)}", extra={"processId": "system", "algorithmTaskId": "system"})

    def _get_extra(self, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取额外日志字段（默认空字符串避免KeyError）"""
        default_extra = {"processId": "", "algorithmTaskId": ""}
        if extra:
            default_extra.update(extra)
        return default_extra

    def info(self, msg: str, extra: Dict[str, Any] = None) -> None:
        """信息日志"""
        self.logger.info(msg, extra=self._get_extra(extra))

    def warning(self, msg: str, extra: Dict[str, Any] = None) -> None:
        """警告日志"""
        self.logger.warning(msg, extra=self._get_extra(extra))

    def error(self, msg: str, extra: Dict[str, Any] = None, exc_info: bool = False) -> None:
        """错误日志"""
        self.logger.error(msg, extra=self._get_extra(extra), exc_info=exc_info)

    def critical(self, msg: str, extra: Dict[str, Any] = None, exc_info: bool = False) -> None:
        """严重错误日志"""
        self.logger.critical(msg, extra=self._get_extra(extra), exc_info=exc_info)
    
    def debug(self, msg: str, extra: Dict[str, Any] = None) -> None:
        """调试日志"""
        self.logger.debug(msg, extra=self._get_extra(extra))


# 初始化全局日志实例
logger = AgentLogger()