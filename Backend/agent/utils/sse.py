from typing import AsyncGenerator, Dict, List, Optional, Tuple
from sse_starlette.sse import EventSourceResponse
from starlette.responses import Response
import asyncio
from asyncio import Queue
import time
# 避免使用下标语法，Python 3.8不支持

from datetime import datetime, timedelta
from agent.models.agui import AGUIEvent
from agent.utils.logger import logger


class SSEManager:
    """SSE连接管理器 - 优化版，支持事件批处理和背压控制"""

    def __init__(self):
        # 存储：process_id -> (事件队列, 创建时间, 最后活动时间)
        self.queues: Dict[str, Tuple[asyncio.Queue, float, float]] = {}
        # 锁：确保线程安全
        self.lock = asyncio.Lock()
        # 最大队列大小
        self.max_queue_size = 500
        # 队列超时时间（秒），5分钟无活动将被清理
        self.queue_timeout = 300
        # 批处理配置
        self.batch_size = 5
        self.batch_interval = 0.1  # 100ms
        # 事件类型优先级映射
        self.event_priority = {
            "error": 0,
            "task.complete": 1,
            "compliance.check.complete": 2,
            "model.extract.complete": 3,
            "file.upload.complete": 4,
            "progress": 5,
            "heartbeat": 6
        }

    async def create_queue(self, process_id: str) -> asyncio.Queue:
        """为任务创建事件队列 - 增强版，确保队列正确初始化"""
        async with self.lock:
            try:
                current_time = time.time()
                if process_id not in self.queues or self.queues[process_id] is None:
                    queue = asyncio.Queue(maxsize=self.max_queue_size)
                    self.queues[process_id] = (queue, current_time, current_time)
                    logger.info(f"SSE队列创建成功: process_id={process_id}, queue_size=0", extra={"processId": process_id})
                else:
                    # 更新最后活动时间
                    queue, created_time, _ = self.queues[process_id]
                    self.queues[process_id] = (queue, created_time, current_time)
                    logger.info(f"SSE队列已存在，已更新活动时间: process_id={process_id}, queue_size={queue.qsize()}", extra={"processId": process_id})
                return queue
            except Exception as e:
                logger.error(f"创建SSE队列异常: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                # 确保返回一个有效的队列
                queue = asyncio.Queue(maxsize=self.max_queue_size)
                self.queues[process_id] = (queue, time.time(), time.time())
                return queue

    async def get_queue(self, process_id: str) -> Optional[asyncio.Queue]:
        """获取指定process_id的队列，增强版"""
        async with self.lock:
            if process_id in self.queues and self.queues[process_id]:
                try:
                    queue, created_time, _ = self.queues[process_id]
                    # 更新最后活动时间
                    self.queues[process_id] = (queue, created_time, time.time())
                    return queue
                except Exception as e:
                    logger.error(f"获取队列时出错: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                    return None
            return None

    async def remove_queue(self, process_id: str) -> None:
        """移除指定process_id的队列，增强版"""
        async with self.lock:
            if process_id in self.queues:
                queue_info = self.queues[process_id]
                if queue_info:
                    try:
                        queue = queue_info[0]  # 获取队列对象
                        # 清空队列中的所有任务
                        try:
                            while not queue.empty():
                                try:
                                    queue.get_nowait()
                                    queue.task_done()
                                except asyncio.QueueEmpty:
                                    break
                                except Exception as inner_e:
                                    logger.error(f"处理队列任务时出错: {str(inner_e)}, process_id={process_id}", 
                                                extra={"processId": process_id})
                        except Exception as e:
                            logger.error(f"清理队列时出错: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                    except Exception as e:
                        logger.error(f"访问队列信息时出错: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                
                # 移除队列引用
                del self.queues[process_id]
                logger.info(f"已移除SSE队列: process_id={process_id}", extra={"processId": process_id})


    async def send_event(self, process_id: str, event: AGUIEvent) -> bool:
        """发送事件到指定process_id的队列，增强版"""
        try:
            queue = await self.get_queue(process_id)
            if queue is None:
                # 队列不存在，尝试创建新队列
                queue = await self.create_queue(process_id)
                logger.info(f"队列不存在，已创建新队列: process_id={process_id}", extra={"processId": process_id})
            
            # 队列满时的处理策略
            if queue.full():
                logger.warning(f"SSE队列已满，将智能丢弃低优先级事件: process_id={process_id}, 当前大小={queue.qsize()}", 
                             extra={"processId": process_id})
                
                # 收集队列中的所有事件
                current_events = []
                while not queue.empty():
                    try:
                        current_events.append(queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                
                # 计算当前事件的优先级
                event_priority = self.event_priority.get(event.event_type, 999)
                
                # 智能筛选和重新入队
                events_to_keep = []
                for existing_event in current_events:
                    # 保留所有比当前事件优先级高的事件
                    existing_priority = self.event_priority.get(existing_event.event_type, 999)
                    if existing_priority < event_priority:
                        events_to_keep.append(existing_event)
                    # 对于相同优先级的进度事件，我们可以只保留最新的
                    elif existing_priority == event_priority and event.event_type == "progress":
                        # 如果是进度事件，我们需要比较以确定是否应该替换或保留
                        if (event.event_payload and 'step' in event.event_payload and 
                            existing_event.event_payload and 'step' in existing_event.event_payload):
                            # 如果现有进度事件的步骤较新或相同，则保留
                            if existing_event.event_payload['step'] >= event.event_payload['step']:
                                events_to_keep.append(existing_event)
                            else:
                                events_to_keep.append(event)
                        else:
                            events_to_keep.append(event)
                
                # 如果队列中没有优先级更高的事件，且队列仍有空间，添加当前事件
                if len(events_to_keep) < self.max_queue_size:
                    # 检查是否已经添加了当前事件
                    current_event_added = any(e is event or 
                                            (e.type == event.type and 
                                            e.data == event.data) for e in events_to_keep)
                    if not current_event_added:
                        events_to_keep.append(event)
                
                # 重新入队
                for event_to_keep in events_to_keep:
                    if not queue.full():
                        try:
                            await queue.put(event_to_keep)
                        except Exception as inner_e:
                            logger.error(f"重新入队事件失败: {str(inner_e)}, process_id={process_id}", 
                                        extra={"processId": process_id})
                
                logger.info(f"SSE队列清理完成: 原始事件数={len(current_events)}, 保留事件数={len(events_to_keep)}", 
                           extra={"processId": process_id})
            else:
                # 尝试放入队列，处理可能的异常
                try:
                    await queue.put(event)
                    # 更新队列活动时间
                    async with self.lock:
                        if process_id in self.queues and self.queues[process_id]:
                            queue, created_time, _ = self.queues[process_id]
                            self.queues[process_id] = (queue, created_time, time.time())
                    logger.debug(f"SSE事件发送成功: process_id={process_id}, event_type={event.type}", 
                                extra={"processId": process_id})
                    return True
                except asyncio.QueueFull:
                    logger.warning(f"队列已满，事件发送失败: process_id={process_id}, event_type={event.type}", 
                                extra={"processId": process_id})
                    # 尝试清理后重试
                    return await self.send_event(process_id, event)
                except Exception as e:
                    logger.error(f"发送事件异常: {str(e)}, process_id={process_id}, event_type={event.type}", 
                                extra={"processId": process_id})
                    return False
            return True
        except Exception as e:
            logger.error(f"SSE事件处理失败: {str(e)}, process_id={process_id}", extra={"processId": process_id})
            return False

    async def sse_generator(self, process_id: str) -> AsyncGenerator[str, None]:
        """生成SSE事件流的异步生成器，增强版"""
        queue = None
        heartbeat_task = None
        try:
            # 获取队列
            queue = await self.get_queue(process_id)
            if queue is None:
                queue = await self.create_queue(process_id)
                logger.info(f"为SSE生成器创建新队列: process_id={process_id}", extra={"processId": process_id})
            
            # 启动心跳任务
            try:
                heartbeat_task = asyncio.create_task(self._send_heartbeats(process_id))
                logger.info(f"SSE心跳任务已启动: process_id={process_id}", extra={"processId": process_id})
            except Exception as e:
                logger.error(f"启动心跳任务失败: {str(e)}, process_id={process_id}", extra={"processId": process_id})
            
            # 批处理事件计数器
            batch_count = 0
            batch_start = time.time()
            batch_events = []
            
            # 主要事件处理循环
            while True:
                try:
                    # 使用超时来检查取消状态
                    try:
                        # 设置合理的超时，避免长时间阻塞
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # 超时检查，用于响应取消
                        if asyncio.current_task().done():
                            raise asyncio.CancelledError()
                        continue
                    
                    # 添加到批处理
                    batch_events.append(event)
                    batch_count += 1
                    
                    # 检查是否应该发送批处理
                    current_time = time.time()
                    if (batch_count >= self.batch_size or 
                        (current_time - batch_start) >= self.batch_interval):
                        
                        # 按优先级排序事件
                        batch_events.sort(key=lambda e: self.event_priority.get(e.type, 999))
                        
                        # 尝试合并进度事件
                        merged_events = []
                        progress_events = []
                        
                        for e in batch_events:
                            if e.type == "progress":
                                progress_events.append(e)
                            else:
                                merged_events.append(e)
                        
                        # 如果有多个进度事件，只保留最新的
                        if progress_events:
                            # 按步骤排序，选择最新的
                            progress_events.sort(key=lambda e: e.data.get('step', 0) if e.data else 0, 
                                               reverse=True)
                            merged_events.append(progress_events[0])
                        
                        # 发送合并后的事件
                        for event_to_send in merged_events:
                            # 构建SSE事件
                            sse_event = f"event: {event_to_send.type}\ndata: {event_to_send.model_dump_json()}\n\n"
                            try:
                                yield sse_event
                                logger.debug(f"SSE事件已发送: type={event_to_send.type}, process_id={process_id}",
                                            extra={"processId": process_id})
                            except Exception as e:
                                logger.error(f"发送SSE事件失败: {str(e)}, type={event_to_send.type}, process_id={process_id}",
                                            extra={"processId": process_id})
                        
                        # 更新队列活动时间
                        async with self.lock:
                            if process_id in self.queues and self.queues[process_id]:
                                q, created_time, _ = self.queues[process_id]
                                self.queues[process_id] = (q, created_time, time.time())
                        
                        # 重置批处理
                        batch_count = 0
                        batch_start = time.time()
                        batch_events = []
                    
                    # 标记任务完成
                    queue.task_done()
                
                except asyncio.CancelledError:
                    logger.info(f"SSE连接已取消: process_id={process_id}", extra={"processId": process_id})
                    break
                except Exception as e:
                    logger.error(f"处理SSE事件时出错: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                    # 确保不会因为单个事件错误而中断整个循环
                    continue
        
        finally:
            # 清理资源
            try:
                # 取消心跳任务
                if heartbeat_task and not heartbeat_task.done():
                    try:
                        heartbeat_task.cancel()
                        try:
                            await asyncio.wait_for(heartbeat_task, timeout=1.0)
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            pass
                        logger.info(f"SSE心跳任务已取消: process_id={process_id}", extra={"processId": process_id})
                    except Exception as e:
                        logger.error(f"取消心跳任务失败: {str(e)}, process_id={process_id}", extra={"processId": process_id})
            except Exception as e:
                logger.error(f"心跳任务清理异常: {str(e)}, process_id={process_id}", extra={"processId": process_id})
            
            try:
                # 清理队列
                await self.remove_queue(process_id)
                logger.info(f"SSE连接关闭，资源已清理: process_id={process_id}", extra={"processId": process_id})
            except Exception as e:
                logger.error(f"队列清理异常: {str(e)}, process_id={process_id}", extra={"processId": process_id})


    def _merge_events(self, events: List[AGUIEvent]) -> List[AGUIEvent]:
        """合并相同类型的事件，减少传输量"""
        if not events:
            return []
            
        merged = []
        event_dict = {}
        
        for event in events:
            # 特殊处理进度事件，只保留最新的
            if event.type == "progress":
                event_dict[event.type] = event
            # 特殊处理文件上传进度，合并成一个事件
            elif event.type == "file.upload.progress":
                if event.type not in event_dict:
                    event_dict[event.type] = event
                else:
                    # 更新为最新的进度数据
                    try:
                        current_data = event_dict[event.type].model_dump()
                        new_data = event.model_dump()
                        # 保留最新的进度信息
                        if new_data.get('data', {}).get('progress', 0) > \
                           current_data.get('data', {}).get('progress', 0):
                            event_dict[event.type] = event
                    except Exception:
                        # 合并失败时保留最新的事件
                        event_dict[event.type] = event
            # 其他事件类型，如果有多个相同类型的，保留最新的
            else:
                event_dict[event.type] = event
        
        # 转回列表并保持顺序
        for event in events:
            if event.type in event_dict:
                merged.append(event_dict[event.type])
                del event_dict[event.type]
        
        return merged
    
    async def _send_heartbeats(self, process_id: str) -> None:
        """后台心跳任务 - 增强版，支持自适应间隔和异常处理"""
        try:
            # 自适应心跳间隔（秒）
            base_interval = 30  # 基础间隔30秒
            current_interval = base_interval
            
            logger.info(f"心跳任务已启动: process_id={process_id}", extra={"processId": process_id})
            
            while True:
                try:
                    # 获取队列检查是否仍在使用中
                    queue = await self.get_queue(process_id)
                    if queue is None:
                        logger.info(f"队列不存在，停止心跳: process_id={process_id}", extra={"processId": process_id})
                        break
                    
                    # 创建心跳事件
                    heartbeat_event = AGUIEvent(
                        type="heartbeat",
                        data={
                            "timestamp": int(time.time() * 1000),
                            "status": "active",
                            "queue_size": queue.qsize(),
                            "process_id": process_id
                        },
                        timestamp=int(time.time() * 1000)
                    )
                    
                    # 发送心跳事件
                    await self.send_event(process_id, heartbeat_event)
                    
                    # 监控队列大小，如果队列过大，临时增加心跳频率
                    queue_size = queue.qsize()
                    if queue_size > self.max_queue_size * 0.7:
                        current_interval = max(5, base_interval // 2)  # 最多增加到5秒一次
                        logger.warning(f"队列接近满载，增加心跳频率: process_id={process_id}, queue_size={queue_size}",
                                    extra={"processId": process_id})
                    else:
                        current_interval = base_interval  # 恢复正常间隔
                    
                    # 等待下一次心跳
                    try:
                        await asyncio.sleep(current_interval)
                    except asyncio.CancelledError:
                        logger.info(f"心跳任务被取消: process_id={process_id}", extra={"processId": process_id})
                        break
                        
                except asyncio.CancelledError:
                    logger.info(f"心跳任务被取消: process_id={process_id}", extra={"processId": process_id})
                    break
                except Exception as e:
                    logger.error(f"心跳事件发送失败: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                    # 出错时减少心跳频率，但继续运行
                    try:
                        await asyncio.sleep(max(60, current_interval * 2))
                    except asyncio.CancelledError:
                        break
        except Exception as e:
            logger.error(f"心跳任务异常终止: {str(e)}, process_id={process_id}", extra={"processId": process_id})

    async def monitor_queue_health(self) -> None:
        """队列健康监控 - 增强版，支持自动清理和状态报告"""
        try:
            logger.info("启动SSE队列健康监控")
            
            while True:
                try:
                    current_time = time.time()
                    queues_to_remove = []
                    
                    async with self.lock:
                        # 深拷贝队列字典以避免在遍历时修改
                        queues_copy = dict(self.queues)
                    
                    # 检查每个队列的健康状态
                    for process_id, queue_info in queues_copy.items():
                        try:
                            if queue_info:
                                queue, created_time, last_active_time = queue_info
                                
                                # 检查队列是否超时（5分钟无活动）
                                if (current_time - last_active_time) > self.queue_timeout:
                                    logger.warning(f"检测到超时队列，将自动清理: process_id={process_id}, 无活动时间={int(current_time - last_active_time)}秒",
                                                extra={"processId": process_id})
                                    queues_to_remove.append(process_id)
                                
                                # 检查队列大小
                                queue_size = queue.qsize()
                                if queue_size > self.max_queue_size * 0.8:
                                    logger.warning(f"队列接近满载: process_id={process_id}, queue_size={queue_size}/{self.max_queue_size}",
                                                extra={"processId": process_id})
                                
                                # 检查队列存活时间
                                queue_age = current_time - created_time
                                if queue_age > 3600:  # 超过1小时
                                    logger.info(f"长时间运行的队列: process_id={process_id}, age={int(queue_age / 60)}分钟, size={queue_size}",
                                            extra={"processId": process_id})
                                
                                # 检查是否有长时间空闲的队列（有事件但长时间未处理）
                                if queue_size > 0 and (current_time - last_active_time) > 120:
                                    logger.warning(f"检测到可能卡住的队列: process_id={process_id}, 队列大小={queue_size}, 无活动时间={int(current_time - last_active_time)}秒",
                                                extra={"processId": process_id})
                        except Exception as e:
                            logger.error(f"检查队列健康时出错: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                            # 如果队列信息有误，将其加入移除列表
                            queues_to_remove.append(process_id)
                    
                    # 清理不健康的队列
                    for process_id in queues_to_remove:
                        try:
                            logger.info(f"清理不健康队列: process_id={process_id}", extra={"processId": process_id})
                            await self.remove_queue(process_id)
                        except Exception as e:
                            logger.error(f"清理队列失败: {str(e)}, process_id={process_id}", extra={"processId": process_id})
                    
                    # 记录整体队列状态
                    if queues_copy:
                        total_queues = len(queues_copy)
                        active_queues = sum(1 for info in queues_copy.values() if info and (current_time - info[2]) < 60)  # 1分钟内活动的队列
                        total_events = sum(info[0].qsize() for info in queues_copy.values() if info)
                        
                        logger.info(f"SSE队列状态报告 - 总队列数: {total_queues}, 活跃队列数: {active_queues}, 总事件数: {total_events}")
                    
                    # 监控间隔
                    await asyncio.sleep(60)  # 每分钟检查一次
                    
                except asyncio.CancelledError:
                    logger.info("队列健康监控被取消")
                    break
                except Exception as e:
                    logger.error(f"队列健康监控异常: {str(e)}")
                    # 出错后等待一段时间再重试
                    try:
                        await asyncio.sleep(30)
                    except asyncio.CancelledError:
                        break
        except Exception as e:
            logger.error(f"队列健康监控任务异常终止: {str(e)}")


    def create_sse_response(self, process_id: str) -> Response:
        """创建SSE响应对象，增强版"""
        try:
            # 为该process_id创建队列（如果不存在）
            asyncio.create_task(self.create_queue(process_id))
            
            logger.info(f"创建SSE响应: process_id={process_id}", extra={"processId": process_id})
            
            # 创建EventSourceResponse对象，设置适当的超时和重试
            response = EventSourceResponse(
                self.sse_generator(process_id),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
                    "Access-Control-Allow-Origin": "*",  # CORS支持
                    "Access-Control-Allow-Methods": "GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                }
            )
            
            # 设置响应的额外属性
            response.retry = 1000  # 客户端重连间隔（毫秒）
            
            return response
        except Exception as e:
            logger.error(f"创建SSE响应失败: {str(e)}, process_id={process_id}", extra={"processId": process_id})
            # 返回错误响应
            return Response(
                content=f"Error creating SSE connection: {str(e)}",
                status_code=500,
                media_type="text/plain",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )

    def _merge_events(self, events: List[AGUIEvent]) -> List[AGUIEvent]:
        """合并相同类型的事件，减少传输量 - 适配新的事件结构"""
        if not events:
            return []
        
        # 按类型分组事件
        events_by_type = {}
        
        for event in events:
            event_type = getattr(event, 'event_type', 'unknown')
            if event_type not in events_by_type:
                events_by_type[event_type] = []
            events_by_type[event_type].append(event)
        
        # 处理不同类型的事件合并策略
        merged_events = []
        
        for event_type, type_events in events_by_type.items():
            # 进度事件：只保留最新的
            if event_type == "progress":
                # 按步骤排序，取最新的
                sorted_events = sorted(
                    type_events,
                    key=lambda e: e.event_payload.get('step', 0) if e.event_payload else 0,
                    reverse=True
                )
                if sorted_events:
                    merged_events.append(sorted_events[0])
            
            # 错误事件：保留所有错误
            elif event_type == "error":
                merged_events.extend(type_events)
            
            # 完成类事件：保留所有完成事件
            elif event_type in ["task.complete", "compliance.check.complete", "model.extract.complete"]:
                merged_events.extend(type_events)
            
            # 心跳事件：只保留一个
            elif event_type == "heartbeat":
                # 取最后一个心跳
                if type_events:
                    merged_events.append(type_events[-1])
            
            # 其他事件：默认保留所有
            else:
                merged_events.extend(type_events)
        
        return merged_events


# 创建全局SSE管理器实例
sse_manager = SSEManager()