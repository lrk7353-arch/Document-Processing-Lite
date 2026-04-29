# 基于AG-UI协议的智能体后端系统实现

## 项目介绍
基于AG-UI协议的智能体后端系统实现是一个基于FastAPI和LangGraph构建的商业发票智能处理系统，能够实现从文件上传、多模态模型调用、合规检查到结果返回的完整处理流程，并通过SSE技术向前端推送实时状态。

## 核心功能

### 1. 文件处理
- 支持PDF、JPEG、PNG格式商业发票上传
- 文件验证、保存与MD5校验
- 生成唯一任务标识跟踪处理进度

### 2. 智能体状态管理
- 基于LangGraph的状态机驱动流程
- 完整状态流转：idle → processing → completed/failed
- 各阶段状态实时推送

### 3. 多模态模型调用
- 调用发票关键字段提取模型
- 支持字段包括：发票号、开票日期、销售方、购买方、商品描述、数量、单价、金额等
- 工具调用事件实时推送

### 4. 合规检查机制
- 执行发票格式校验规则
- 金额逻辑一致性验证
- 日期有效性检查
- 风险提示生成

### 5. 实时状态推送
- 基于SSE技术的AG-UI协议事件流
- 全流程状态实时监控
- 支持文件上传、模型调度、合规检查、结果生成等事件推送

## 技术架构

### 后端框架
- FastAPI：高性能Web框架
- LangGraph：智能体状态管理
- SQLAlchemy：数据库ORM
- PostgreSQL：数据存储（可选）

### 通信协议
- RESTful API：文件上传与操作接口
- SSE (Server-Sent Events)：实时事件流推送
- AG-UI协议：前端交互规范

## 目录结构

```
agent/
├── api/            # API路由定义
│   ├── action.py   # 用户操作接口
│   ├── algorithm_in.py  # 算法回调接口
│   ├── compliance.py    # 合规检查接口
│   ├── file.py     # 文件上传接口
│   └── sse.py      # SSE事件流接口
├── config.py       # 配置管理
├── db/             # 数据库相关
│   ├── crud/       # CRUD操作
│   ├── init.py     # 数据库初始化
│   └── session.py  # 数据库会话
├── langgraph/      # 智能体状态机
│   ├── graph.py    # 状态图定义
│   ├── nodes/      # 处理节点
│   └── state.py    # 状态定义
├── models/         # 数据模型
│   ├── agui.py     # AG-UI协议模型
│   ├── algorithm_data.py  # 算法接口模型
│   └── db.py       # 数据库模型
├── service/        # 业务服务
│   ├── algorithm_service.py  # 算法交互服务
│   ├── compliance_service.py # 合规检查服务
│   ├── db_service.py      # 数据库服务
│   └── file_service.py    # 文件处理服务
├── utils/          # 工具函数
│   ├── error.py    # 错误定义
│   ├── logger.py   # 日志工具
│   ├── retry.py    # 重试机制
│   └── sse.py      # SSE管理
├── main.py         # 应用入口
└── uploads/        # 文件上传目录
```

## 安装配置

### 1. 环境要求
- Python 3.8+
- FastAPI 0.104+
- PostgreSQL (可选)

### 2. 依赖安装
```bash
pip install -r requirements.txt
```

### 3. 配置文件
在项目根目录创建`.env`文件，配置以下参数：
```
# API配置
API_HOST=0.0.0.0
API_PORT=8000

# 算法接口配置
ALGORITHM_API_URL=http://algorithm-service:8000/api/v1
ALGORITHM_SERVICE_TOKEN=your-service-token
ALGORITHM_TIMEOUT=60

# 数据库配置（可选）
DATABASE_URL=postgresql://admin:password@localhost:5432/example_db

# 重试配置
RETRY_MAX_COUNT=3
RETRY_INITIAL_DELAY=1

# 上传目录
UPLOAD_DIR=./uploads
```

## 快速启动

### 开发环境启动
```bash
python -m agent.main
```

### Docker部署
```bash
docker-compose up -d
```

## API文档
服务启动后，可访问以下地址查看API文档：
- Swagger UI: http://localhost:8000/api/docs
- OpenAPI Schema: http://localhost:8000/api/openapi.json

## 主要接口

### 1. 文件上传
- URL: `/api/file/upload`
- 方法: POST
- 功能: 上传商业发票文件，启动智能体处理流程
- 返回: process_id用于后续SSE订阅

### 2. SSE事件流
- URL: `/api/agent/stream?process_id={process_id}`
- 方法: GET
- 功能: 订阅任务处理的实时事件流

### 3. 算法回调
- URL: `/api/algorithm/callback`
- 方法: POST
- 功能: 接收算法服务的异步处理结果

### 4. 合规检查
- URL: `/api/compliance/start`
- 方法: POST
- 功能: 手动触发合规检查流程

### 5. 健康检查
- URL: `/api/health`
- 方法: GET
- 功能: 检查服务和数据库连接状态

## 事件类型

系统通过SSE推送以下主要事件类型：

1. 文件上传事件
   - `file.upload.start`
   - `file.upload.complete`

2. 模型调度事件
   - `model.dispatch.start`
   - `model.extract.complete`

3. 工具调用事件
   - `tool.call.start`
   - `tool.call.complete`

4. 合规检查事件
   - `compliance.check.start`
   - `compliance.check.complete`

5. 结果事件
   - `task.complete`
   - `task.error`

## 错误处理

系统定义了完善的错误码体系，主要包括：

- `FILE_TYPE_INVALID`: 文件类型不支持
- `DATA_MISSING`: 数据缺失
- `ALGORITHM_RESULT_MISSING`: 算法结果缺失
- `COMPLIANCE_CHECK_ERROR`: 合规检查错误

## 日志系统

日志文件默认存储在项目根目录的`logs/`文件夹中，日志级别可在配置中调整。每条日志包含：
- process_id: 任务唯一标识
- algorithmTaskId: 算法任务标识
- 时间戳
- 日志级别
- 日志内容

## 注意事项

1. 确保算法服务地址和token配置正确
2. 数据库连接失败不会影响基本的文件处理和SSE推送功能
3. 生产环境部署时建议配置CORS白名单
4. 大文件上传可能需要调整超时配置

## 版本信息

当前版本：1.0.0

## 许可证

保留所有权利