from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
import os


class Settings(BaseSettings):
    """系统配置中心"""
    # 数据库配置
    postgres_user: str = Field(..., env="POSTGRES_USER")
    postgres_password: str = Field(..., env="POSTGRES_PASSWORD")
    postgres_db: str = Field(..., env="POSTGRES_DB")
    postgres_host: str = Field("localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(..., env="POSTGRES_PORT")

    # API配置
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")

    # 算法组接口配置
    algorithm_api_url: str = Field(..., env="ALGORITHM_API_URL")
    algorithm_service_token: str = Field(..., env="ALGORITHM_SERVICE_TOKEN")
    algorithm_timeout: int = Field(30, env="ALGORITHM_TIMEOUT")

    # SSE配置
    sse_max_retry_delay: int = Field(30000, env="SSE_MAX_RETRY_DELAY")
    sse_heartbeat_interval: int = Field(30, env="SSE_HEARTBEAT_INTERVAL")

    # 重试配置
    retry_max_count: int = Field(3, env="RETRY_MAX_COUNT")
    retry_initial_delay: int = Field(1, env="RETRY_INITIAL_DELAY")

    # 日志配置
    log_retention_days: int = Field(7, env="LOG_RETENTION_DAYS")
    log_dir: Path = Field(Path("./logs"), env="LOG_DIR")

    # 文件配置
    upload_dir: Path = Field(Path("./uploads"), env="UPLOAD_DIR")

    # 外部LLM配置
    deepseek_api_key: str | None = Field(None, env="DEEPSEEK_API_KEY")

    # PGVector配置
    pgvector_url: str | None = Field(None, env="PGVECTOR_URL")

    # AG-UI协议配置
    sse_endpoint: str = Field("/api/agent/stream", env="SSE_ENDPOINT")
    action_endpoint: str = Field("/api/agent/action", env="ACTION_ENDPOINT")
    
    # JWT配置
    secret_key: str = Field("your-secret-key-here-change-in-production", env="SECRET_KEY")
    algorithm: str = Field("HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    @property
    def current_timestamp(self) -> float:
        """获取当前时间戳"""
        import time
        return time.time()

    @property
    def database_url(self) -> str:
        """生成数据库连接URL"""
        return (f"postgresql+psycopg2://{self.postgres_user}:"
                f"{self.postgres_password}@{self.postgres_host}:"
                f"{self.postgres_port}/{self.postgres_db}")

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "case_sensitive": False
    }

    # 回调基础地址（供算法服务回调使用）
    callback_base: str = Field("http://localhost:8000", env="BACKEND_CALLBACK_BASE")


# 初始化配置实例
settings = Settings()

# 创建必要目录
settings.log_dir.mkdir(exist_ok=True, parents=True)
settings.upload_dir.mkdir(exist_ok=True, parents=True)