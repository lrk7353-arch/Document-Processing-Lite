from enum import Enum
from typing import Dict, Tuple, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response


class ErrorCode(Enum):
    """系统统一错误码"""
    # 基础错误（1000-1999）
    SUCCESS = (0, "成功")
    SYSTEM_ERROR = (1000, "系统内部错误")
    PARAM_ERROR = (1001, "参数错误")
    AUTH_ERROR = (1002, "认证失败")
    PERMISSION_DENIED = (1003, "权限不足")
    RESOURCE_NOT_FOUND = (1004, "资源不存在")

    # 文件相关错误（2000-2999）
    FILE_UPLOAD_ERROR = (2000, "文件上传失败")
    FILE_TYPE_INVALID = (2001, "不支持的文件类型")
    FILE_SIZE_EXCEED = (2002, "文件大小超过限制")
    FILE_NOT_FOUND = (2003, "文件不存在")
    FILE_READ_ERROR = (2004, "文件读取失败")

    # 算法相关错误（3000-3999）
    ALGORITHM_SERVICE_UNAVAILABLE = (3000, "算法服务暂不可用")
    ALGORITHM_AUTH_FAILED = (3001, "算法服务认证失败")
    ALGORITHM_TIMEOUT = (3002, "算法服务响应超时")
    ALGORITHM_MODEL_NOT_FOUND = (3003, "未找到指定模型")
    ALGORITHM_VALIDATION_FAILED = (3004, "逻辑校验失败")
    ALGORITHM_VALIDATION_SERVICE_ERROR = (3005, "校验服务暂不可用")
    ALGORITHM_RESULT_MISSING = (3006, "算法结果缺失")
    ALGORITHM_RESULT_PROCESS_ERROR = (3007, "算法结果处理错误")

    # 合规相关错误（4000-4999）
    COMPLIANCE_SERVICE_ERROR = (4000, "合规检查服务异常")
    COMPLIANCE_RULE_NOT_FOUND = (4001, "合规规则不存在")
    COMPLIANCE_CHECK_FAILED = (4002, "合规检查未通过")

    # 智能体相关错误（5000-5999）
    AGENT_STATE_ERROR = (5000, "智能体状态异常")
    AGENT_TASK_RUNNING = (5001, "智能体正在执行其他任务")
    AGENT_TASK_TIMEOUT = (5002, "智能体任务超时")
    AGENT_ACTION_NOT_SUPPORTED = (5003, "不支持的用户操作")
    
    # 处理相关错误（6000-6999）
    ERROR_HANDLER_ERROR = (6000, "错误处理器异常")

    @property
    def code(self) -> int:
        """获取错误码"""
        return self.value[0]

    @property
    def message(self) -> str:
        """获取错误描述"""
        return self.value[1]


class AppException(HTTPException):
    """应用自定义异常基类"""
    def __init__(self, 
                 error_code: ErrorCode, 
                 detail: Optional[str] = None,
                 headers: Optional[Dict[str, str]] = None):
        self.error_code = error_code
        # 如果提供了详细信息，则使用详细信息，否则使用错误码的默认消息
        self.detail = detail or error_code.message
        # 根据错误类型设置适当的HTTP状态码
        status_code = self._get_http_status_code(error_code)
        super().__init__(status_code=status_code, detail=self.detail, headers=headers)
    
    def _get_http_status_code(self, error_code: ErrorCode) -> int:
        """根据错误码获取对应的HTTP状态码"""
        if error_code.code == 0:
            return 200
        elif 1000 <= error_code.code < 2000:
            # 基础错误
            if error_code == ErrorCode.PARAM_ERROR:
                return 400
            elif error_code == ErrorCode.AUTH_ERROR:
                return 401
            elif error_code == ErrorCode.PERMISSION_DENIED:
                return 403
            elif error_code == ErrorCode.RESOURCE_NOT_FOUND:
                return 404
            else:
                return 500
        elif 2000 <= error_code.code < 3000:
            # 文件相关错误
            return 400
        elif 3000 <= error_code.code < 5000:
            # 算法和合规相关错误
            return 503
        else:
            # 其他错误
            return 500


class FileException(AppException):
    """文件相关异常"""
    pass


class AlgorithmException(AppException):
    """算法相关异常"""
    pass


class AuthException(AppException):
    """认证相关异常"""
    pass


def get_error_info(error_code: ErrorCode, detail: Optional[str] = None) -> Dict[str, Any]:
    """获取错误信息字典，统一错误响应格式"""
    return {
        "success": False,
        "errorCode": error_code.name,
        "errorMsg": detail or error_code.message,
        "code": error_code.code,
        "timestamp": None,  # 将在异常处理器中设置
        "data": None
    }


def get_success_info(data: Optional[Any] = None) -> Dict[str, Any]:
    """获取成功响应信息字典"""
    return {
        "success": True,
        "errorCode": "SUCCESS",
        "errorMsg": "",
        "code": 0,
        "timestamp": None,  # 将在响应处理器中设置
        "data": data
    }


def get_error_by_code(code: int) -> Tuple[ErrorCode, str]:
    """通过错误码获取错误枚举"""
    for error in ErrorCode:
        if error.code == code:
            return error, error.message
    return ErrorCode.SYSTEM_ERROR, "未知错误"


# 全局异常处理器
def create_exception_handler():
    """创建全局异常处理器"""
    async def exception_handler(request: Request, exc: Exception):
        import time
        
        if isinstance(exc, AppException):
            # 处理自定义异常
            error_info = get_error_info(exc.error_code, exc.detail)
            error_info["timestamp"] = int(time.time() * 1000)
            return JSONResponse(
                status_code=exc.status_code,
                content=error_info
            )
        elif isinstance(exc, HTTPException):
            # 处理FastAPI内置的HTTPException
            # 将其转换为我们的统一格式
            error_code = ErrorCode.SYSTEM_ERROR
            if exc.status_code == 400:
                error_code = ErrorCode.PARAM_ERROR
            elif exc.status_code == 401:
                error_code = ErrorCode.AUTH_ERROR
            elif exc.status_code == 403:
                error_code = ErrorCode.PERMISSION_DENIED
            elif exc.status_code == 404:
                error_code = ErrorCode.RESOURCE_NOT_FOUND
                
            error_info = get_error_info(error_code, str(exc.detail))
            error_info["timestamp"] = int(time.time() * 1000)
            return JSONResponse(
                status_code=exc.status_code,
                content=error_info
            )
        else:
            # 处理其他所有未捕获的异常
            error_info = get_error_info(ErrorCode.SYSTEM_ERROR, str(exc))
            error_info["timestamp"] = int(time.time() * 1000)
            return JSONResponse(
                status_code=500,
                content=error_info
            )
    
    return exception_handler


# 统一响应格式中间件
def create_response_handler():
    """创建统一响应格式中间件"""
    async def response_handler(request: Request, call_next):
        import time
        
        # 直接使用原始响应，但拦截后统一格式化
        response = await call_next(request)
        
        # 只处理JSON响应
        if response.media_type == "application/json":
            # 读取原始响应内容
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # 转换为Python对象
            import json
            try:
                data = json.loads(body.decode('utf-8'))
                
                # 检查是否已经是统一格式
                if isinstance(data, dict) and "success" in data and "errorCode" in data:
                    # 已经是统一格式，只添加时间戳
                    data["timestamp"] = int(time.time() * 1000)
                else:
                    # 不是统一格式，转换为成功响应格式
                    formatted_data = get_success_info(data)
                    formatted_data["timestamp"] = int(time.time() * 1000)
                    data = formatted_data
                
                # 创建新的响应
                new_response = JSONResponse(
                    status_code=response.status_code,
                    content=data,
                    headers=dict(response.headers)
                )
                # 移除可能导致问题的headers
                new_response.headers.pop('content-length', None)
                return new_response
            except Exception as e:
                # 如果解析失败，记录错误并返回原始响应
                print(f"Response formatting error: {e}")
                # 重新构造原始响应
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
        
        return response
    
    return response_handler