from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from agent.config import settings

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    echo=False,  # 生产环境关闭SQL日志
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Session:
    """获取数据库会话（依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()