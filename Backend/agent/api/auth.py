from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import timedelta, datetime
from typing import Optional, Dict
from agent.utils.auth import (
    create_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, 
    get_current_user,
    verify_password,
    Role, 
    check_permissions
)
from agent.config import settings
from agent.utils.logger import logger
import time

# 初始化路由
router = APIRouter(prefix="/api/auth", tags=["认证"])

# 在实际项目中，应该从数据库中获取用户
# 这里使用内存存储作为简化实现
class UserStore:
    def __init__(self):
        # {username: {password_hash, role}}
        self.users: Dict[str, Dict[str, str]] = {
            "admin": {
                "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "admin123"
                "role": Role.ADMIN.value
            },
            "user": {
                "password_hash": "$2b$12$GQJQVzkUcUvDqCnwPqD37Od98DcQcRbCgJg2P0aX7YpG5K1Q5Z6cK",  # "user123"
                "role": Role.USER.value
            }
        }
    
    def get_user(self, username: str) -> Optional[Dict[str, str]]:
        return self.users.get(username)
    
    def user_exists(self, username: str) -> bool:
        return username in self.users

# 全局用户存储实例
user_store = UserStore()

# Token请求模型
class TokenRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., min_length=3, description="用户密码")

# Token响应模型
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    role: str

# 认证响应模型
class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[TokenResponse] = None

# 错误响应模型
class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    timestamp: int

@router.post("/login", summary="用户登录", response_model=LoginResponse)
async def login(token_request: TokenRequest):
    """
    用户登录接口，验证用户名和密码并返回访问令牌
    
    - **username**: 用户名
    - **password**: 密码
    """
    # 验证用户名和密码
    if not user_store.user_exists(token_request.username):
        logger.warning(f"尝试使用不存在的用户名登录: {token_request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = user_store.get_user(token_request.username)
    
    # 验证密码
    if not verify_password(token_request.password, user["password_hash"]):
        logger.warning(f"用户 {token_request.username} 登录失败：密码错误")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌，包含用户信息和角色
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": token_request.username,
            "role": user["role"],
            "iat": datetime.utcnow().timestamp()
        },
        expires_delta=access_token_expires
    )
    
    logger.info(f"用户 {token_request.username} 登录成功，角色: {user['role']}")
    
    return LoginResponse(
        success=True,
        message="登录成功",
        token=TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 返回秒数
            role=user["role"]
        )
    )

# 保持向后兼容的token接口
@router.post("/token", summary="获取访问令牌", response_model=TokenResponse)
async def login_for_access_token(token_request: TokenRequest):
    """
    获取JWT访问令牌（向后兼容接口）
    """
    # 调用新的login函数，但返回兼容的格式
    response = await login(token_request)
    if not response.success or not response.token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=response.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return response.token

@router.post("/refresh", summary="刷新访问令牌")
async def refresh_access_token(current_user: dict = Depends(get_current_user)):
    """
    刷新访问令牌
    """
    # 验证用户是否仍然存在
    if not user_store.user_exists(current_user.get("sub")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = user_store.get_user(current_user.get("sub"))
    
    # 创建新的访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": current_user.get("sub"),
            "role": user["role"],
            "iat": datetime.utcnow().timestamp()
        },
        expires_delta=access_token_expires
    )
    
    logger.info(f"用户 {current_user.get('sub')} 刷新了访问令牌")
    
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=user["role"]
    )

@router.post("/logout", summary="用户登出")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    用户登出接口
    
    在实际项目中，这里应该将token加入黑名单
    """
    username = current_user.get("sub")
    logger.info(f"用户 {username} 登出")
    
    # 在实际项目中，这里应该将token加入黑名单
    # 由于我们使用的是无状态JWT，这里只能记录日志
    
    return {
        "success": True,
        "message": "登出成功",
        "timestamp": int(time.time())
    }

@router.get("/me", summary="获取当前用户信息")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    获取当前登录用户的信息
    """
    username = current_user.get("sub")
    user = user_store.get_user(username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return {
        "username": username,
        "role": user["role"],
        "authenticated_at": current_user.get("iat")
    }