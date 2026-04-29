import aiohttp
import asyncio
import json
import time
import os
from typing import Dict, Any, Optional
from agent.config import settings
from agent.utils.logger import logger


class AlgorithmClient:
    """
    算法服务客户端，负责与运行在8001端口的CPU服务通信
    """
    
    def __init__(self):
        # 算法服务基础URL - 从配置中读取
        self.base_url = settings.algorithm_api_url or "http://localhost:8001"
        # API端点
        self.health_endpoint = f"{self.base_url}/health"
        self.process_endpoint = f"{self.base_url}/api/algorithm/invoice-extract"
        # 服务令牌 - 从配置中获取
        self.service_token = settings.algorithm_service_token or "your_service_token_here"
    
    async def health_check(self) -> bool:
        """
        检查算法服务健康状态
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-Service-Token": self.service_token,
                    "Content-Type": "application/json"
                }
                async with session.get(
                    self.health_endpoint,
                    headers=headers,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("status") == "healthy"
                    logger.error(f"算法服务健康检查失败: HTTP {response.status}")
                    return False
        except Exception as e:
            logger.error(f"算法服务连接失败: {str(e)}", exc_info=True)
            return False
    
    async def process_document(
        self,
        file_path: str,
        file_type: str,
        process_id: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        调用算法服务处理文档
        
        Args:
            file_path: 本地文件路径
            file_type: 文件MIME类型
            process_id: 处理任务ID
            max_retries: 最大重试次数
            
        Returns:
            处理结果
        """
        retry_count = 0
        last_error = None
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        while retry_count < max_retries:
            try:
                logger.info(
                    f"调用算法服务处理文档，尝试 {retry_count + 1}/{max_retries}",
                    extra={"processId": process_id}
                )
                
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "X-Service-Token": self.service_token,
                        "Content-Type": "application/json"
                    }
                    
                    # 准备请求数据，匹配算法服务的AlgorithmRequest模型
                    # 使用绝对路径，避免算法服务工作目录不同导致文件无法读取
                    abs_path = os.path.abspath(file_path)
                    request_data = {
                        "processId": process_id,
                        "fileInfo": {
                            "fileId": process_id,  # 使用process_id作为fileId
                            "fileName": file_name,
                            "storagePath": abs_path,  # 传递绝对路径，算法服务可直接读取
                            "fileType": file_type,
                            "fileSize": file_size,
                            "uploadTime": int(time.time() * 1000)
                        },
                        "modelParams": {
                            "modelId": "model_6_focus",
                            "modelName": "发票关键字段提取模型(model_6_focus)",
                            "targetFields": ["发票号码", "开票日期", "金额", "税率", "税额", "购买方名称", "销售方名称"],
                            "confidenceThreshold": 0.85,
                            "useCache": True
                        },
                        "callbackUrl": "http://localhost:8000/api/algorithm/callback",  # 保持URL干净，不包含额外参数
                        "validationParams": {
                            "needValidation": True,
                            "ruleIds": ["invoice_basic_validation"],
                            "ruleVersion": "v1.0",
                            "skipOnFail": False
                        },
                        "priority": "medium",
                        "timestamp": int(time.time() * 1000)
                    }
                    
                    # 发送请求
                    async with session.post(
                        self.process_endpoint,
                        json=request_data,
                        headers=headers,
                        timeout=300
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(
                                f"算法服务处理任务已受理: {result.get('algorithmTaskId')}",
                                extra={"processId": process_id}
                            )
                            
                            # 返回算法服务受理结果，实际处理结果将通过callbackUrl异步返回
                            # 移除模拟等待和模拟结果，让真正的异步处理流程正常工作
                            return {
                                "status": "accepted",
                                "algorithmTaskId": result.get('algorithmTaskId'),
                                "message": "文档处理任务已受理，请等待异步处理完成",
                                "data": {
                                    "processId": process_id,
                                    "callbackUrl": request_data.get('callbackUrl'),
                                    "taskStatus": "processing"
                                }
                            }
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"算法服务返回错误: HTTP {response.status}, {error_text}",
                                extra={"processId": process_id}
                            )
                            last_error = f"HTTP {response.status}: {error_text}"
                
            except aiohttp.ClientError as e:
                logger.error(
                    f"算法服务通信异常: {str(e)}",
                    extra={"processId": process_id},
                    exc_info=True
                )
                last_error = f"ClientError: {str(e)}"
            except Exception as e:
                logger.error(
                    f"调用算法服务时发生未知异常: {str(e)}",
                    extra={"processId": process_id},
                    exc_info=True
                )
                last_error = f"UnknownError: {str(e)}"
            
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # 指数退避
                logger.info(
                    f"算法服务调用失败，{wait_time}秒后重试",
                    extra={"processId": process_id}
                )
                await asyncio.sleep(wait_time)
        
        # 所有重试都失败
        logger.error(
            f"算法服务调用失败，已达到最大重试次数",
            extra={"processId": process_id}
        )
        
        # 返回错误信息，以便前端展示
        return {
            "status": "error",
            "message": last_error or "算法服务调用失败",
            "data": None
        }
    
    async def validate_invoice(
        self,
        invoice_data: Dict[str, Any],
        process_id: str
    ) -> Dict[str, Any]:
        """
        调用算法服务验证发票数据
        
        Args:
            invoice_data: 发票数据
            process_id: 处理任务ID
            
        Returns:
            验证结果
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.service_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{self.base_url}/validate_invoice",
                    json=invoice_data,
                    headers=headers,
                    timeout=60
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"发票验证失败: HTTP {response.status}, {error_text}",
                            extra={"processId": process_id}
                        )
                        return {"status": "error", "message": error_text}
        except Exception as e:
            logger.error(
                f"调用发票验证服务失败: {str(e)}",
                extra={"processId": process_id},
                exc_info=True
            )
            return {"status": "error", "message": str(e)}