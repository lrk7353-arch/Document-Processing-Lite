-- =============================================
-- 脚本名称: init_v2.sql (修复版)
-- 项目: 非结构化文档智能治理中台
-- 描述: 数据库重构，支持Schema-less存储、向量检索和人工反馈回路
-- =============================================

-- 1. 启用 UUID 生成插件
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. 尝试启用向量扩展 (安全模式)
-- 使用 DO $$ 包裹，防止因缺少插件文件导致整个脚本报错停止
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '警告: 未检测到 pgvector 插件，向量相关功能将暂时跳过。';
END $$;

-- =============================================
-- 核心改造 1: 创建通用的资产表 doc_assets
-- =============================================
CREATE TABLE IF NOT EXISTS doc_assets (
    asset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    process_id VARCHAR(100), -- 关联的任务/流程ID
    doc_type VARCHAR(50) NOT NULL, -- 文档类型: invoice, contract
    
    -- 存储 OCR 识别出的全文
    raw_text TEXT, 
    
    -- 【核心】Schema-less 设计：存储 AI 提取的结构化数据
    structured_data JSONB, 
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 为 JSONB 字段创建 GIN 索引
CREATE INDEX IF NOT EXISTS idx_doc_assets_structured_data ON doc_assets USING GIN (structured_data);

-- 【动态添加向量字段】
-- 只有当 vector 插件成功安装时，才添加这个字段，避免报错
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        -- 检查字段是否已存在，不存在则添加
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='doc_assets' AND column_name='content_embedding') THEN
            ALTER TABLE doc_assets ADD COLUMN content_embedding vector(1536);
        END IF;
    ELSE
        RAISE NOTICE '跳过 content_embedding 字段创建，因为 vector 插件未启用。';
    END IF;
END $$;

-- =============================================
-- 核心改造 2: 增强合规记录 (Traceability)
-- =============================================

-- 如果表不存在则创建
CREATE TABLE IF NOT EXISTS compliance_rule_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID,
    rule_id VARCHAR(50),
    is_passed BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 动态修改表结构：新增快照和风险等级字段
DO $$
BEGIN
    -- 添加 snapshot_data 列
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='compliance_rule_results' AND column_name='snapshot_data') THEN
        ALTER TABLE compliance_rule_results ADD COLUMN snapshot_data JSONB;
    END IF;

    -- 添加 severity 列
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='compliance_rule_results' AND column_name='severity') THEN
        ALTER TABLE compliance_rule_results ADD COLUMN severity VARCHAR(20) DEFAULT 'Low';
    END IF;
END $$;

-- =============================================
-- 核心改造 3: 新增人工反馈表 (Human-in-the-loop)
-- =============================================
CREATE TABLE IF NOT EXISTS human_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID NOT NULL, 
    
    field_key VARCHAR(100) NOT NULL, -- 哪个字段错了
    old_value TEXT, -- AI 的值
    new_value TEXT, -- 人工修正的值
    
    feedback_type VARCHAR(50), -- 错误类型
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_feedback_asset_id ON human_feedback(asset_id);

-- 提示信息
DO $$
BEGIN
    RAISE NOTICE '数据库重构脚本执行完毕！请检查 Messages 窗口是否有警告信息。';
END $$;