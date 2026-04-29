import asyncio
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple, Any
from fastapi import UploadFile
from datetime import datetime
from agent.config import settings
from agent.models.agui import FileUploadCompleteData
from agent.models.algorithm_data import FileInfo
from agent.utils.logger import logger
from agent.utils.error import ErrorCode, get_error_info


class FileService:
    """文件处理服务"""

    def __init__(self):
        self.upload_dir = settings.upload_dir

    def _generate_file_path(self, file_id: str, file_ext: str) -> Path:
        """生成文件存储路径（按日期分区）"""
        date_dir = self.upload_dir / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(exist_ok=True, parents=True)
        return date_dir / f"{file_id}.{file_ext}"

    def _calculate_file_md5(self, file_path: Path) -> str:
        """计算文件MD5校验码"""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    async def save_upload_file(self, file: Any, file_id: str) -> Tuple[
        Optional[FileUploadCompleteData], Optional[ErrorCode]]:
        """保存上传文件"""
        try:
            # 安全地获取文件名，同时支持驼峰和蛇形命名
            filename = getattr(file, 'fileName', None) or getattr(file, 'filename', None) or f"file_{file_id}"
            
            # 提取文件扩展名
            file_ext = filename.split(".")[-1].lower() if "." in filename else "bin"
            file_path = self._generate_file_path(file_id, file_ext)
            
            # 尝试以不同方式获取文件内容
            file_size = 0
            
            # 1. 检查是否有storagePath属性（FileInfo或类似对象）
            storage_path = getattr(file, 'storagePath', None)
            if storage_path:
                try:
                    # 从storagePath复制文件
                    with open(storage_path, 'rb') as src, open(file_path, 'wb') as dst:
                        while chunk := src.read(4096):
                            dst.write(chunk)
                            file_size += len(chunk)
                except Exception as copy_error:
                    logger.warning(f"无法从storagePath复制文件: {str(copy_error)}", extra={"processId": file_id})
                    # 使用默认大小
                    file_size = getattr(file, 'fileSize', 0) or getattr(file, 'size', 0)
            # 2. 检查是否有read方法（UploadFile或文件流）
            elif hasattr(file, 'read'):
                try:
                    if asyncio.iscoroutinefunction(file.read):
                        # 异步读取
                        with open(file_path, "wb") as f:
                            while chunk := await file.read(4096):
                                f.write(chunk)
                                file_size += len(chunk)
                    else:
                        # 同步读取
                        with open(file_path, "wb") as f:
                            while chunk := file.read(4096):
                                f.write(chunk)
                                file_size += len(chunk)
                except Exception as read_error:
                    logger.warning(f"无法读取文件内容: {str(read_error)}", extra={"processId": file_id})
                    file_size = 0
            else:
                # 如果都不行，创建一个空文件并记录警告
                open(file_path, 'wb').close()
                logger.warning(f"无法获取文件内容，创建空文件", extra={"processId": file_id})
            
            # 计算MD5
            md5 = self._calculate_file_md5(file_path)
            
            # 生成文件完成数据
            file_data = FileUploadCompleteData(
                fileId=file_id,
                fileName=filename,
                storagePath=str(file_path),
                md5=md5,
                finishTime=int(datetime.now().timestamp() * 1000),
                fileSize=file_size,
                succeed="上传成功"
            )

            # 使用已获取的filename变量进行日志记录
            logger.info(
                f"文件保存成功: fileId={file_id}, fileName={filename}, size={file_size}",
                extra={"processId": file_id}
            )
            return file_data, None

        except Exception as e:
            logger.error(
                f"文件保存失败: {str(e)}",
                extra={"processId": file_id, "algorithmTaskId": ""},
                exc_info=True
            )
            return None, ErrorCode.FILE_UPLOAD_ERROR

    def get_file_info(self, file_id: str, file_path: str) -> Tuple[Optional[dict], Optional[ErrorCode]]:
        """获取文件信息"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"文件不存在: fileId={file_id}, path={file_path}", extra={"processId": file_id})
                return None, ErrorCode.FILE_NOT_FOUND

            # 获取文件大小
            file_size = file_path.stat().st_size
            # 获取文件类型
            file_type = file_path.suffix.lstrip(".")

            return {
                       "fileId": file_id,
                       "fileName": file_path.name,
                       "fileSize": file_size,
                       "fileType": file_type,
                       "storagePath": str(file_path)
                   }, None

        except Exception as e:
            logger.error(
                f"获取文件信息失败: {str(e)}",
                extra={"processId": file_id},
                exc_info=True
            )
            return None, ErrorCode.FILE_READ_ERROR

    def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            file_path = Path(file_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"文件删除成功: path={file_path}", extra={"processId": "", "algorithmTaskId": ""})
                return True
            return False
        except Exception as e:
            logger.error(f"文件删除失败: {str(e)}", extra={"processId": "", "algorithmTaskId": ""}, exc_info=True)
            return False


# 初始化文件服务实例
file_service = FileService()