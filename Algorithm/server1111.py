# -*- coding: utf-8 -*-
"""
==========================================================
📘 文件名: server1111.py
📌 功能: FastAPI 服务 - 发票智能算法服务 (模型推理 + 逻辑校验)
📍 模型路径: ./model_6_focus
📍 规则路径: ./rule_config.json
📍 对接契约: 算法接口对接 v2（含逻辑校验工具）
==========================================================
"""
import os
import time
import json
from typing import Dict, Any, List, Optional

import uvicorn
import pandas as pd
import torch
import pytesseract
import httpx
import re
from pdf2image import convert_from_path
try:
    import pypdfium2 as pdfium
except Exception:
    pdfium = None
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from transformers import AutoProcessor, AutoModelForTokenClassification

from invoice_validator_with_rules_Version1 import RuleEngine



# ==========================================================
# 🌱 环境配置 & 路径
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
RULE_PATH = os.path.join(BASE_DIR, "rule_config.json")
METRIC_LOG_PATH = os.path.join(BASE_DIR, "training_metrics.csv")

API_TOKEN = ""  # 如需鉴权，可在 .env 中配置 SERVICE_TOKEN / API_TOKEN
MODEL_PATH = os.path.join(BASE_DIR, "model_6_focus")

DEVICE = torch.device("cpu")

processor, model = None, None

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"✅ 已加载环境配置: {ENV_PATH}")
else:
    print("⚠️ 未找到 .env 文件，使用默认环境配置")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8001))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# 回调时也带上服务令牌（与文档保持一致）
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", API_TOKEN or "")

tesseract_cmd_env = os.getenv("TESSERACT_CMD")
if tesseract_cmd_env:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_env
else:
    default_cmd = r"D:\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_cmd):
        pytesseract.pytesseract.tesseract_cmd = default_cmd

# ==========================================================
# ⚙️ 加载规则配置
# ==========================================================
def load_rules() -> Dict[str, Any]:
    if not os.path.exists(RULE_PATH):
        raise FileNotFoundError(f"未找到规则文件: {RULE_PATH}")
    with open(RULE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


rules_data: Dict[str, Any] = {}
rule_engine: Optional[RuleEngine] = None

try:
    rules_data = load_rules()
    rule_engine = RuleEngine(rules_data)
    print(f"✅ 已加载规则配置文件: {RULE_PATH}")
except Exception as e:
    rule_engine = None
    print(f"❌ 加载规则失败: {e}")

# ==========================================================
# 🧮 金额字段规范化工具
# ==========================================================
def normalize_amount_value(text: Optional[str]) -> str:
    """
    将金额相关字符串规范化为纯数字字符串:
    - 去掉百分号 %
    - 去掉常见货币符号（$ / ¥ / ￥ / €）
    - 处理千分位和小数分隔符（兼容 212,09 / 1,234.56）
    """
    if text is None:
        return ""

    s = str(text).strip()
    if not s:
        return s

    s = s.replace("%", "")
    for sym in ["$", "￥", "¥", "€"]:
        s = s.replace(sym, "")

    s = s.replace(" ", "")

    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")

    s = re.sub(r"[^\d.\-]", "", s)

    try:
        value = float(s)
        return f"{value:.2f}"
    except Exception:
        return s

def detect_currency_symbol(words: List[str]) -> Optional[str]:
    """
    从 OCR 的 words 里尝试识别货币符号：
    优先返回 $, 其次 €, 再次 ¥/￥。
    如需扩展可以加 USD/EUR/RMB 等代码判断。
    """
    joined = " ".join(words)

    # 先看符号
    if "$" in joined:
        return "$"
    if "€" in joined:
        return "€"
    if "￥" in joined or "¥" in joined:
        return "¥"

    # 再简单看一下常见货币代码
    upper = joined.upper()
    if "USD" in upper:
        return "$"
    if "EUR" in upper:
        return "€"
    if "CNY" in upper or "RMB" in upper:
        return "¥"

    return None


# ==========================================================
# 🧠 加载本地 LayoutLMv3 模型
# ==========================================================
def load_model():
    global processor, model
    try:
        print(f"🔍 正在加载模型: {MODEL_PATH}")
        processor = AutoProcessor.from_pretrained(MODEL_PATH)
        model = AutoModelForTokenClassification.from_pretrained(MODEL_PATH)
        model.to(DEVICE)
        model.eval()
        print("✅ 模型加载完成")
    except Exception as e:
        processor, model = None, None
        print(f"❌ 模型加载失败: {e}")


# ==========================================================
# 📦 回调与校验相关数据模型（对齐文档结构）
# ==========================================================
class ValidationRuleResult(BaseModel):
    """单条校验规则执行结果"""
    ruleId: str
    ruleName: str
    field: str
    errorMsg: Optional[str] = None


class ValidationResult(BaseModel):
    """整体校验结果"""
    validationStatus: str  # "passed" / "failed" / "skipped"
    ruleVersion: str
    validationTime: int
    failedRules: Optional[List[ValidationRuleResult]] = None


class AlgorithmInitialResponse(BaseModel):
    """算法服务同步返回给业务后端的初始响应"""
    code: int
    message: str
    algorithmTaskId: str
    status: str                 # "pending" / "running" / "accepted"
    validationTaskStatus: Optional[str] = None  # "pending_validation" 等
    estimatedTime: Optional[int] = None         # 预估总耗时（秒）


# ==========================================================
# 🔁 LayoutLM 结果 → extractedFields
# ==========================================================
def extract_party_names_from_words(words: List[str]) -> tuple[Optional[str], Optional[str]]:
    """
    从 OCR 的 words 里，按“Seller: … / Client: …”模式，提取：
    - seller_name（比如 Juarez PLC）
    - client_name（比如 Peters-Santiago）
    """
    text = " ".join(words)

    seller_name: Optional[str] = None
    client_name: Optional[str] = None

    # 1) Seller: 后面一般是 “Juarez PLC” 这种 “若干词 + 公司后缀”
    seller_pattern = re.compile(
        r"Seller\s*:?\s*"
        r"([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\s+"
        r"(?:PLC|LLC|Ltd|Limited|Inc\.?|GmbH|S\.A\.?))"
    )
    m_seller = seller_pattern.search(text)
    if m_seller:
        seller_name = m_seller.group(1).strip()

    # 2) Client: 后面一般是 “Peters-Santiago” 或一个/两个词的名字
    client_pattern = re.compile(
        r"Client\s*:?\s*"
        r"([A-Z][A-Za-z]*(?:[-\s][A-Z][A-Za-z]*)?)"
    )
    m_client = client_pattern.search(text)
    if m_client:
        client_name = m_client.group(1).strip()

    return seller_name, client_name




def map_entities_to_fields(
    entities: Dict[str, str],
    currency_symbol: Optional[str] = None,
) -> List[Dict[str, Any]]:

    """
    把 LayoutLM 抽出来的实体字典，转成 extractedFields 列表；
    在这里做一层“发票专用”的后处理：
    - 从 INVOICE_DATE 里抽出真正的日期 + 发票号
    - 从 TOTAL_AMOUNT 里抽出总金额
    - 从 BUYER 里尽量抽出一个干净的买方名称
    """
    type_to_field = {
        "INVOICE_NO": "invoiceNo",
        "INVOICE_DATE": "issueDate",
        "SELLER": "sellerName",
        "BUYER": "buyerName",
        "DESCRIPTION": "goodsDesc",
        "QUANTITY": "quantity",
        "UNIT_PRICE": "unitPrice",
        "TOTAL_AMOUNT": "amount",
    }

    # 复制一份，避免直接改入参
    ents = dict(entities)

    # ---- 1）从 INVOICE_DATE 里抽日期 + 发票号 ----
    date_text = ents.get("INVOICE_DATE")
    if isinstance(date_text, str):
        # 日期：优先匹配 09/09/2015 或 2015-09-09 这种
        m_date = re.search(r"\d{2}/\d{2}/\d{4}", date_text)
        if not m_date:
            m_date = re.search(r"\d{4}-\d{2}-\d{2}", date_text)
        if m_date:
            ents["INVOICE_DATE"] = m_date.group(0)

        # 发票号：取里面第一个“长度>=6 的纯数字串”
        m_inv = re.findall(r"\b\d{6,}\b", date_text)
        if m_inv:
            ents["INVOICE_NO"] = m_inv[0]

    # ---- 2）从 TOTAL_AMOUNT 里抽总金额（最后一个金额）----
    tot_text = ents.get("TOTAL_AMOUNT")
    if isinstance(tot_text, str):
        # 匹配 193,02 / 193.02 这种格式
        matches = re.findall(r"\d+[.,]\d{2}", tot_text)
        if matches:
            ents["TOTAL_AMOUNT"] = matches[-1]

    # ---- 3）从 BUYER 里抽一个“像样的名字” ----
       # ---- 3）从 BUYER 里抽一个“像样的名字” ----
    buyer_text = ents.get("BUYER")
    if isinstance(buyer_text, str):
        clean = buyer_text

        # 3.1 先在 ITEMS 前截断（有些发票会在后面接 ITEMS 之类的单词）
        if "ITEMS" in clean:
            clean = clean.split("ITEMS", 1)[0]

        # 3.2 在第一个数字出现之前截断（把电话、账号之类的全砍掉）
        m_digit = re.search(r"\d", clean)
        if m_digit:
            clean = clean[: m_digit.start()]

        # 3.3 去掉结尾标点和多余空格
        clean = clean.strip().rstrip(",; ")

        # 3.4 再按“公司名 + 地址”切一刀，尽量只保留名字部分
        if clean:
            parts = clean.split()

            address_keywords = {
                "Street", "St",
                "Road", "Rd",
                "Avenue", "Ave",
                "Lane", "Ln",
                "Way",
                "Throughway",
                "Drive", "Dr",
                "Boulevard", "Blvd",
                "Court", "Ct",
                "Place", "Pl",
                "Square", "Sq",
            }

            trimmed_parts: List[str] = []
            for p in parts:
                # 碰到明显地址词或以 -shire 结尾的地名，就停
                if p in address_keywords or p.lower().endswith("shire"):
                    break
                trimmed_parts.append(p)

            # 特殊处理：类似 "PLC Peters-Santiago"，
            # 把开头多余的 PLC 去掉，留下人/公司名
            if trimmed_parts and trimmed_parts[0] == "PLC" and len(trimmed_parts) >= 2:
                trimmed_parts = trimmed_parts[1:]

            if trimmed_parts:
                clean = " ".join(trimmed_parts)

        # 避免清洗过头变成空串
        if clean:
            ents["BUYER"] = clean


    # ---- 4）组装成 extractedFields 列表 ----
    out: List[Dict[str, Any]] = []

    for etype, raw_text in ents.items():
        field_name = type_to_field.get(etype)
        if not field_name:
            continue

        val = raw_text.strip() if isinstance(raw_text, str) else raw_text

        # 默认展示值
        display_val = val

        # ✅ 对 amount 做显示层处理：前面加“识别到的货币符号”
        if field_name == "amount" and isinstance(display_val, str) and currency_symbol:
            if not display_val.lstrip().startswith(currency_symbol):
                display_val = f"{currency_symbol} {display_val}"

        entry: Dict[str, Any] = {
            "fieldName": field_name,
            "fieldType": etype,
            "fieldValue": display_val,   # 用 display_val
            "confidence": 0.85,
        }

        # 数值类字段额外提供 numericValue，方便规则和后端逻辑用
        if etype in ("TOTAL_AMOUNT", "UNIT_PRICE", "QUANTITY") or "amount" in field_name.lower():
            entry["numericValue"] = normalize_amount_value(val)

        out.append(entry)


    return out


# ==========================================================
# 🧾 将 extractedFields 映射为规则引擎输入格式
# ==========================================================
def build_raw_invoice_for_rules(extracted_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    将 extractedFields 转成 RuleEngine 需要的字段结构：
    invoice_no / date / buyer_name / seller_name / description / quantity / unit_price / total_amount
    """
    name_map = {
        "invoiceNo": "invoice_no",
        "issueDate": "date",
        "buyerName": "buyer_name",
        "sellerName": "seller_name",
        "goodsDesc": "description",
        "quantity": "quantity",
        "unitPrice": "unit_price",
        "amount": "total_amount",
    }

    raw: Dict[str, Any] = {}

    for f in extracted_fields:
        fname = f.get("fieldName")
        key = name_map.get(fname)
        if not key:
            continue

        if key in ("quantity", "unit_price", "total_amount"):
            val = f.get("numericValue") or f.get("fieldValue")
        else:
            val = f.get("fieldValue")

        raw[key] = val

    return raw


def run_validation_if_needed(
    extracted_fields: List[Dict[str, Any]],
    validation_params: Dict[str, Any],
) -> Optional[ValidationResult]:
    """
    根据 validationParams 决定是否调用规则引擎。
    这里先做“全量规则 + 汇总错误”的版本：
      - validationStatus: passed / failed
      - failedRules: 只有一条“汇总规则”
    如果后续需要精细到每条 ruleId，再一起扩。
    """
    if not rule_engine:
        print("⚠️ 未加载规则引擎，跳过逻辑校验")
        return None

    need_flag = validation_params.get("needValidation")
    if need_flag is False:
        # 显式关闭才跳过
        return None

    # 将提取出的字段转成规则引擎的输入
    raw_invoice = build_raw_invoice_for_rules(extracted_fields)

    # 当前在线版本：不做历史库 / 文件内去重（都传空集合）
    result = rule_engine.apply_rules(raw_invoice, history_set=set(), seen_in_file=set())
    passed = bool(result.get("passed", True))
    errors: List[str] = result.get("errors", [])

    status = "passed" if passed else "failed"
    rule_version = validation_params.get("ruleVersion") or "v1.0"

    failed_rules: Optional[List[ValidationRuleResult]] = None
    if not passed:
        # 简单汇总成一条规则（后续可细化）
        msg = "；".join(errors) if errors else "逻辑校验失败"
        failed_rules = [
            ValidationRuleResult(
                ruleId="INVOICE_RULE_ENGINE",
                ruleName="发票逻辑规则集",
                field="ALL",
                errorMsg=msg,
            )
        ]

    vr = ValidationResult(
        validationStatus=status,
        ruleVersion=rule_version,
        validationTime=int(time.time() * 1000),
        failedRules=failed_rules,
    )
    return vr


# ==========================================================
# 🚀 初始化 FastAPI 应用
# ==========================================================
app = FastAPI(
    title="Invoice Algorithm Service",
    version="3.0.0",
    description="LayoutLMv3 模型推理 + 发票规则校验 + 指标分析",
)


@app.on_event("startup")
async def startup_event():
    """服务启动时加载模型"""
    load_model()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# 🩺 健康检查
# ==========================================================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Invoice model service is running"}


# ==========================================================
# 🧩 OCR 工具：Tesseract + bbox 归一化
# ==========================================================
def ocr_words_boxes(image: Image.Image):
    try:
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            lang="chi_sim+eng",
        )
    except Exception:
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            lang="eng",
        )

    words: List[str] = []
    boxes: List[List[int]] = []
    width, height = image.size

    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        x0_px, y0_px = x, y
        x1_px, y1_px = x + w, y + h

        if width == 0 or height == 0:
            continue

        x0 = int(x0_px / width * 1000)
        x1 = int(x1_px / width * 1000)
        y0 = int(y0_px / height * 1000)
        y1 = int(y1_px / height * 1000)

        x0 = max(0, min(1000, x0))
        x1 = max(0, min(1000, x1))
        y0 = max(0, min(1000, y0))
        y1 = max(0, min(1000, y1))

        if x1 <= x0:
            x1 = min(1000, x0 + 1)
        if y1 <= y0:
            y1 = min(1000, y0 + 1)

        box = [x0, y0, x1, y1]

        words.append(text)
        boxes.append(box)

    return words, boxes

# ==========================================================
# 🧾 ITEMS 表：从 OCR 里直接解析多行行项目
# ==========================================================
import re as _re_local  # 防止和上面的 re 混淆，用同一个也行

def _group_lines_by_y(words: List[str], boxes: List[List[int]], y_thr: int = 8) -> List[List[int]]:
    """按 y 中线聚类，把 token 分成一行一行（返回的是索引列表）"""
    idxs = list(range(len(words)))
    idxs.sort(key=lambda i: ((boxes[i][1] + boxes[i][3]) // 2))

    lines: List[List[int]] = []
    cur: List[int] = []
    last_y = None

    for i in idxs:
        cy = (boxes[i][1] + boxes[i][3]) // 2
        if last_y is None or abs(cy - last_y) <= y_thr:
            cur.append(i)
        else:
            if cur:
                lines.append(cur)
            cur = [i]
        last_y = cy

    if cur:
        lines.append(cur)
    return lines


def _find_items_header_line(words: List[str], lines: List[List[int]]) -> tuple[int, dict]:
    """
    找到包含 Description / Qty / UM 字样的那一行，
    同时记录每一列表头 token 的索引。
    """
    header_keywords = {
        "DESC": ["description"],
        "QTY": ["qty", "quantity"],
        "UM": ["um", "unit"],
    }

    header_line_idx = -1
    header_cols: Dict[str, int] = {}

    for li, line in enumerate(lines):
        texts = [words[i].lower() for i in line]
        joined = " ".join(texts)

        # 粗筛：这一行至少要有 description / qty / um 里的两个
        hit = {
            key: any(k in joined for k in kws)
            for key, kws in header_keywords.items()
        }
        if sum(hit.values()) < 2:
            continue

        col_idx: Dict[str, int] = {}
        for key, kws in header_keywords.items():
            for i in line:
                t = words[i].lower()
                if any(k == t or k in t for k in kws):
                    col_idx[key] = i
                    break

        if "DESC" in col_idx and "QTY" in col_idx:
            header_line_idx = li
            header_cols = col_idx
            break

    return header_line_idx, header_cols


def extract_line_items_from_ocr(words: List[str], boxes: List[List[int]]) -> List[Dict[str, Any]]:
    """
    只用 OCR 结果抽 ITEMS 表里的多行。
    支持 Description 跨多行：
    - 上面若有若干只含描述、不含数量/金额的行，会和当前这一行拼成完整描述。
    返回每行一个 dict: {description, qty, um, net_price, net_worth, vat, gross_worth}
    抽不到的字段就是 None。
    """
    if not words or not boxes:
        return []

    # 1. 按 y 聚类成多行
    lines = _group_lines_by_y(words, boxes, y_thr=8)

    # 2. 找表头所在行 & 各列表头 token
    header_line_idx, header_cols = _find_items_header_line(words, lines)
    if header_line_idx < 0 or not header_cols:
        return []  # 没找到 ITEMS 表

    def cx(idx: int) -> int:
        b = boxes[idx]
        return (b[0] + b[2]) // 2

    # 三个关键列的 x 中心
    desc_x = cx(header_cols["DESC"])
    qty_x = cx(header_cols["QTY"])
    um_x = cx(header_cols.get("UM", header_cols["QTY"]))

    # 额外几列（Net price / Net worth / VAT / Gross worth）
    extra_cols = ["NET_PRICE", "NET_WORTH", "VAT", "GROSS_WORTH"]
    extra_header_idxs = [i for i in lines[header_line_idx] if cx(i) > um_x + 5]
    extra_header_idxs.sort(key=cx)
    extra_col_x = {name: cx(idx) for name, idx in zip(extra_cols, extra_header_idxs)}

    # 列范围（简单按 x 划区）
    col_xs = {
        "DESC_LEFT": desc_x - 9999,
        "DESC_RIGHT": qty_x - 5,
        "QTY_LEFT": qty_x - 5,
        "QTY_RIGHT": um_x - 5,
        "UM_LEFT": um_x - 5,
        "UM_RIGHT": (cx(extra_header_idxs[0]) - 5) if extra_header_idxs else um_x + 9999,
    }

    items: List[Dict[str, Any]] = []

    # 用来累积“只含描述”的多行
    pending_desc_tokens: List[str] = []

    # 3. 从表头下一行往下解析
    for li in range(header_line_idx + 1, len(lines)):
        line = lines[li]
        line_words = [words[i] for i in line]
        lower_text = " ".join(w.lower() for w in line_words)

        # summary / total 行：到此为止
        if "summary" in lower_text or "total" in lower_text:
            break
        # 空白行：跳过但不清空 pending
        if not any(re.search(r"\w", w) for w in line_words):
            continue

        # 按列切一遍
        desc_tokens_line, qty_tokens_line, um_tokens_line = [], [], []
        extras_tokens_line = {k: [] for k in extra_cols}

        for idx in line:
            x = cx(idx)
            t = words[idx]

            if col_xs["DESC_LEFT"] <= x <= col_xs["DESC_RIGHT"]:
                desc_tokens_line.append(t)
            elif col_xs["QTY_LEFT"] <= x <= col_xs["QTY_RIGHT"]:
                qty_tokens_line.append(t)
            elif col_xs["UM_LEFT"] <= x <= col_xs["UM_RIGHT"]:
                um_tokens_line.append(t)
            else:
                for name, ex in extra_col_x.items():
                    if abs(x - ex) < 40:  # 粗略窗口
                        extras_tokens_line[name].append(t)
                        break

        # 判定这一行是不是“主行”（真正有数量/金额）
        has_qty_or_amount = (
            bool(qty_tokens_line)
            or bool(extras_tokens_line["NET_PRICE"])
            or bool(extras_tokens_line["NET_WORTH"])
            or bool(extras_tokens_line["GROSS_WORTH"])
        )

        # ✨ 3.1 如果不是主行，只含描述 → 先累积到 pending 里
        if not has_qty_or_amount:
            if desc_tokens_line:
                pending_desc_tokens.extend(desc_tokens_line)
            # 既没数量也没描述的行，可以忽略
            continue

        # ✨ 3.2 是主行：把“上面攒的描述 + 当前行描述”一起当成这一条的 description
        full_desc_tokens: List[str] = []
        if pending_desc_tokens:
            full_desc_tokens.extend(pending_desc_tokens)
        if desc_tokens_line:
            full_desc_tokens.extend(desc_tokens_line)
        # 用完清空，为下一条 item 做准备
        pending_desc_tokens = []

        # 若 description 也完全没有，说明这行本身就是某种怪格式，可以直接跳过
        if not full_desc_tokens and not qty_tokens_line:
            continue

        join = lambda ts: " ".join(ts).strip() if ts else None

        row = {
            "description": join(full_desc_tokens),
            "qty": join(qty_tokens_line),
            "um": join(um_tokens_line),
            "net_price": join(extras_tokens_line["NET_PRICE"]),
            "net_worth": join(extras_tokens_line["NET_WORTH"]),
            "vat": join(extras_tokens_line["VAT"]),
            "gross_worth": join(extras_tokens_line["GROSS_WORTH"]),
        }

        items.append(row)

    return items



# ==========================================================
# 🧩 LayoutLM 推理：PDF → extractedFields
# ==========================================================
def _load_first_page_image(pdf_path: str) -> Image.Image:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    try:
        pages = convert_from_path(pdf_path)
        if not pages:
            raise ValueError("PDF 中没有页面")
        return pages[0]
    except Exception as e:
        if pdfium is None:
            raise RuntimeError("PDF 渲染失败且未安装 pypdfium2，请安装或配置 Poppler") from e
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            page = pdf.get_page(0)
            bitmap = page.render(scale=2).to_pil()
            page.close()
            pdf.close()
            return bitmap
        except Exception as e2:
            raise RuntimeError(f"PDF 渲染失败: {e2}")

def extract_fields_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    if processor is None or model is None:
        raise RuntimeError("模型尚未加载，请检查 startup_event 中的 load_model 是否正常")

    image = _load_first_page_image(pdf_path)
    print(f"📄 PDF 转图片成功，使用第 1 页进行识别")

    words, boxes = ocr_words_boxes(image)
    if not words:
        raise ValueError("OCR 未识别到任何文本")

    print(f"🔍 OCR 识别到 {len(words)} 个词")
    # 2.1 先用规则从 OCR 里解析 ITEMS 表的多行
    line_items = extract_line_items_from_ocr(words, boxes)
    if line_items:
        print(f"🧾 解析出 {len(line_items)} 条行项目")
        for idx, it in enumerate(line_items, start=1):
            print(f"   第{idx}行: {it}")
    else:
        print("🧾 未解析出 ITEMS 行项目")

      # 👇 新增：识别货币符号
    currency_symbol = detect_currency_symbol(words)

    encoding = processor(
        images=image,
        text=words,
        boxes=boxes,
        truncation=True,
        padding="max_length",
        return_tensors="pt",
    )

    word_ids = encoding.word_ids(batch_index=0)
    inputs = {k: v.to(DEVICE) for k, v in encoding.items() if hasattr(v, "to")}

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predictions = torch.argmax(logits, dim=-1)[0].cpu().tolist()

    id2label = model.config.id2label

    entities: Dict[str, str] = {}
    used = set()

    for token_idx, word_idx in enumerate(word_ids):
        if word_idx is None:
            continue

        label = id2label[predictions[token_idx]]
        if label == "O":
            continue

        if "-" in label:
            _, ent_type = label.split("-", 1)
        else:
            ent_type = label

        key = (ent_type, word_idx)
        if key in used:
            continue
        used.add(key)

        word = words[word_idx]
        if ent_type not in entities:
            entities[ent_type] = word
        else:
            entities[ent_type] += " " + word

    # ------- 用整页文本再“精修”一次卖方 / 买方 -------
    seller_name, client_name = extract_party_names_from_words(words)

    # 小策略：
    # - 如果没识别出 seller_name，但识别出了 client_name，
    #   那就先把 client_name 当成 seller（你的这张票就是这样）
    if not seller_name and client_name:
        seller_name = client_name
        client_name = None  # 避免下面再用它去覆盖 BUYER

    if seller_name:
        # 只覆盖 SELLER，BUYER 仍然用模型自己的实体
        entities["SELLER"] = seller_name

    print(f"🧠 模型识别出的实体(修正后): {entities}")

    # 如果解析到了 ITEMS 行项目，用第 1 行兜底填充 DESCRIPTION / QUANTITY
    if 'line_items' in locals() and line_items:
        first_item = line_items[0]
        print(f"🧾 使用 ITEMS 第 1 行兜底: {first_item}")

        desc = first_item.get("description")
        qty = first_item.get("qty")

        if desc:
            entities["DESCRIPTION"] = desc
        if qty:
            entities["QUANTITY"] = qty

        print(f"🧾 兜底覆盖后的实体: {entities}")

    extracted_fields = map_entities_to_fields(entities, currency_symbol)

    print(f"📦 提取出的字段: {extracted_fields}")

    return extracted_fields


# ==========================================================
# 🧩 核心任务执行：推理 + 校验 + 回调
# ==========================================================
async def run_algorithm_task(
    process_id: str,
    file_info: Dict[str, Any],
    callback_url: str,
    algorithm_task_id: str,
    validation_params: Dict[str, Any],
):
    """
    后台执行算法任务，并按接口契约回调后端
    """
    pdf_path = file_info.get("storagePath")
    try:
        print("🔧 正在读取 PDF:", pdf_path)
        extracted_fields = extract_fields_from_pdf(pdf_path)
    
        # ---------- 逻辑校验 ----------
        validation_result = run_validation_if_needed(extracted_fields, validation_params)
        status = "success"
        error_code = None
        error_msg = None

        if validation_result and validation_result.validationStatus == "failed":
            skip_on_fail = bool(validation_params.get("skipOnFail"))
            if skip_on_fail:
                status = "fail"
                error_code = "VALIDATION_FAILED"
                error_msg = "逻辑校验失败，终止算法执行"

               # ---------- 构造回调数据 ----------
        now_ms = int(time.time() * 1000)
        headers = {
            "Content-Type": "application/json",
        }
        if SERVICE_TOKEN:
            headers["X-Service-Token"] = SERVICE_TOKEN

        # 这里先定义通用的基础字段（两种情况都要带）
        base_data = {
            "algorithmTaskId": algorithm_task_id,
            "processId": process_id,
            "modelId": "invoice_field_v1.0",            # 你的模型 ID
            "modelName": "发票关键字段提取模型",          # 你的模型名称
        }

        async with httpx.AsyncClient(trust_env=False) as client:
            if status == "success":
                # ✅ 模型 + 校验都 OK
                callback_data = {
                    **base_data,
                    "status": "success",
                    "extractedFields": extracted_fields,  # 模型真输出
                    "validationResult": (
                        validation_result.dict() if validation_result else None
                    ),
                    "endTime": now_ms,
                }
            else:
                # ⚠️ 例如 VALIDATION_FAILED 这种：
                # 仍然把模型抽取结果和校验结果一并回给后端
                callback_data = {
                    **base_data,
                    "status": "fail",
                    "errorCode": error_code,
                    "errorMsg": error_msg,
                    "extractedFields": extracted_fields,  # 一样是真实字段
                    "validationResult": (
                        validation_result.dict() if validation_result else None
                    ),
                    "failTime": now_ms,
                }

            resp = await client.post(callback_url, json=callback_data, headers=headers)
            resp.raise_for_status()

        print("✅ 已成功回调后端！")


    except Exception as e:
        print("❌ 算法执行报错:", e)
        now_ms = int(time.time() * 1000)
        error_data = {
            "algorithmTaskId": algorithm_task_id,
            "processId": process_id,
            "status": "fail",
            "errorCode": "SERVICE_UNAVAILABLE",
            "errorMsg": str(e),
            "validationResult": None,
            "failTime": now_ms,
            "modelId": "invoice_field_v1.0",
        }

        headers = {"Content-Type": "application/json"}
        if SERVICE_TOKEN:
            headers["X-Service-Token"] = SERVICE_TOKEN

        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                await client.post(callback_url, json=error_data, headers=headers)
        except Exception as e2:
            print("❌ 回调错误也失败了:", e2)


# ==========================================================
# 🧩 统一的入口处理函数（供两个路由复用）
# ==========================================================
async def _handle_algorithm_extract(request: Request) -> AlgorithmInitialResponse:
    """
    与后端《算法接口对接 v2》契约对齐：
    - Body: JSON
      {processId, fileInfo, modelParams, callbackUrl, validationParams}
    """
    # 0. 鉴权（可选）
    service_token = request.headers.get("X-Service-Token")
    if API_TOKEN:
        if service_token != API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid X-Service-Token")

    body = await request.json()

    process_id = body.get("processId")
    file_info = body.get("fileInfo") or {}
    callback_url = body.get("callbackUrl")
    model_params = body.get("modelParams") or {}
    validation_params = body.get("validationParams") or {}

    if not process_id or not callback_url or "storagePath" not in file_info:
        raise HTTPException(
            status_code=400,
            detail="缺少必要参数：processId / fileInfo.storagePath / callbackUrl",
        )

        # ✅ 只在明确 needValidation=false 时不建校验任务
    need_flag = validation_params.get("needValidation")
    need_validation = (need_flag is not False)

    validation_task_status = None
    if need_validation:
        validation_task_status = "pending_validation"
        # 这里暂时不强校验 ruleIds 是否存在，避免前后端联调阶段频繁 400
        # 如需严格遵守文档，可在此处检查 ruleIds 并抛出 VALIDATION_PARAM_MISSING / VALIDATION_RULE_NOT_FOUND

    import uuid
    algorithm_task_id = f"alg-task-{uuid.uuid4()}"

    print(f"🔥 接收到后端任务 processId={process_id}")
    print(f"📄 文件路径: {file_info.get('storagePath')}")
    print(f"📬 回调地址: {callback_url}")
    print(f"🧠 模型参数: {model_params}")
    print(f"🧪 校验参数: {validation_params}")
    print("==== 开始后台处理 ====")

    # 后台执行任务
    import asyncio
    asyncio.create_task(
        run_algorithm_task(
            process_id=process_id,
            file_info=file_info,
            callback_url=callback_url,
            algorithm_task_id=algorithm_task_id,
            validation_params=validation_params,
        )
    )

    # 同步返回“任务受理成功”
    # 这里 estimatedTime 写个经验值（秒），后续可根据模型耗时统计调整
    return AlgorithmInitialResponse(
        code=200,
        message="模型+校验任务受理成功" if need_validation else "模型任务受理成功",
        algorithmTaskId=algorithm_task_id,
        status="pending",
        validationTaskStatus=validation_task_status,
        estimatedTime=7,
    )


# ==========================================================
# 🧩 路由：新契约路径 + 兼容旧路径
# ==========================================================
@app.post("/api/algorithm/invoice-extract", response_model=AlgorithmInitialResponse)
async def api_algorithm_invoice_extract(request: Request):
    return await _handle_algorithm_extract(request)


@app.post("/algorithm/extract", response_model=AlgorithmInitialResponse)
async def algorithm_extract_compat(request: Request):
    """
    兼容旧版 /algorithm/extract 调用：
    内部复用新契约处理函数，方便后端切换。
    """
    return await _handle_algorithm_extract(request)


# ==========================================================
# 📈 召回率 / 指标接口（原样保留）
# ==========================================================
@app.get("/algorithm/metrics")
def get_metrics():
    if not os.path.exists(METRIC_LOG_PATH):
        return {"success": False, "message": "未找到训练日志文件"}

    try:
        df = pd.read_csv(METRIC_LOG_PATH)
        metrics = df.to_dict(orient="records")
        summary = df.iloc[-1].to_dict()
        return {"success": True, "summary": summary, "curve_data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取召回率文件失败: {e}")


@app.get("/algorithm/metrics/chart", summary="获取模型性能曲线（ECharts格式）")
async def get_metrics_chart():
    possible_files = ["metrics_data.csv", "training_metrics.csv"]
    csv_path = None

    for fname in possible_files:
        full_path = os.path.join(BASE_DIR, fname)
        if os.path.exists(full_path):
            csv_path = full_path
            print(f"📄 检测到指标文件：{full_path}")
            break

    if not csv_path:
        return JSONResponse(
            {
                "success": False,
                "message": "未找到任何指标文件，请先生成真实的 metrics_data.csv 或 training_metrics.csv",
            },
            status_code=404,
        )

    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", engine="python")
        df.columns = [c.strip().lower() for c in df.columns]

        required_cols = {"epoch", "precision", "recall", "f1"}
        if not required_cols.issubset(df.columns):
            return JSONResponse(
                {
                    "success": False,
                    "message": f"CSV 文件缺少必要列，应包含：{', '.join(required_cols)}",
                },
                status_code=400,
            )

        data = {
            "xAxis": df["epoch"].tolist(),
            "series": {
                "precision": df["precision"].tolist(),
                "recall": df["recall"].tolist(),
                "f1": df["f1"].tolist(),
            },
            "source_file": os.path.basename(csv_path),
            "success": True,
            "message": f"曲线数据加载成功（来源：{os.path.basename(csv_path)}）",
        }

        print(f"📊 成功加载指标数据：{csv_path}")
        return JSONResponse(content=data)

    except Exception as e:
        print(f"❌ 加载或解析指标文件失败: {e}")
        return JSONResponse(
            {
                "success": False,
                "message": f"读取或解析指标文件出错: {str(e)}",
            },
            status_code=500,
        )


# ==========================================================
# ♻️ 规则热加载接口（原样保留）
# ==========================================================
@app.post("/algorithm/reload_rules")
def reload_rules():
    global rules_data, rule_engine
    try:
        new_rules = load_rules()
        rules_data = new_rules
        rule_engine = RuleEngine(new_rules)
        print("♻️ 规则文件已重新加载！")
        return {"success": True, "message": "规则文件已重新加载 ✅"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"规则重载失败: {e}")


# ==========================================================
# ⚙️ 启动信息
# ==========================================================
print(f"🚀 Algorithm service running at http://{HOST}:{PORT}")
print(f"🐞 Debug Mode: {'ON' if DEBUG_MODE else 'OFF'}")

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, reload=DEBUG_MODE)
