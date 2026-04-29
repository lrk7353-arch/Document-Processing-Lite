 DocSmart 智能数据中台开发规范 (v1.0)
文档状态: Draft | 最后更新: 2026-02-10 | 维护人: [Your Name]
1. 项目愿景与架构 (Architecture)
本项目旨在构建一个非结构化数据智能治理中台。不同于传统 ERP，我们专注于将 PDF/图片等“暗数据”转化为可被业务系统利用的“高价值资产”，并提供动态的合规风控能力。
核心分层：
前端 (Frontend): 用户交互、数据可视化、人工审核 (Human-in-the-loop)。
业务后端 (Backend - Port 8000): 任务调度、数据持久化、业务逻辑校验、API 网关。
算法引擎 (Algorithm - Port 8001): OCR 识别 (Tesseract)、LLM 推理、实体提取。
数据层 (Data Layer): PostgreSQL (关系型数据) + VectorDB (知识库/规则库)。
2. 环境部署规范 (Environment Setup)
为避免环境差异导致的“幻觉 Bug”，所有开发与部署环境必须遵循以下标准。
2.1 基础依赖
OS: Windows 10/11 或 Linux (Ubuntu 20.04+)
Python: 3.10.x (严禁使用 3.12+，部分库尚未兼容)
Node.js: v18+ (用于前端构建)
Database: PostgreSQL 15+
2.2 关键系统工具 (System Tools)
必须安装并配置到系统环境变量 PATH 中：
Tesseract OCR 5.0+:
Windows 安装路径建议: C:\Program Files\Tesseract-OCR
必须配置环境变量 TESSDATA_PREFIX 指向 tessdata 目录。
Poppler / pypdfium2:
本项目已迁移至 pypdfium2 (纯 Python 库)，无需手动配置 Poppler 环境变量。
2.3 Python 依赖管理 (Strict)
原则：严禁直接使用 pip，必须使用 python -m pip 以确保路径正确。

Bash


# 初始化虚拟环境
python -m venv .venv

# 激活环境 (Windows)
.\.venv\Scripts\Activate.ps1

# 安装依赖 (后端)
cd Backend
python -m pip install -r requirements.txt

# 补充依赖 (如遇到 OCR 渲染问题)
python -m pip install pypdfium2 aiohttp psycopg2-binary sqlalchemy


3. 数据持久化设计 (Database Schema)
这是本次迭代的核心。我们将从“内存流转”升级为“数据库存储”。
数据库选型: PostgreSQL
ORM 框架: SQLAlchemy (Async)
3.1 核心表结构设计 (ER Diagram Draft)
表 1: 文档主表 (documents)
记录文件的生命周期，用于任务追踪。
字段名
类型
约束
说明
id
UUID
PK
文档唯一标识 (process_id)
filename
Varchar
Not Null
原始文件名
upload_user
Varchar


上传人
status
Varchar
Index
状态 (PENDING, PROCESSING, COMPLETED, FAILED)
risk_level
Varchar
Index
风险等级 (HIGH, MEDIUM, LOW, PASS)
process_time
Float


总耗时 (ms)
created_at
Timestamp


创建时间

表 2: 发票结构化数据表 (invoice_data)
存储 OCR 提取后的“净数据”，用于 BI 分析。
字段名
类型
说明
id
BigInt
PK, Auto Increment
document_id
UUID
FK -> documents.id
invoice_no
Varchar
发票号码
invoice_date
Date
开票日期
amount
Decimal(12,2)
总金额
seller_name
Varchar
销售方名称
buyer_name
Varchar
购买方名称
items_json
JSONB
关键: 存储明细行 (货物名称、单价、数量)

表 3: 合规检查记录表 (compliance_logs)
存储风控结果，用于审计和模型微调。
字段名
类型
说明
id
BigInt
PK
document_id
UUID
FK -> documents.id
rule_id
Varchar
触发的规则 ID (如 DATE_VALID_002)
is_passed
Boolean
是否通过
risk_score
Int
扣分/风险值
description
Text
具体的失败原因 (LLM 生成的解释)

4. 逻辑开发标准 (Coding Standards)
4.1 Pydantic 数据校验 (Schema Evolution)
为了防止 TotalDuration=0 导致的崩溃，所有数据模型必须遵循宽容输入、严格输出原则。
示例规范 (Backend/agent/schemas/task.py):

Python


from pydantic import BaseModel, Field, field_validator

class TaskCompletedData(BaseModel):
    totalDuration: int = Field(..., description="耗时(ms)")

    @field_validator('totalDuration')
    def validate_duration(cls, v):
        # 强制逻辑：如果计算出 0，自动修正为 1，防止前端报错
        return max(1, v)


4.2 异常处理与日志
原则: 业务逻辑层 (Service) 绝不裸奔。必须使用 try-except 包裹，并记录 traceback。
日志: 必须包含 process_id，以便在 Kibana/本地日志文件中追踪单个文件的全链路。
4.3 合规规则引擎 (compliance_service.py)
扩展性: 规则不应写死在代码里。
下一步计划: 将规则配置化（存储在 JSON 或数据库中），例如：
JSON
{
  "rule_id": "AMOUNT_CHECK",
  "expression": "amount > 0 && amount < 1000000",
  "error_msg": "金额超出风控限制"
}


5. 快速启动 (Quick Start)
Step 1: 启动 PostgreSQL
确保本地或 Docker 容器中数据库已运行，并创建数据库 doc_smart_db。
Step 2: 启动算法服务 (Port 8001)

PowerShell


cd Algorithm
# 确保已激活虚拟环境
python server1111.py


Step 3: 启动业务后端 (Port 8000)

PowerShell


cd Backend
# 确保安装了 database 依赖
python -m pip install asyncpg sqlalchemy
uvicorn agent.main:app --host 0.0.0.0 --port 8000 --reload


注意：--reload 模式下，修改代码会自动重启，但若修改环境变量需手动重启。
Step 4: 启动前端 (Port 5173)

PowerShell


cd Frontend
npm run dev


6. 近期迭代路线图 (Roadmap)
[ ] v1.1 (本周): 完成 PostgreSQL 接入，实现发票数据的落库存储。
[ ] v1.2 (下周): 升级合规逻辑，支持“跨单据校验”（如发票 vs 合同）。
[ ] v1.3 (未来): 接入 VectorDB，实现基于自然语言的“智能查数”。
💡 如何使用这份文档？
保存: 在你的项目根目录下新建一个文件 README.md (或 DEV_SPEC.md)，把上面的内容复制进去。
执行: 按照第 5 部分的“快速启动”检查一遍你的流程。
开发: 接下来我们将按照 第 3 部分 (数据库设计) 开始写代码。