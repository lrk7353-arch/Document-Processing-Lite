# -*- coding: utf-8 -*-
"""
Invoice validator with configurable rule engine
- CSV（中文表头）映射保留
- 校验逻辑由外部 JSON 配置驱动（默认 rule_config.json）
- 支持规则类型：required, regex, length, range, date_range, decimal_places,
  logic (表达式), prohibited_chars, duplicate, similarity（买卖双方相似度）等
- 支持配置引用 ${global.xxx}、条件执行、优先级、severity（error/warning）
- 保留风险评分并支持在配置中定义扣分权重
- 使用方式:
    python invoice_validator_with_rules.py [path/to/batch1_3_split_clear.csv] [path/to/rule_config.json]
  默认 CSV: batch1_3_split_clear.csv
  默认 规则文件: rule_config.json

注意：为简化表达式求值，我们在受限环境下使用 eval，配置表达式应谨慎（仅在受信任环境下使用）。
"""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import List, Dict, Any, Optional, Set, Tuple
import csv
import sys
import json
import os
import copy

MAX_NAME_LENGTH = 100
PROHIBITED_NAME_CHARS = set(['！', '？', '\n', '\r', '\t'])

def _strip_and_none(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s != "" else None
    return v

def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    la = len(a)
    lb = len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev_row = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, start=1):
            insertions = prev_row[j] + 1
            deletions = cur[j - 1] + 1
            substitutions = prev_row[j - 1] + (0 if ca == cb else 1)
            cur[j] = min(insertions, deletions, substitutions)
        prev_row = cur
    return prev_row[lb]

# --------------------
# Rule Engine
# --------------------
class RuleEngine:
    SUPPORTED_RULE_TYPES = {
        "required", "regex", "length", "range", "date_range", "decimal_places",
        "logic", "prohibited_chars", "duplicate", "similarity"
    }

    def __init__(self, config: Dict[str, Any]):
        self.raw_config = config
        self.global_cfg = config.get("global", {})
        self.fields_cfg = config.get("fields", {})
        # scoring config (deductions)
        self.scoring = config.get("scoring", {})
        # header mapping may be in config (optional)
        self.header_mapping = config.get("header_mapping")
        # Validate config structure
        self._validate_config()

    # Resolve simple ${global.xxx} in strings; also support nested dicts/lists
    def _resolve_refs(self, obj):
        if isinstance(obj, str):
            # pattern ${global.xxx}
            def repl(m):
                path = m.group(1)
                parts = path.split(".")
                if parts[0] != "global":
                    return m.group(0)
                cur = self.global_cfg
                for p in parts[1:]:
                    if isinstance(cur, dict) and p in cur:
                        cur = cur[p]
                    else:
                        return m.group(0)
                return str(cur)
            return re.sub(r"\$\{([^}]+)\}", repl, obj)
        elif isinstance(obj, dict):
            return {k: self._resolve_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_refs(v) for v in obj]
        else:
            return obj

    def _validate_config(self):
        # top-level checks
        if not isinstance(self.global_cfg, dict):
            raise ValueError("配置文件缺少 global 节或其格式不正确")
        if not isinstance(self.fields_cfg, dict):
            raise ValueError("配置文件缺少 fields 节或其格式不正确")
        # Validate each field's rules
        for field, rules in self.fields_cfg.items():
            if not isinstance(rules, list):
                raise ValueError(f"字段 {field} 的规则须为列表")
            for r in rules:
                if not isinstance(r, dict):
                    raise ValueError(f"字段 {field} 的某条规则不是对象")
                if "rule_id" not in r:
                    raise ValueError(f"字段 {field} 的某条规则缺少 rule_id")
                if "rule_type" not in r:
                    raise ValueError(f"规则 {r.get('rule_id')} 缺少 rule_type")
                if r["rule_type"] not in self.SUPPORTED_RULE_TYPES:
                    raise ValueError(f"规则 {r.get('rule_id')} 使用了不支持的 rule_type: {r['rule_type']}")
                if "severity" not in r:
                    raise ValueError(f"规则 {r.get('rule_id')} 缺少 severity（error/warning）")
                if r["severity"] not in ("error", "warning"):
                    raise ValueError(f"规则 {r.get('rule_id')} severity 必须为 error 或 warning")
                if "error_msg" not in r:
                    raise ValueError(f"规则 {r.get('rule_id')} 缺少 error_msg")
                # minimal params check per rule_type
                rt = r["rule_type"]
                params = r.get("params", {})
                if rt == "regex" and "pattern" not in params:
                    raise ValueError(f"规则 {r.get('rule_id')} 类型 regex 需提供 params.pattern")
                if rt == "length" and ("max" not in params and "min" not in params):
                    raise ValueError(f"规则 {r.get('rule_id')} 类型 length 需提供 params.max 或 params.min")
                if rt == "range" and ("max" not in params and "min" not in params):
                    raise ValueError(f"规则 {r.get('rule_id')} 类型 range 需提供 params.max 或 params.min")
                if rt == "date_range" and ("max" not in params and "min" not in params):
                    raise ValueError(f"规则 {r.get('rule_id')} 类型 date_range 需提供 params.max 或 params.min")
                if rt == "decimal_places" and "max_places" not in params:
                    raise ValueError(f"规则 {r.get('rule_id')} 类型 decimal_places 需提供 params.max_places")
                if rt == "duplicate" and ("scope" not in params or params["scope"] not in ("history", "file")):
                    raise ValueError(f"规则 {r.get('rule_id')} 类型 duplicate 需提供 params.scope (history|file)")
                if rt == "similarity":
                    if "other_field" not in params:
                        raise ValueError(f"规则 {r.get('rule_id')} 类型 similarity 需提供 params.other_field")
                # resolve string refs inside params/error_msg
        # After basic validation, resolve any ${global.xxx} in the entire fields_cfg
        self.fields_cfg = {f: [self._resolve_refs(r) for r in rules] for f, rules in self.fields_cfg.items()}
        # header mapping if provided
        if self.header_mapping:
            # ensure mapping is dict
            if not isinstance(self.header_mapping, dict):
                raise ValueError("header_mapping 必须为 dict")

    # Helper: parse date with allowed formats from global
    def parse_date(self, raw: str):
        if raw is None:
            return None, "空值"
        if isinstance(raw, datetime):
            return raw.date(), None
        s = str(raw).strip()
        if s == "":
            return None, "空字符串"
        formats = self.global_cfg.get("allowed_date_formats", ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"])
        for fmt in formats:
            try:
                dt = datetime.strptime(s, fmt).date()
                return dt, None
            except Exception:
                pass
        # try more flexible parsing like original: mm/dd/yyyy vs dd/mm/yyyy heuristics
        if "/" in s:
            parts = s.split("/")
            if len(parts) == 3:
                p0, p1, p2 = parts
                try:
                    i0 = int(p0); i1 = int(p1); i2 = int(p2)
                except Exception:
                    return None, "日期格式不合法（含非数字部分）"
                if i0 > 9999:
                    return None, f"日期格式错误，日期部分数值超出合理范围（{i0} 过大）"
                # choose try order heuristically (same as original)
                if i0 > 12 and i1 <= 12:
                    try_order = ["%d/%m/%Y"]
                elif i1 > 12 and i0 <= 12:
                    try_order = ["%m/%d/%Y"]
                else:
                    try_order = ["%m/%d/%Y", "%d/%m/%Y"]
                tried = []
                for fmt in try_order:
                    try:
                        dt = datetime.strptime(s, fmt).date()
                        return dt, None
                    except Exception:
                        tried.append(fmt)
                return None, f"日期解析失败（尝试格式 {tried}）"
        if re.fullmatch(r"\d{8}", s):
            try:
                dt = datetime.strptime(s, "%Y%m%d").date()
                return dt, None
            except Exception:
                pass
        return None, "不支持的日期格式"

    def parse_decimal(self, value, field_label, errors: List[str]):
        if value is None:
            errors.append(f"{field_label} 缺失")
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            s = value.strip()
            s = s.replace(",", "").replace(" ", "")
            if s == "":
                errors.append(f"{field_label} 为空字符串")
                return None
            try:
                return Decimal(s)
            except InvalidOperation:
                errors.append(f"{field_label} 无法解析为数值：{value}")
                return None
        errors.append(f"{field_label} 类型不受支持：{type(value)}")
        return None

    # Core: evaluate rules for one invoice
    def apply_rules(self, raw_invoice: Dict[str, Any], history_set: Set[str], seen_in_file: Set[str]) -> Dict[str, Any]:
        """
        raw_invoice: original row mapping keys to raw values (strings)
        history_set: historical invoice numbers (uppercased)
        seen_in_file: invoice numbers already seen in this file (uppercased)
        Returns: {passed, errors, warnings, normalized}
        """
        errors: List[str] = []
        warnings: List[str] = []
        normalized: Dict[str, Any] = {}

        # Basic normalization similar to original:
        fields = {
            "invoice_no": _strip_and_none(raw_invoice.get("invoice_no")),
            "date": _strip_and_none(raw_invoice.get("date")),
            "buyer_name": _strip_and_none(raw_invoice.get("buyer_name")),
            "seller_name": _strip_and_none(raw_invoice.get("seller_name")),
            "description": _strip_and_none(raw_invoice.get("description")),
            "quantity": raw_invoice.get("quantity"),
            "unit_price": raw_invoice.get("unit_price"),
            "total_amount": raw_invoice.get("total_amount"),
        }

        # normalize invoice_no (uppercase) if present
        if fields["invoice_no"] is not None and isinstance(fields["invoice_no"], str):
            normalized["invoice_no"] = fields["invoice_no"].upper()

        # normalize names
        for label in ("buyer_name", "seller_name"):
            v = fields.get(label)
            if v is not None and isinstance(v, str):
                normalized[label] = v.strip()

        # description
        if fields.get("description") is not None and isinstance(fields.get("description"), str):
            normalized["description"] = fields["description"].strip()

        # parse numbers (but keep original raw until rules run)
        qty = self.parse_decimal(fields.get("quantity"), "quantity", errors)
        unit_price = self.parse_decimal(fields.get("unit_price"), "unit_price", errors)
        total_amt = self.parse_decimal(fields.get("total_amount"), "total_amount", errors)

        if qty is not None:
            normalized["quantity"] = qty
        if unit_price is not None:
            normalized["unit_price"] = unit_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total_amt is not None:
            normalized["total_amount"] = total_amt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # parse date
        parsed_date = None
        if fields.get("date") is not None:
            pd, derr = self.parse_date(fields.get("date"))
            if pd is None:
                # don't add here; let rules handle date parsing error. But we append an internal parse error to errors
                errors.append(f"date 无法解析：{derr}")
            else:
                parsed_date = pd
                normalized["date"] = parsed_date.strftime("%Y-%m-%d")

        # prepare a context for condition/logic evaluation: normalized values, numeric fields available as Decimal
        eval_ctx = {}
        eval_ctx.update({k: v for k, v in normalized.items()})
        # Also put raw fields as fallback
        eval_ctx.update({k: fields.get(k) for k in fields.keys() if k not in eval_ctx})
        # numeric friendly names (quantity/unit_price/total_amount) - use Decimal or None
        eval_ctx["quantity"] = normalized.get("quantity")
        eval_ctx["unit_price"] = normalized.get("unit_price")
        eval_ctx["total_amount"] = normalized.get("total_amount")
        eval_ctx["invoice_no"] = normalized.get("invoice_no")
        eval_ctx["buyer_name"] = normalized.get("buyer_name")
        eval_ctx["seller_name"] = normalized.get("seller_name")
        eval_ctx["description"] = normalized.get("description")
        eval_ctx["date_parsed"] = parsed_date  # date object or None

        # Helper to evaluate condition or logic expression safely (limited globals)
        def safe_eval(expr: str, local_vars: Dict[str, Any]):
            # We allow basic operators and attribute access on decimals/dates/strings,
            # but no builtins. This is a pragmatic compromise; configs should be trusted.
            try:
                return eval(expr, {"__builtins__": None}, local_vars)
            except Exception:
                return None

        # Apply each field's rules in priority order
        # We'll build a list of rules across fields sorted by priority
        rules_to_apply = []
        for field, rules in self.fields_cfg.items():
            for r in rules:
                pr = r.get("priority", 1000)
                rules_to_apply.append((pr, field, r))
        rules_to_apply.sort(key=lambda x: x[0])  # lower priority first

        for _, field, rule in rules_to_apply:
            rid = rule["rule_id"]
            rtype = rule["rule_type"]
            severity = rule.get("severity", "error")
            params = rule.get("params", {})
            # condition evaluation (if provided) - condition is a python expression using variable names
            cond = rule.get("condition")
            if cond:
                cond_res = safe_eval(self._resolve_refs(cond), eval_ctx)
                if not cond_res:
                    continue  # skip this rule
            # retrieve the value to validate
            value = None
            if field in eval_ctx:
                value = eval_ctx.get(field)
            else:
                # missing field - use raw
                value = fields.get(field)

            # perform checks by rule type
            triggered = False
            msg = rule.get("error_msg", "")
            # For messages, allow placeholders like {field}, {min}, {max}, etc.
            fmt_params = {"field": field}
            fmt_params.update(params if isinstance(params, dict) else {})

            if rtype == "required":
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    triggered = True

            elif rtype == "regex":
                pattern = params.get("pattern")
                if pattern is None:
                    continue
                try:
                    pat = re.compile(pattern)
                except Exception:
                    # invalid pattern in config
                    errors.append(f"配置错误：rule {rid} regex pattern 无效: {pattern}")
                    continue
                vs = value if value is not None else ""
                if not isinstance(vs, str):
                    vs = str(vs)
                if not pat.match(vs):
                    triggered = True

            elif rtype == "length":
                vs = value if value is not None else ""
                if not isinstance(vs, str):
                    vs = str(vs)
                ln = len(vs)
                minv = params.get("min")
                maxv = params.get("max")
                if minv is not None and ln < int(minv):
                    triggered = True
                if maxv is not None and ln > int(maxv):
                    triggered = True
                fmt_params["min"] = minv
                fmt_params["max"] = maxv

            elif rtype == "range":
                # numeric range; value should be Decimal or parseable
                numeric = value
                if not isinstance(numeric, Decimal):
                    # try parse if string or int
                    try:
                        numeric = Decimal(str(value)) if value is not None else None
                    except Exception:
                        numeric = None
                minv = params.get("min")
                maxv = params.get("max")
                if minv is not None:
                    min_dec = Decimal(str(minv))
                    if numeric is None or numeric < min_dec:
                        triggered = True
                if maxv is not None:
                    max_dec = Decimal(str(maxv))
                    if numeric is None or numeric > max_dec:
                        triggered = True
                fmt_params["min"] = minv
                fmt_params["max"] = maxv

            elif rtype == "date_range":
                # params min/max are date strings in allowed formats or ISO YYYY-MM-DD
                minv = params.get("min")
                maxv = params.get("max")
                # value expected to be parsed_date available as date_parsed
                dv = eval_ctx.get("date_parsed")
                parsed_min = None
                parsed_max = None
                if minv is not None:
                    parsed_min, _ = self.parse_date(minv)
                if maxv is not None:
                    parsed_max, _ = self.parse_date(maxv)
                if dv is None:
                    triggered = True
                else:
                    if parsed_min is not None and dv < parsed_min:
                        triggered = True
                    if parsed_max is not None and dv > parsed_max:
                        triggered = True
                fmt_params["min"] = minv
                fmt_params["max"] = maxv

            elif rtype == "decimal_places":
                max_places = int(params.get("max_places", 2))
                numeric = value
                if isinstance(numeric, Decimal):
                    tup = numeric.normalize().as_tuple()
                    exp = -tup.exponent if tup.exponent < 0 else 0
                    if exp > max_places:
                        triggered = True
                else:
                    # try parse
                    try:
                        d = Decimal(str(value))
                        tup = d.normalize().as_tuple()
                        exp = -tup.exponent if tup.exponent < 0 else 0
                        if exp > max_places:
                            triggered = True
                    except Exception:
                        # not parseable -> trigger as format error
                        triggered = True
                fmt_params["max_places"] = max_places

            elif rtype == "logic":
                # expression in params.expression to be evaluated with eval_ctx
                expr = params.get("expression")
                if expr is None:
                    continue
                # allow expressions like "total_amount == (quantity * unit_price).quantize(Decimal('0.01'))"
                # We inject Decimal class into local context for convenience
                local_ctx = dict(eval_ctx)
                local_ctx["Decimal"] = Decimal
                res = safe_eval(expr, local_ctx)
                if res is None or res is False:
                    triggered = True
                fmt_params.update(params)

            elif rtype == "prohibited_chars":
                # params.chars: list or string
                forbid = params.get("chars", [])
                if isinstance(forbid, str):
                    forbid = list(forbid)
                vs = value if value is not None else ""
                if any(ch in vs for ch in forbid):
                    triggered = True
                fmt_params["chars"] = forbid

            elif rtype == "duplicate":
                scope = params.get("scope", "history")
                inv_no = normalized.get("invoice_no") or (raw_invoice.get("invoice_no") or "").upper()
                if scope == "history":
                    if inv_no and inv_no in history_set:
                        triggered = True
                elif scope == "file":
                    if inv_no and inv_no in seen_in_file:
                        triggered = True
                fmt_params["scope"] = scope

            elif rtype == "similarity":
                other_field = params.get("other_field")
                max_distance = int(params.get("max_distance", 2))
                max_len_diff = int(params.get("max_length_diff", 3))
                v1 = normalized.get(field) or (raw_invoice.get(field) or "")
                v2 = normalized.get(other_field) or (raw_invoice.get(other_field) or "")
                if not isinstance(v1, str) or not isinstance(v2, str):
                    # cannot compare; skip
                    triggered = False
                else:
                    s1 = v1.strip().lower()
                    s2 = v2.strip().lower()
                    if s1 != s2:
                        ld = levenshtein_distance(s1, s2)
                        ldiff = abs(len(s1) - len(s2))
                        if ld <= max_distance and ldiff <= max_len_diff:
                            triggered = True
                            fmt_params["distance"] = ld
                            fmt_params["length_diff"] = ldiff
                fmt_params.update(params)

            # If triggered, append message to errors or warnings
            if triggered:
                try:
                    msg = rule.get("error_msg", "")
                    # format placeholders
                    msg = msg.format(field=field, **{k: v for k, v in fmt_params.items()})
                except Exception:
                    msg = rule.get("error_msg", "")
                if severity == "error":
                    errors.append(msg)
                else:
                    warnings.append(msg)

        # After all rules, also perform original-style quantity/unit_price/total_amount comparison if not already defined in rules
        # But since original config will include such logic rule, we skip adding duplicates here.

        passed = len(errors) == 0
        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "normalized": normalized
        }

    # Compute risk score and confidence level using scoring config
    def compute_risk_and_confidence(self, errors: List[str], warnings: List[str]) -> Tuple[int, str]:
        # scoring config example:
        # {
        #   "deductions": {
        #       "required": 20,
        #       "format": 15,
        #       "logic": 30,
        #       "duplicate_history": 40,
        #       "numeric_format": 15,
        #       "warning_large_qty": 5,
        #       "warning_total_diff": 3,
        #       "warning_in_file_dup": 8
        #   },
        #   "confidence_levels": { "high": [90,100], "mid":[70,89], ... }
        # }
        deductions = self.scoring.get("deductions", {})
        # default deduction mapping if not provided
        default = {
            "required": 20,
            "format": 15,
            "logic": 30,
            "duplicate_history": 40,
            "numeric_format": 15,
            "warning_large_qty": 5,
            "warning_total_diff": 3,
            "warning_in_file_dup": 8
        }
        # merge
        dd = dict(default)
        dd.update(deductions)

        score = 100
        # We'll attempt to classify each error string into categories using keywords (configurable by pattern in scoring)
        # Scoring patterns (can be extended in config)
        patterns = self.scoring.get("patterns", {
            "missing": ["缺失", "空值", "为空字符串", "为仅空白"],
            "format": ["格式错误", "类型错误", "无法解析为数值", "类型不受支持", "小数位超过", "无法解析为日期"],
            "logic": ["逻辑不一致", "不一致", "逻辑", "超出当前日期", "非法"],
            "duplicate_history": ["历史数据重复", "与历史数据重复", "发票号码重复"]
        })
        # Count errors
        e_missing = e_format = e_logic = e_duplicate_history = 0
        for e in errors:
            el = e.lower()
            matched = False
            for kw in patterns.get("duplicate_history", []):
                if kw.lower() in el:
                    e_duplicate_history += 1
                    matched = True
                    break
            if matched:
                continue
            for kw in patterns.get("missing", []):
                if kw.lower() in el:
                    e_missing += 1
                    matched = True
                    break
            if matched:
                continue
            for kw in patterns.get("logic", []):
                if kw.lower() in el:
                    e_logic += 1
                    matched = True
                    break
            if matched:
                continue
            for kw in patterns.get("format", []):
                if kw.lower() in el:
                    e_format += 1
                    matched = True
                    break
            if matched:
                continue
            # fallback to format
            e_format += 0

        score -= e_missing * dd.get("required", dd["required"])
        score -= e_format * dd.get("format", dd["format"])
        score -= e_logic * dd.get("logic", dd["logic"])
        score -= e_duplicate_history * dd.get("duplicate_history", dd["duplicate_history"])

        # warnings classification
        w_large = w_total_diff = w_in_file_dup = 0
        for w in warnings:
            wl = w.lower()
            if "数量异常偏大" in wl or "数量异常" in wl:
                w_large += 1
            if "总金额与数量×单价存在差异" in wl or ("差异" in wl and "数量" in wl and "单价" in wl):
                w_total_diff += 1
            if "本文件内发票号重复" in wl or "本文件内重复" in wl:
                w_in_file_dup += 1
        score -= w_large * dd.get("warning_large_qty", dd["warning_large_qty"])
        score -= w_total_diff * dd.get("warning_total_diff", dd["warning_total_diff"])
        score -= w_in_file_dup * dd.get("warning_in_file_dup", dd["warning_in_file_dup"])

        if score < 0:
            score = 0
        score = int(score)

        # confidence level thresholds configurable
        thresholds = self.scoring.get("confidence_thresholds", {
            "high": [90, 100],
            "medium": [70, 89],
            "low": [40, 69],
            "very_low": [0, 39]
        })
        lvl = "极低置信度"
        if thresholds:
            if thresholds["high"][0] <= score <= thresholds["high"][1]:
                lvl = "高置信度"
            elif thresholds["medium"][0] <= score <= thresholds["medium"][1]:
                lvl = "中置信度"
            elif thresholds["low"][0] <= score <= thresholds["low"][1]:
                lvl = "低置信度"
            else:
                lvl = "极低置信度"
        else:
            # fallback
            if score >= 90:
                lvl = "高置信度"
            elif score >= 70:
                lvl = "中置信度"
            elif score >= 40:
                lvl = "低置信度"
            else:
                lvl = "极低置信度"
        return score, lvl

# ---------------------------
# CSV -> 字段映射与主流程 (保留 HEADER_MAPPING 以向后兼容)
# ---------------------------
HEADER_MAPPING = {
    "发票号码": "invoice_no",
    "日期": "date",
    "买方名称": "buyer_name",
    "卖方名称": "seller_name",
    "货物描述": "description",
    "数量": "quantity",
    "单价": "unit_price",
    "总金额": "total_amount",
}

def read_csv_as_invoices(path: str, header_mapping_override: Optional[Dict[str,str]] = None) -> List[Dict[str, Any]]:
    invoices = []
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV 文件未找到：{path}")
    with open(path, "r", encoding="utf-8", newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = [fn.strip().lstrip('\ufeff') if fn else fn for fn in reader.fieldnames or []]
        col_to_key = {}
        hm = header_mapping_override if header_mapping_override is not None else HEADER_MAPPING
        for col in fieldnames:
            if col in hm:
                col_to_key[col] = hm[col]
            elif col in hm.values():
                col_to_key[col] = col
            else:
                col_nospace = col.replace(" ", "")
                mapped = None
                for k, v in hm.items():
                    if k.replace(" ", "") == col_nospace:
                        mapped = v
                        break
                col_to_key[col] = mapped
        for i, row in enumerate(reader, start=1):
            invoice = {}
            for col, val in row.items():
                if col is None:
                    continue
                col = col.strip().lstrip('\ufeff')
                key = col_to_key.get(col)
                if key:
                    invoice[key] = val
            invoices.append(invoice)
    return invoices

# ---------------------------
# Main
# ---------------------------
def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"规则配置文件未找到：{path}")
    with open(path, "r", encoding="utf-8") as fr:
        cfg = json.load(fr)
    return cfg

def main(csv_path: str, config_path: str):
    print("读取 CSV：", csv_path)
    invoices = read_csv_as_invoices(csv_path)
    print(f"共读取 {len(invoices)} 条记录（按 CSV 行计）")
    # 加载规则配置
    cfg = load_config(config_path)
    # allow header mapping override from config
    header_mapping_override = cfg.get("header_mapping")
    if header_mapping_override:
        # re-read invoices with new mapping if mapping provided
        invoices = read_csv_as_invoices(csv_path, header_mapping_override)
    engine = RuleEngine(cfg)

    # history init
    history_list = cfg.get("history_invoice_numbers", [])
    validator_history = set([str(x).upper() for x in history_list if x is not None])
    seen = set()
    results = []
    for idx, inv in enumerate(invoices, start=1):
        res = engine.apply_rules(inv, validator_history, seen)
        inv_no_norm = res["normalized"].get("invoice_no")
        if inv_no_norm:
            # check in-file duplicate: the engine's duplicate rule may have flagged this already if configured,
            # but we also append the standard warning if found (to maintain prior behavior)
            if inv_no_norm in seen:
                res["warnings"].append(f"本文件内发票号重复：{inv_no_norm}")
            seen.add(inv_no_norm)
            validator_history.add(inv_no_norm)  # add to history to prevent later duplicates
        # compute risk score using engine
        risk_score, confidence_level = engine.compute_risk_and_confidence(res["errors"], res["warnings"])
        res["risk_score"] = risk_score
        res["confidence_level"] = confidence_level

        results.append({
            "row": idx,
            "invoice_in": inv,
            "result": res
        })
        status = "PASS" if res["passed"] else "FAIL"
        print(f"[{status}] 行 {idx} 发票号: {inv.get('invoice_no')} -> errors:{len(res['errors'])} warnings:{len(res['warnings'])} risk_score:{risk_score} confidence:{confidence_level}")

    out_file = "validation_results.json"
    with open(out_file, "w", encoding="utf-8") as fw:
        json.dump(results, fw, ensure_ascii=False, indent=2, default=str)
    print(f"校验完成。结果已写入 {out_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = "batch1_3_split_clear.csv"
    if len(sys.argv) > 2:
        config_path = sys.argv[2]
    else:
        config_path = "rule_config.json"
    try:
        main(csv_path, config_path)
    except Exception as e:
        print("运行时发生错误：", e)
        raise