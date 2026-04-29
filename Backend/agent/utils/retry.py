import asyncio
from typing import Callable, TypeVar, Any, Dict, Tuple
from functools import wraps
from agent.config import settings
from agent.utils.logger import logger

T = TypeVar('T')


def async_retry(
        retry_exceptions: Tuple[Exception, ...] = (Exception,),
        max_attempts: int = None,
        initial_delay: float = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    异步指数退避重试装饰器

    Args:
        retry_exceptions: 需要重试的异常类型
        max_attempts: 最大重试次数（默认使用配置）
        initial_delay: 初始重试间隔（默认使用配置）
    """
    max_attempts = max_attempts or settings.retry_max_count
    initial_delay = initial_delay or settings.retry_initial_delay

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # 提取日志所需的额外字段
            extra = kwargs.pop("extra", {})
            process_id = extra.get("processId", "")
            algorithm_task_id = extra.get("algorithmTaskId", "")

            attempts = 0
            while attempts < max_attempts:
                attempts += 1
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    # 最后一次尝试失败，抛出异常
                    if attempts >= max_attempts:
                        logger.error(
                            f"重试已达最大次数({max_attempts})，操作失败: {str(e)}",
                            extra={"processId": process_id, "algorithmTaskId": algorithm_task_id},
                            exc_info=True
                        )
                        raise

                    # 计算指数退避间隔
                    delay = initial_delay * (2 ** (attempts - 1))
                    # 加入随机抖动（±10%）避免同时重试
                    jitter = delay * (0.9 + (0.2 * asyncio.random()))

                    logger.warning(
                        f"第{attempts}次尝试失败，将在{jitter:.2f}秒后重试: {str(e)}",
                        extra={"processId": process_id, "algorithmTaskId": algorithm_task_id},
                        exc_info=True
                    )

                    # 等待重试间隔
                    await asyncio.sleep(jitter)

        return wrapper

    return decorator