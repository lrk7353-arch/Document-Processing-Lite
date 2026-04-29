from sqlalchemy.orm import Session
from agent.models.db import Base
from agent.db.session import engine, get_db
from agent.config import settings
import logging

# 配置日志
logger = logging.getLogger(__name__)

def init_db(db: Session) -> None:
    """初始化数据库（创建所有表）"""
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        logger.info(f"数据库初始化完成，连接地址：{settings.database_url}")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        logger.warning("服务将继续运行，但数据库功能可能不可用")

if __name__ == "__main__":
    """独立执行数据库初始化"""
    try:
        db = next(get_db())
        init_db(db)
    except Exception as e:
        logger.error(f"独立执行数据库初始化失败: {str(e)}")
        logger.warning("程序将继续运行，但数据库功能可能不可用")