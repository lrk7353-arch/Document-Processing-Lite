--
-- PostgreSQL database dump
--

-- Dumped from database version 11.2
-- Dumped by pg_dump version 11.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: algorithm_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.algorithm_tasks (
    algorithm_task_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    process_id character varying(64) NOT NULL,
    model_id character varying(64) NOT NULL,
    model_name character varying(128) NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    start_time timestamp without time zone,
    end_time timestamp without time zone
);


ALTER TABLE public.algorithm_tasks OWNER TO postgres;

--
-- Name: COLUMN algorithm_tasks.algorithm_task_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.algorithm_task_id IS '算法任务唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN algorithm_tasks.process_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.process_id IS '关联任务主表的process_id';


--
-- Name: COLUMN algorithm_tasks.model_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.model_id IS '调用的模型ID';


--
-- Name: COLUMN algorithm_tasks.model_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.model_name IS '模型名称';


--
-- Name: COLUMN algorithm_tasks.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.status IS '模型状态：pending/processing/completed/failed';


--
-- Name: COLUMN algorithm_tasks.start_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.start_time IS '模型调用开始时间';


--
-- Name: COLUMN algorithm_tasks.end_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.algorithm_tasks.end_time IS '模型调用结束时间';


--
-- Name: compliance_rule_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.compliance_rule_results (
    rule_result_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    compliance_task_id character varying(64) NOT NULL,
    rule_id character varying(64) NOT NULL,
    rule_name character varying(128) NOT NULL,
    result character varying(16) NOT NULL,
    reason text,
    checked_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.compliance_rule_results OWNER TO postgres;

--
-- Name: COLUMN compliance_rule_results.rule_result_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.rule_result_id IS '合规规则检查结果唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN compliance_rule_results.compliance_task_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.compliance_task_id IS '关联合规检查任务表的compliance_task_id';


--
-- Name: COLUMN compliance_rule_results.rule_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.rule_id IS '关联规则定义表的rule_id';


--
-- Name: COLUMN compliance_rule_results.rule_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.rule_name IS '规则名称';


--
-- Name: COLUMN compliance_rule_results.result; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.result IS '规则结果：pass/fail';


--
-- Name: COLUMN compliance_rule_results.reason; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.reason IS '失败原因';


--
-- Name: COLUMN compliance_rule_results.checked_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rule_results.checked_at IS '规则检查时间，默认当前时间戳';


--
-- Name: compliance_rules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.compliance_rules (
    rule_id character varying(64) NOT NULL,
    rule_name character varying(128) NOT NULL,
    rule_description text,
    rule_definition jsonb NOT NULL,
    rule_type character varying(64) NOT NULL,
    is_active boolean DEFAULT true,
    version character varying(32) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.compliance_rules OWNER TO postgres;

--
-- Name: COLUMN compliance_rules.rule_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.rule_id IS '合规规则唯一标识，主键';


--
-- Name: COLUMN compliance_rules.rule_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.rule_name IS '规则名称';


--
-- Name: COLUMN compliance_rules.rule_description; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.rule_description IS '规则描述';


--
-- Name: COLUMN compliance_rules.rule_definition; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.rule_definition IS '规则校验逻辑，JSONB格式';


--
-- Name: COLUMN compliance_rules.rule_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.rule_type IS '规则类型：data_validation/logic_validation';


--
-- Name: COLUMN compliance_rules.is_active; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.is_active IS '是否启用，默认true';


--
-- Name: COLUMN compliance_rules.version; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.version IS '规则版本';


--
-- Name: COLUMN compliance_rules.created_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_rules.created_at IS '规则创建时间，默认当前时间戳';


--
-- Name: compliance_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.compliance_tasks (
    compliance_task_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    process_id character varying(64) NOT NULL,
    overall_result character varying(16) NOT NULL,
    status character varying(32) NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone
);


ALTER TABLE public.compliance_tasks OWNER TO postgres;

--
-- Name: COLUMN compliance_tasks.compliance_task_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_tasks.compliance_task_id IS '合规检查任务唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN compliance_tasks.process_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_tasks.process_id IS '关联任务主表的process_id';


--
-- Name: COLUMN compliance_tasks.overall_result; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_tasks.overall_result IS '合规结果：pass/fail';


--
-- Name: COLUMN compliance_tasks.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_tasks.status IS '检查状态：processing/completed/failed';


--
-- Name: COLUMN compliance_tasks.start_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_tasks.start_time IS '合规检查开始时间';


--
-- Name: COLUMN compliance_tasks.end_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.compliance_tasks.end_time IS '合规检查结束时间';


--
-- Name: extracted_fields; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.extracted_fields (
    field_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    algorithm_task_id character varying(64) NOT NULL,
    invoice_no character varying(50),
    invoice_date date,
    buyer_name character varying(100),
    seller_name character varying(100),
    description character varying(100),
    quantity numeric(10,2) NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    total_amount numeric(12,2) NOT NULL,
    confidence numeric(3,2) NOT NULL,
    extracted_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT extracted_fields_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
    CONSTRAINT extracted_fields_quantity_check CHECK ((quantity >= 0.01)),
    CONSTRAINT extracted_fields_total_amount_check CHECK ((total_amount >= 0.01)),
    CONSTRAINT extracted_fields_unit_price_check CHECK ((unit_price >= 0.01))
);


ALTER TABLE public.extracted_fields OWNER TO postgres;

--
-- Name: COLUMN extracted_fields.field_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.field_id IS '字段提取结果唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN extracted_fields.algorithm_task_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.algorithm_task_id IS '关联算法任务表的algorithm_task_id';


--
-- Name: COLUMN extracted_fields.invoice_no; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.invoice_no IS '发票号码';


--
-- Name: COLUMN extracted_fields.invoice_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.invoice_date IS '发票日期';


--
-- Name: COLUMN extracted_fields.buyer_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.buyer_name IS '买方名称';


--
-- Name: COLUMN extracted_fields.seller_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.seller_name IS '卖方名称';


--
-- Name: COLUMN extracted_fields.description; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.description IS '货物描述';


--
-- Name: COLUMN extracted_fields.quantity; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.quantity IS '数量，≥0.01';


--
-- Name: COLUMN extracted_fields.unit_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.unit_price IS '单价，≥0.01';


--
-- Name: COLUMN extracted_fields.total_amount; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.total_amount IS '总金额，≥0.01';


--
-- Name: COLUMN extracted_fields.confidence; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.confidence IS '提取置信度，0-1之间';


--
-- Name: COLUMN extracted_fields.extracted_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.extracted_fields.extracted_at IS '字段提取时间，默认当前时间戳';


--
-- Name: sse_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sse_sessions (
    session_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    process_id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    last_event_id character varying(64),
    connect_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_active_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.sse_sessions OWNER TO postgres;

--
-- Name: COLUMN sse_sessions.session_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sse_sessions.session_id IS 'SSE会话唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN sse_sessions.process_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sse_sessions.process_id IS '关联任务主表的process_id';


--
-- Name: COLUMN sse_sessions.user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sse_sessions.user_id IS '会话所属用户ID';


--
-- Name: COLUMN sse_sessions.last_event_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sse_sessions.last_event_id IS '最后推送事件ID，用于断点续传';


--
-- Name: COLUMN sse_sessions.connect_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sse_sessions.connect_time IS '会话建立时间，默认当前时间戳';


--
-- Name: COLUMN sse_sessions.last_active_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sse_sessions.last_active_time IS '最后活跃时间，用于清理过期会话';


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tasks (
    process_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    file_id character varying(64) NOT NULL,
    file_name character varying(255) NOT NULL,
    file_path character varying(512) NOT NULL,
    agent_state character varying(32) DEFAULT 'init'::character varying NOT NULL,
    total_progress integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.tasks OWNER TO postgres;

--
-- Name: COLUMN tasks.process_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.process_id IS '任务唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN tasks.file_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.file_id IS '文件唯一标识';


--
-- Name: COLUMN tasks.file_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.file_name IS '原始文件名';


--
-- Name: COLUMN tasks.file_path; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.file_path IS '文件存储路径';


--
-- Name: COLUMN tasks.agent_state; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.agent_state IS '智能体状态：init/uploading/parsing/extracting/checking/completed/failed';


--
-- Name: COLUMN tasks.total_progress; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.total_progress IS '处理进度(0-100)';


--
-- Name: COLUMN tasks.created_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.created_at IS '任务创建时间，默认当前时间戳';


--
-- Name: COLUMN tasks.updated_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.tasks.updated_at IS '任务更新时间，默认当前时间戳';


--
-- Name: user_actions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_actions (
    action_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    process_id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    action_type character varying(64) NOT NULL,
    action_data jsonb NOT NULL,
    action_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.user_actions OWNER TO postgres;

--
-- Name: COLUMN user_actions.action_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_actions.action_id IS '用户操作唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN user_actions.process_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_actions.process_id IS '关联任务主表的process_id';


--
-- Name: COLUMN user_actions.user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_actions.user_id IS '操作用户ID';


--
-- Name: COLUMN user_actions.action_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_actions.action_type IS '操作类型：confirm/modify/reupload';


--
-- Name: COLUMN user_actions.action_data; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_actions.action_data IS '操作详情，JSONB格式';


--
-- Name: COLUMN user_actions.action_time; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.user_actions.action_time IS '操作时间，默认当前时间戳';


--
-- Name: validation_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.validation_results (
    validation_id character varying(64) DEFAULT public.gen_random_uuid() NOT NULL,
    algorithm_task_id character varying(64) NOT NULL,
    validation_status character varying(32) NOT NULL,
    failed_rules jsonb,
    warnings jsonb,
    validated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.validation_results OWNER TO postgres;

--
-- Name: COLUMN validation_results.validation_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.validation_results.validation_id IS '校验结果唯一标识，主键，自动生成UUID';


--
-- Name: COLUMN validation_results.algorithm_task_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.validation_results.algorithm_task_id IS '关联算法任务表的algorithm_task_id';


--
-- Name: COLUMN validation_results.validation_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.validation_results.validation_status IS '校验状态：passed/warning/failed';


--
-- Name: COLUMN validation_results.failed_rules; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.validation_results.failed_rules IS '失败规则列表，JSONB格式';


--
-- Name: COLUMN validation_results.warnings; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.validation_results.warnings IS '警告信息列表，JSONB格式';


--
-- Name: COLUMN validation_results.validated_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.validation_results.validated_at IS '校验时间，默认当前时间戳';


--
-- Data for Name: algorithm_tasks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.algorithm_tasks (algorithm_task_id, process_id, model_id, model_name, status, start_time, end_time) FROM stdin;
5cfe6fd1-7843-4d9c-8cff-5ad7c40693ed	ee437046-e2b0-4274-afe5-a80c0afd3915	model_001	测试模型	pending	\N	\N
\.


--
-- Data for Name: compliance_rule_results; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.compliance_rule_results (rule_result_id, compliance_task_id, rule_id, rule_name, result, reason, checked_at) FROM stdin;
\.


--
-- Data for Name: compliance_rules; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.compliance_rules (rule_id, rule_name, rule_description, rule_definition, rule_type, is_active, version, created_at) FROM stdin;
INV-001	invoice_no_format	发票号码仅允许大写字母、数字、-、_，且不重复	{"regex": "^[A-Z0-9\\\\-_]+$", "max_length": 50, "unique_check": true}	data_validation	t	v1.0	2025-11-06 16:23:51.777329
INV-002	invoice_date_valid	日期需在1900年至未来1年之间，格式为YYYY-MM-DD	{"format": "YYYY-MM-DD", "min_year": 1900, "max_future_days": 365}	data_validation	t	v1.0	2025-11-06 16:23:51.777329
INV-003	buyer_seller_valid	名称长度≤100，无非法字符，且买方≠卖方	{"not_equal": true, "max_length": 100, "prohibited_chars": ["!", "?", "\\\\n"]}	data_validation	t	v1.0	2025-11-06 16:23:51.777329
INV-004	description_valid	描述长度≤100，无非法字符	{"max_length": 100, "prohibited_chars": ["!", "?", "\\\\n"]}	data_validation	t	v1.0	2025-11-06 16:23:51.777329
INV-005	quantity_range	数量≥0.01，超100万提示警告	{"min_value": 0.01, "warning_threshold": 1000000}	data_validation	t	v1.0	2025-11-06 16:23:51.777329
INV-006	amount_precision	单价/总金额≥0.01，小数位≤2位	{"min_value": 0.01, "max_decimal": 2}	data_validation	t	v1.0	2025-11-06 16:23:51.777329
INV-007	total_amount_logic	总金额需等于数量×单价（允许±0.01误差）	{"tolerance": 0.01}	logic_validation	t	v1.0	2025-11-06 16:23:51.777329
\.


--
-- Data for Name: compliance_tasks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.compliance_tasks (compliance_task_id, process_id, overall_result, status, start_time, end_time) FROM stdin;
\.


--
-- Data for Name: extracted_fields; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.extracted_fields (field_id, algorithm_task_id, invoice_no, invoice_date, buyer_name, seller_name, description, quantity, unit_price, total_amount, confidence, extracted_at) FROM stdin;
\.


--
-- Data for Name: sse_sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sse_sessions (session_id, process_id, user_id, last_event_id, connect_time, last_active_time) FROM stdin;
\.


--
-- Data for Name: tasks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tasks (process_id, file_id, file_name, file_path, agent_state, total_progress, created_at, updated_at) FROM stdin;
ee437046-e2b0-4274-afe5-a80c0afd3915	test_file_001	测试发票.pdf	/test/path/001.pdf	init	0	2025-11-06 18:26:49.414861	2025-11-06 18:26:49.414861
\.


--
-- Data for Name: user_actions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_actions (action_id, process_id, user_id, action_type, action_data, action_time) FROM stdin;
\.


--
-- Data for Name: validation_results; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.validation_results (validation_id, algorithm_task_id, validation_status, failed_rules, warnings, validated_at) FROM stdin;
b8e8bc3b-9f5d-4f93-9c5c-1a721764f85b	5cfe6fd1-7843-4d9c-8cff-5ad7c40693ed	failed	["INV-001", "INV-003"]	\N	2025-11-06 18:29:54.408902
\.


--
-- Name: algorithm_tasks algorithm_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.algorithm_tasks
    ADD CONSTRAINT algorithm_tasks_pkey PRIMARY KEY (algorithm_task_id);


--
-- Name: compliance_rule_results compliance_rule_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_rule_results
    ADD CONSTRAINT compliance_rule_results_pkey PRIMARY KEY (rule_result_id);


--
-- Name: compliance_rules compliance_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_rules
    ADD CONSTRAINT compliance_rules_pkey PRIMARY KEY (rule_id);


--
-- Name: compliance_tasks compliance_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_tasks
    ADD CONSTRAINT compliance_tasks_pkey PRIMARY KEY (compliance_task_id);


--
-- Name: extracted_fields extracted_fields_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.extracted_fields
    ADD CONSTRAINT extracted_fields_pkey PRIMARY KEY (field_id);


--
-- Name: sse_sessions sse_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sse_sessions
    ADD CONSTRAINT sse_sessions_pkey PRIMARY KEY (session_id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (process_id);


--
-- Name: user_actions user_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_actions
    ADD CONSTRAINT user_actions_pkey PRIMARY KEY (action_id);


--
-- Name: validation_results validation_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.validation_results
    ADD CONSTRAINT validation_results_pkey PRIMARY KEY (validation_id);


--
-- Name: idx_algorithm_tasks_process_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_algorithm_tasks_process_id ON public.algorithm_tasks USING btree (process_id);


--
-- Name: idx_algorithm_tasks_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_algorithm_tasks_status ON public.algorithm_tasks USING btree (status);


--
-- Name: idx_compliance_rule_results_rule_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_compliance_rule_results_rule_id ON public.compliance_rule_results USING btree (rule_id);


--
-- Name: idx_compliance_tasks_process_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_compliance_tasks_process_id ON public.compliance_tasks USING btree (process_id);


--
-- Name: idx_extracted_fields_algorithm_task_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_extracted_fields_algorithm_task_id ON public.extracted_fields USING btree (algorithm_task_id);


--
-- Name: idx_extracted_fields_invoice_no; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_extracted_fields_invoice_no ON public.extracted_fields USING btree (invoice_no);


--
-- Name: idx_sse_sessions_last_active_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sse_sessions_last_active_time ON public.sse_sessions USING btree (last_active_time);


--
-- Name: idx_tasks_agent_state; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tasks_agent_state ON public.tasks USING btree (agent_state);


--
-- Name: idx_tasks_file_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tasks_file_id ON public.tasks USING btree (file_id);


--
-- Name: idx_tasks_process_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tasks_process_id ON public.tasks USING btree (process_id);


--
-- Name: idx_user_actions_process_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_actions_process_id ON public.user_actions USING btree (process_id);


--
-- Name: algorithm_tasks algorithm_tasks_process_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.algorithm_tasks
    ADD CONSTRAINT algorithm_tasks_process_id_fkey FOREIGN KEY (process_id) REFERENCES public.tasks(process_id) ON DELETE CASCADE;


--
-- Name: compliance_rule_results compliance_rule_results_compliance_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_rule_results
    ADD CONSTRAINT compliance_rule_results_compliance_task_id_fkey FOREIGN KEY (compliance_task_id) REFERENCES public.compliance_tasks(compliance_task_id) ON DELETE CASCADE;


--
-- Name: compliance_tasks compliance_tasks_process_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.compliance_tasks
    ADD CONSTRAINT compliance_tasks_process_id_fkey FOREIGN KEY (process_id) REFERENCES public.tasks(process_id) ON DELETE CASCADE;


--
-- Name: extracted_fields extracted_fields_algorithm_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.extracted_fields
    ADD CONSTRAINT extracted_fields_algorithm_task_id_fkey FOREIGN KEY (algorithm_task_id) REFERENCES public.algorithm_tasks(algorithm_task_id) ON DELETE CASCADE;


--
-- Name: sse_sessions sse_sessions_process_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sse_sessions
    ADD CONSTRAINT sse_sessions_process_id_fkey FOREIGN KEY (process_id) REFERENCES public.tasks(process_id) ON DELETE CASCADE;


--
-- Name: user_actions user_actions_process_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_actions
    ADD CONSTRAINT user_actions_process_id_fkey FOREIGN KEY (process_id) REFERENCES public.tasks(process_id) ON DELETE CASCADE;


--
-- Name: validation_results validation_results_algorithm_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.validation_results
    ADD CONSTRAINT validation_results_algorithm_task_id_fkey FOREIGN KEY (algorithm_task_id) REFERENCES public.algorithm_tasks(algorithm_task_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

