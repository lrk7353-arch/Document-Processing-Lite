from datetime import datetime, timedelta
from typing import Optional, Union, List
from enum import Enum
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from agent.config import settings
from agent.db.session import get_db
from agent.utils.logger import logger

# OAuth2密码Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer认证方案
security = HTTPBearer()

# JWT配置从settings读取
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# 角色枚举
class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

# 权限定义
class Permission(str, Enum):
    VIEW_DOCUMENTS = "view_documents"
    UPLOAD_DOCUMENTS = "upload_documents"
    PROCESS_DOCUMENTS = "process_documents"
    MANAGE_USERS = "manage_users"
    VIEW_REPORTS = "view_reports"

# 角色权限映射
ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.VIEW_DOCUMENTS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.PROCESS_DOCUMENTS,
        Permission.MANAGE_USERS,
        Permission.VIEW_REPORTS
    ],
    Role.USER: [
        Permission.VIEW_DOCUMENTS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.PROCESS_DOCUMENTS,
        Permission.VIEW_REPORTS
    ],
    Role.GUEST: [
        Permission.VIEW_DOCUMENTS
    ]
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    获取密码的哈希值
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
    
    Returns:
        str: 编码后的JWT令牌
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def _verify_token_impl(token: str, credentials_exception: HTTPException) -> dict:
    """
    验证令牌的内部实现
    
    Args:
        token: JWT令牌
        credentials_exception: 认证失败异常
        
    Returns:
        解码后的令牌数据
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.error("令牌中缺少用户标识")
            raise credentials_exception
            
        # 检查令牌是否过期
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            logger.error("令牌已过期")
            raise credentials_exception
            
        return payload
    except JWTError as e:
        logger.error(f"JWT验证失败: {str(e)}")
        raise credentials_exception

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    验证令牌
    
    Args:
        credentials: HTTP认证凭据
    
    Returns:
        dict: 解码后的令牌数据
    
    Raises:
        HTTPException: 认证失败时抛出
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 开发环境支持固定token
    if credentials.credentials == "dev-token-for-testing":
        logger.info("开发环境：使用固定测试token")
        # 返回一个模拟的用户信息
        return {
            "sub": "dev_user",
            "role": "admin",
            "exp": datetime.utcnow().timestamp() + 3600  # 1小时过期
        }
    
    return _verify_token_impl(credentials.credentials, credentials_exception)

def verify_token_string(token: str) -> dict:
    """
    验证令牌字符串
    
    Args:
        token: JWT令牌字符串
    
    Returns:
        解码后的令牌数据
    
    Raises:
        HTTPException: 认证失败时抛出
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return _verify_token_impl(token, credentials_exception)

def get_user_permissions(user_role: str) -> List[Permission]:
    """
    获取用户角色对应的权限列表
    
    Args:
        user_role: 用户角色
        
    Returns:
        权限列表
    """
    try:
        role_enum = Role(user_role)
        return ROLE_PERMISSIONS.get(role_enum, [])
    except ValueError:
        # 角色不存在时返回空权限列表
        logger.warning(f"未知角色: {user_role}")
        return []

def check_permissions(user: dict, required_permissions: List[Permission]) -> bool:
    """
    检查用户是否具有所需的权限
    
    Args:
        user: 用户信息字典，包含role字段
        required_permissions: 需要的权限列表
        
    Returns:
        用户是否具有所有所需权限
    """
    user_role = user.get("role")
    if not user_role:
        logger.warning("用户角色未定义")
        return False
    
    user_permissions = get_user_permissions(user_role)
    
    # 检查是否拥有所有必需的权限
    for permission in required_permissions:
        if permission not in user_permissions:
            logger.warning(f"用户 {user.get('sub')} 缺少权限: {permission}")
            return False
    
    return True

def get_current_user(payload: dict = Depends(verify_token)) -> dict:
    """
    获取当前用户信息
    
    Args:
        payload: 解码后的令牌数据
    
    Returns:
        dict: 用户信息，包含角色和权限
    """
    # 添加用户角色和权限到返回的用户信息中
    user_role = payload.get("role", Role.USER.value)
    payload["permissions"] = [p.value for p in get_user_permissions(user_role)]
    
    return payload

def get_current_user_oauth2(token: str = Depends(oauth2_scheme)) -> dict:
    """
    获取当前用户信息（使用OAuth2密码流）
    
    Args:
        token: JWT令牌
    
    Returns:
        dict: 用户信息，包含角色和权限
    """
    payload = verify_token_string(token)
    
    # 添加用户角色和权限到返回的用户信息中
    user_role = payload.get("role", Role.USER.value)
    payload["permissions"] = [p.value for p in get_user_permissions(user_role)]
    
    return payload

# 权限依赖项工厂函数
def require_permissions(*required_permissions: Permission):
    """
    创建一个权限检查依赖项
    
    Args:
        *required_permissions: 需要的权限列表
        
    Returns:
        权限检查依赖项函数
    """
    def permission_checker(current_user: dict = Depends(get_current_user)):
        if not check_permissions(current_user, list(required_permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user
    
    return permission_checker