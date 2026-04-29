import sys
import asyncio
from pathlib import Path
from typing import Optional
# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent  # Backend目录
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# 导入所有依赖
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from agent.config import settings
from agent.utils.sse import sse_manager
from agent.utils.error import create_exception_handler, create_response_handler, AppException

# 全局存储健康监控任务
sse_health_task: Optional[asyncio.Task] = None
from agent.config import settings
from agent.db.init import init_db
from agent.db.session import get_db
from agent.api.file import router as file_router
from agent.api.sse import router as sse_router
from agent.api.algorithm_in import router as algorithm_router
from agent.api.compliance import router as compliance_router
from agent.api.action import router as action_router
from agent.api.auth import router as auth_router
from agent.api.task import router as task_router
from agent.api.chat import router as chat_router
from agent.api.smart_doc import router as smart_doc_router 
from agent.utils.logger import logger
from sqlalchemy.orm import Session

# 初始化FastAPI应用
app = FastAPI(
    title="基于AG-UI协议的智能体后端系统实现API",
    description="基于AG-UI协议的单证处理智能体后端服务",
    version="1.0.0",
    docs_url="/api/docs/swagger",  # Swagger UI地址
    redoc_url="/api/docs/redoc",  # ReDoc文档地址
    openapi_url="/api/openapi.json"  # OpenAPI Schema地址
)

# 配置CORS（支持前端跨域访问，《通信机制文档.pdf》2.2认证方式跨域说明）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加统一响应格式中间件
app.middleware("http")(create_response_handler())

# 注册全局异常处理器
app.add_exception_handler(Exception, create_exception_handler())

# 注册路由
app.include_router(file_router)
app.include_router(sse_router)
app.include_router(algorithm_router)
app.include_router(compliance_router)
app.include_router(action_router)
app.include_router(auth_router)
app.include_router(task_router)
app.include_router(chat_router)
app.include_router(smart_doc_router, tags=["智能单证引擎"])

# 自定义Swagger UI（添加AG-UI协议说明）
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui():
    # 移除description参数，因为当前FastAPI版本不支持
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API文档",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css"
    )

# 根路由
@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Document Processing Intelligent Agent Backend is Running",
        "docs_url": "/api/docs",
        "health_url": "/api/health"
    }

# 应用启动钩子（初始化数据库）
@app.on_event("startup")
async def startup_event():
    logger.info("智能体后端服务启动中...", extra={"processId": "system", "algorithmTaskId": "system"})
    # 初始化数据库（在DB不可用时不阻塞启动）
    try:
        init_db(None)  # 内部使用engine
    except Exception:
        logger.warning("数据库初始化跳过（不可用）", extra={"processId": "system", "algorithmTaskId": "system"})
    
    # 启动SSE队列健康监控任务
    global sse_health_task
    sse_health_task = asyncio.create_task(sse_manager.monitor_queue_health())
    logger.info("SSE队列健康监控已启动", extra={"processId": "system", "algorithmTaskId": "system"})
    
    logger.info(f"服务启动完成，监听地址：{settings.api_host}:{settings.api_port}",
                extra={"processId": "system", "algorithmTaskId": "system"})

# 应用关闭钩子
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("智能体后端服务关闭中...", extra={"processId": "system", "algorithmTaskId": "system"})
    
    # 取消SSE队列健康监控任务
    global sse_health_task
    if sse_health_task and not sse_health_task.done():
        sse_health_task.cancel()
        try:
            await sse_health_task
        except asyncio.CancelledError:
            logger.info("SSE队列健康监控已取消", extra={"processId": "system", "algorithmTaskId": "system"})

# 健康检查接口
@app.get("/api/health", summary="服务健康检查")
async def health_check(db: Session = Depends(get_db)):
    import time
    try:
        # 检查数据库连接，使用正确的SQLAlchemy语法
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        # 直接返回统一响应格式
        return {
            "success": True,
            "errorCode": "SUCCESS",
            "errorMsg": "",
            "code": 0,
            "timestamp": int(time.time() * 1000),
            "data": {
                "status": "healthy",
                "service": "document_agent",
                "database": "connected"
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}", extra={"processId": "system", "algorithmTaskId": "system"})
        # 直接返回统一错误格式
        return {
            "success": False,
            "errorCode": "SYSTEM_ERROR",
            "errorMsg": str(e),
            "code": 1000,
            "timestamp": int(time.time() * 1000),
            "data": None
        }

if __name__ == "__main__":
    import uvicorn
    # 强制绑定 127.0.0.1:8000 以避免 Windows 防火墙或 0.0.0.0 绑定失败的问题
    uvicorn.run(
        "agent.main:app",
        host="127.0.0.1", 
        port=8000,
        reload=False
    )