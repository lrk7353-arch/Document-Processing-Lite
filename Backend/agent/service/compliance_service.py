from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from agent.models.agui import (
    ComplianceCheckStartData, ComplianceCheckProgressData,
    ComplianceCheckCompleteData, RuleResult, TaskTotalProgressData,
    TaskCompleteData, FieldDetail, AGUIEvent
)
from agent.models.algorithm_data import ExtractedFieldResult
from agent.utils.logger import logger
from agent.utils.sse import sse_manager
from agent.utils.error import ErrorCode
from agent.db.crud.compliance import create_compliance_task, update_compliance_success, update_compliance_failure
from sqlalchemy.orm import Session


class ComplianceService:
    """增强版合规检查服务（支持复杂逻辑校验规则执行）"""

    def __init__(self):
        # 预定义合规规则（扩展版）
        self.compliance_rules = {
            "AMOUNT_LOGIC_001": {
                "ruleName": "金额逻辑校验",
                "description": "总金额 = 数量 × 单价（允许±0.01误差）",
                "severity": "high"
            },
            "DATE_VALID_002": {
                "ruleName": "日期有效性校验",
                "description": "开票日期不能晚于当前日期，且格式为YYYY-MM-DD",
                "severity": "high"
            },
            "SELLER_BUYER_003": {
                "ruleName": "买卖双方信息完整性",
                "description": "销售方名称和购买方名称不能为空",
                "severity": "high"
            },
            "GOODS_DESC_004": {
                "ruleName": "货物描述非空校验",
                "description": "货物描述字段不能为空",
                "severity": "medium"
            },
            "INVOICE_NO_FORMAT_005": {
                "ruleName": "发票号码格式校验",
                "description": "发票号码必须为数字且长度在6-20位之间",
                "severity": "high"
            },
            "AMOUNT_RANGE_006": {
                "ruleName": "金额范围校验",
                "description": "发票金额不能为负数且不能超过1000000元",
                "severity": "high"
            },
            "CONTRACT_NO_CHECK_007": {
                "ruleName": "合同编号关联性检查",
                "description": "如果存在合同编号，检查格式是否有效",
                "severity": "medium"
            },
            "TAX_RATE_CHECK_008": {
                "ruleName": "税率合理性检查",
                "description": "如果存在税率信息，检查是否在合理范围内（0-1之间）",
                "severity": "medium"
            }
        }

    def _get_rule_detail(self, rule_id: str) -> Optional[Dict[str, str]]:
        """获取合规规则详情"""
        return self.compliance_rules.get(rule_id)

    async def _push_compliance_event(self, process_id: str, event_type: str, data: Any):
        """推送合规相关SSE事件（《通信机制文档.pdf》SSE格式）"""
        try:
            # 创建AGUIEvent对象
            event = AGUIEvent(
                type=event_type,
                data=data,
                timestamp=int(datetime.now().timestamp() * 1000)
            )
            
            # 发送事件到SSE管理器
            success = await sse_manager.send_event(
                process_id=process_id,
                event=event
            )
            
            if not success:
                logger.warning(f"推送SSE事件失败: type={event_type}, process_id={process_id}", 
                             extra={"processId": process_id})
        except Exception as e:
            logger.error(f"推送SSE事件异常: {str(e)}, type={event_type}", 
                        extra={"processId": process_id}, exc_info=True)

    async def start_compliance_check(
            self, db: Session, process_id: str, extracted_fields: List[ExtractedFieldResult]
    ) -> Tuple[Optional[ComplianceCheckCompleteData], Optional[ErrorCode]]:
        """
        执行合规检查（文档"合规判断相关事件"流程）
        步骤：1. 推送开始事件 2. 创建合规任务 3. 逐条执行规则 4. 推送结果事件
        增强功能：增加风险等级评估，更详细的结果信息
        """
        logger.info(f"[合规检查] 开始检查任务: {process_id}")
        
        # 1. 推送合规检查开始事件（文档11.合规检查开始）
        check_rules = list(self.compliance_rules.keys())
        start_event_data = ComplianceCheckStartData(
            processId=process_id,
            checkRules=check_rules,
            startTime=int(datetime.now().timestamp() * 1000)
        )
        await self._push_compliance_event(
            process_id=process_id,
            event_type="compliance.check.start",
            data=start_event_data
        )

        # 2. 创建合规任务（数据库持久化）
        db_compliance_task = create_compliance_task(
            db=db,
            process_id=process_id,
            check_rules=check_rules,
            start_time=datetime.now()
        )
        if not db_compliance_task:
            logger.error(
                "创建合规任务失败",
                extra={"processId": process_id, "algorithmTaskId": ""}
            )
            return None, ErrorCode.SYSTEM_ERROR

        # 3. 推送任务总进度更新（文档15.任务总进度更新）
        await self._push_compliance_event(
            process_id=process_id,
            event_type="task.total.progress",
            data=TaskTotalProgressData(
                processId=process_id,
                currentStage="合规检查中",
                progress=30  # 假设总流程：上传20% + 模型提取50% + 合规检查30%
            )
        )

        # 4. 逐条执行合规规则（文档12.合规检查进度）
        rule_results: List[RuleResult] = []
        total_rules = len(check_rules)
        high_risk_count = 0
        medium_risk_count = 0
        low_risk_count = 0

        for idx, rule_id in enumerate(check_rules, 1):
            rule_detail = self._get_rule_detail(rule_id)
            if not rule_detail:
                logger.warning(
                    f"合规规则不存在: ruleId={rule_id}",
                    extra={"processId": process_id}
                )
                continue

            # 推送当前规则检查进度
            progress = int((idx / total_rules) * 100)
            await self._push_compliance_event(
                process_id=process_id,
                event_type="compliance.check.progress",
                data=ComplianceCheckProgressData(
                    processId=process_id,
                    progress=progress,
                    checkedRules=idx,
                    totalRules=total_rules,
                    currentRule=rule_id
                )
            )

            # 执行具体规则校验
            result, reason = self._execute_rule(rule_id, extracted_fields)
            
            # 确定风险等级
            risk_level = "low"
            if result == "fail":
                severity = rule_detail.get("severity", "medium")
                if severity == "high":
                    risk_level = "high"
                    high_risk_count += 1
                elif severity == "medium":
                    risk_level = "medium"
                    medium_risk_count += 1
                else:
                    low_risk_count += 1
            
            # 添加增强版规则结果
            rule_result = RuleResult(
                ruleId=rule_id,
                ruleName=rule_detail["ruleName"],
                result=result,
                reason=reason
            )
            
            # 添加风险等级信息（通过扩展属性存储）
            rule_result.severity = rule_detail.get("severity", "medium")
            rule_result.riskLevel = risk_level
            
            rule_results.append(rule_result)

        # 5. 生成合规检查结果（文档13.合规检查完成）
        overall_result = "pass" if all(r.result == "pass" for r in rule_results) else "fail"
        
        # 评估整体风险等级
        has_high_risk = any(hasattr(r, 'riskLevel') and r.riskLevel == "high" for r in rule_results)
        has_medium_risk = any(hasattr(r, 'riskLevel') and r.riskLevel == "medium" for r in rule_results)
        
        overall_risk_level = "low"
        if has_high_risk:
            overall_risk_level = "high"
        elif has_medium_risk:
            overall_risk_level = "medium"
        
        # 创建扩展版完成数据
        complete_event_data = ComplianceCheckCompleteData(
            processId=process_id,
            overallResult=overall_result,
            ruleResults=rule_results,
            endTime=int(datetime.now().timestamp() * 1000)
        )
        
        # 添加增强版属性
        complete_event_data.overallRiskLevel = overall_risk_level
        complete_event_data.highRiskCount = high_risk_count
        complete_event_data.mediumRiskCount = medium_risk_count
        complete_event_data.lowRiskCount = low_risk_count

        # 6. 更新数据库合规任务状态
        update_result = update_compliance_success(
            db=db,
            process_id=process_id,
            compliance_result=complete_event_data
        )
        if not update_result:
            logger.error(
                "更新合规任务结果失败",
                extra={"processId": process_id}
            )
            return None, ErrorCode.SYSTEM_ERROR

        # 7. 推送合规检查完成事件
        await self._push_compliance_event(
            process_id=process_id,
            event_type="compliance.check.complete",
            data=complete_event_data
        )

        # 8. 推送任务完成事件（聚合模型提取与合规结果）
        try:
            extracted_details = [
                FieldDetail(
                    fieldName=getattr(f, 'fieldName', ''),
                    fieldValue=getattr(f, 'fieldValue', ''),
                    confidence=getattr(f, 'confidence', 0.0),
                    position=getattr(f, 'position', None)
                ) for f in extracted_fields
            ]
        except Exception as map_err:
            logger.warning(f"字段映射失败，使用空结果推送task.complete: {map_err}", extra={"processId": process_id})
            extracted_details = []
        # 计算耗时 (当前时间 - 开始时间)
        current_ts = int(datetime.now().timestamp() * 1000)
        start_ts = start_event_data.startTime
        duration = current_ts - start_ts
        # 确保至少为 1ms，防止电脑太快算出 0 导致报错
        final_duration = max(1, duration)

        task_complete = TaskCompleteData(
            processId=process_id,
            fileId=f"file-{process_id}",
            extractedFields=extracted_details,
            complianceResult=complete_event_data,
            totalDuration=final_duration  # <--- 使用计算出的值
        )
        await self._push_compliance_event(
            process_id=process_id,
            event_type="task.complete",
            data=task_complete
        )

        # 9. 推送最终任务总进度（100%）
        await self._push_compliance_event(
            process_id=process_id,
            event_type="task.total.progress",
            data=TaskTotalProgressData(
                processId=process_id,
                currentStage="合规检查完成",
                progress=100
            )
        )

        logger.info(
            f"合规检查完成: overallResult={overall_result}, 风险等级: {overall_risk_level}, "
            f"规则通过{sum(1 for r in rule_results if r.result == 'pass')}/{total_rules}条, "
            f"高风险问题: {high_risk_count}, 中风险问题: {medium_risk_count}, 低风险问题: {low_risk_count}",
            extra={"processId": process_id}
        )
        return complete_event_data, None

    def _norm_num(self, v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            if not s:
                return None
            s = s.replace('%', '')
            for sym in ['$', '￥', '¥', '€']:
                s = s.replace(sym, '')
            s = s.replace(' ', '')
            if ',' in s and '.' in s:
                s = s.replace(',', '')
            elif ',' in s and '.' not in s:
                s = s.replace(',', '.')
            return float(s)
        except Exception:
            return None

    def _parse_date(self, s: Any) -> Optional[datetime]:
        if s is None:
            return None
        t = str(s).strip()
        if not t:
            return None
        fmts = ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']
        for f in fmts:
            try:
                return datetime.strptime(t, f)
            except Exception:
                pass
        return None

    def _execute_rule(self, rule_id: str, extracted_fields: List[ExtractedFieldResult]) -> Tuple[str, Optional[str]]:
        """
        执行具体合规规则校验（增强版）
        返回：(result: pass/fail, reason: 失败原因)
        """
        # 转换字段为字典便于查询
        field_dict = {f.fieldName: f.fieldValue for f in extracted_fields}

        try:
            if rule_id == "AMOUNT_LOGIC_001":
                raw_q = field_dict.get("quantity")
                raw_p = field_dict.get("unitPrice")
                raw_a = field_dict.get("amount")
                q = self._norm_num(raw_q)
                p = self._norm_num(raw_p)
                a = self._norm_num(raw_a)
                def fmt(v: Optional[float]):
                    return f"{v:.2f}" if isinstance(v, (int, float)) and v is not None else "解析失败"
                if q is None or p is None or a is None:
                    reason = (
                        f"quantity: 原值={raw_q}, 解析={fmt(q)}；"
                        f"unitPrice: 原值={raw_p}, 解析={fmt(p)}；"
                        f"amount: 原值={raw_a}, 解析={fmt(a)}；"
                        "支持格式示例：'81.40'、'$ 81.40'、'162,79'（逗号作小数点或千分位）"
                    )
                    return "fail", reason
                c = q * p
                diff = abs(a - c)
                passed = diff <= 0.01
                reason = (
                    f"quantity: 原值={raw_q}, 解析={fmt(q)}；"
                    f"unitPrice: 原值={raw_p}, 解析={fmt(p)}；"
                    f"amount: 原值={raw_a}, 解析={fmt(a)}；"
                    f"计算: {fmt(q)} × {fmt(p)} = {fmt(c)}，实际={fmt(a)}，差值={fmt(diff)}，阈值=0.01 → "
                    + ("通过" if passed else "不通过")
                )
                return ("pass", reason) if passed else ("fail", reason)

            elif rule_id == "DATE_VALID_002":
                dstr = field_dict.get("issueDate")
                if not dstr:
                    return "fail", "开票日期: 原值=空 → 不通过"
                d = self._parse_date(dstr)
                if d is None:
                    return "fail", f"开票日期: 原值={dstr}, 解析=失败 → 不通过"
                if d.date() > datetime.now().date():
                    return "fail", f"开票日期: 原值={dstr}, 解析={d.strftime('%Y-%m-%d')} 晚于当前日期 → 不通过"
                return "pass", f"开票日期: 原值={dstr}, 解析={d.strftime('%Y-%m-%d')} ≤ 当前日期 → 通过"

            elif rule_id == "SELLER_BUYER_003":
                # 规则3：买卖双方信息完整性
                seller_name = field_dict.get("sellerName", "").strip()
                buyer_name = field_dict.get("buyerName", "").strip()

                if not seller_name and not buyer_name:
                    return "fail", "买卖双方: seller=空, buyer=空 → 不通过"
                elif not seller_name:
                    return "fail", f"买卖双方: seller=空, buyer={buyer_name} → 不通过"
                elif not buyer_name:
                    return "fail", f"买卖双方: seller={seller_name}, buyer=空 → 不通过"
                elif seller_name == buyer_name:
                    return "fail", f"买卖双方: seller={seller_name}, buyer={buyer_name} 相同 → 不通过"
                return "pass", f"买卖双方: seller={seller_name}, buyer={buyer_name} 均非空且不同 → 通过"

            elif rule_id == "GOODS_DESC_004":
                # 规则4：货物描述非空
                goods_desc = field_dict.get("goodsDesc", "").strip()
                if not goods_desc:
                    return "fail", "货物描述: 原值=空 → 不通过"
                elif len(goods_desc) < 5:
                    return "fail", f"货物描述: 原值={goods_desc}, 长度={len(goods_desc)} < 5 → 不通过"
                return "pass", f"货物描述: 原值={goods_desc}, 长度={len(goods_desc)} ≥ 5 → 通过"

            elif rule_id == "INVOICE_NO_FORMAT_005":
                ino = (field_dict.get("invoiceNo") or "").strip()
                if not ino:
                    return "fail", "发票号码: 原值=空 → 不通过"
                import re
                if not re.fullmatch(r"[A-Za-z0-9\-]{6,20}", ino):
                    return "fail", f"发票号码: 原值={ino}, 规则=[A-Za-z0-9-]{6,20} 不匹配 → 不通过"
                return "pass", f"发票号码: 原值={ino}, 规则匹配 → 通过"

            elif rule_id == "AMOUNT_RANGE_006":
                a = self._norm_num(field_dict.get("amount"))
                if a is None:
                    return "fail", f"发票金额: 原值={field_dict.get('amount')}, 解析=失败 → 不通过"
                if a < 0:
                    return "fail", f"发票金额: 解析={a:.2f} < 0 → 不通过"
                if a > 1000000:
                    return "fail", f"发票金额: 解析={a:.2f} > 1000000 → 不通过"
                return "pass", f"发票金额: 解析={a:.2f} 在[0, 1000000]内 → 通过"

            elif rule_id == "CONTRACT_NO_CHECK_007":
                # 规则7：合同编号关联性检查
                contract_no = field_dict.get("contractNumber", "").strip()
                if contract_no:  # 只在有合同编号时检查
                    # 合同编号格式简单校验：只允许字母、数字、横线、下划线
                    import re
                    if not re.match(r'^[A-Za-z0-9-_]+$', contract_no):
                        return "fail", f"合同编号: 原值={contract_no}, 规则=^[A-Za-z0-9-_]+$ 不匹配 → 不通过"
                    elif len(contract_no) > 50:
                        return "fail", f"合同编号: 原值={contract_no}, 长度={len(contract_no)} > 50 → 不通过"
                return "pass", f"合同编号: 原值={'空' if not contract_no else contract_no} 校验通过 → 通过"

            elif rule_id == "TAX_RATE_CHECK_008":
                tr = field_dict.get("taxRate")
                if tr is None:
                    return "pass", "税率: 原值=空（可选项） → 通过"
                v = self._norm_num(tr)
                if v is None:
                    return "fail", f"税率: 原值={tr}, 解析=失败 → 不通过"
                if not (0 <= v <= 1):
                    return "fail", f"税率: 解析={v:.4f} 不在[0,1] → 不通过"
                return "pass", f"税率: 解析={v:.4f} 在[0,1]内 → 通过"

            else:
                return "fail", f"未知合规规则：{rule_id}"

        except Exception as e:
            logger.error(
                f"执行合规规则{rule_id}异常: {str(e)}",
                extra={"processId": "", "algorithmTaskId": ""}
            )
            return "fail", f"规则执行异常：{str(e)}"


    async def handle_compliance_callback(self, callback_data: dict, db: Session) -> dict:
        """
        处理合规回调数据
        """
        try:
            logger.info(
                "收到合规回调数据",
                extra={"processId": callback_data.get('processId', ''), "algorithmTaskId": callback_data.get('algorithmTaskId', '')}
            )
            
            # 这里可以添加实际的回调处理逻辑
            # 例如：验证数据、更新数据库、触发后续流程等
            
            return {"code": 0, "message": "回调处理成功"}
            
        except Exception as e:
            logger.error(
                f"处理合规回调异常: {str(e)}",
                extra={"processId": callback_data.get('processId', ''), "algorithmTaskId": callback_data.get('algorithmTaskId', '')}
            )
            return {"code": 1, "message": f"处理失败: {str(e)}"}

# 初始化合规服务实例
compliance_service = ComplianceService()