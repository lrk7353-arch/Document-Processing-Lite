// src/components/ResultPanel.tsx
import { useState, type FC } from "react";

type ExtractedField = {
  fieldName: string;
  fieldValue: string | number;
  confidence?: number;
};

// 风险级别类型
type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;

type ComplianceItem = {
  label: string;
  pass: boolean;
  desc?: string;
  code?: string;
  severity?: string; // low | medium | high | string
  riskLevel?: RiskLevel;
};

// 风险警报类型
type RiskAlert = {
  alertId: string;
  alertType: string;
  riskLevel: RiskLevel;
  ruleId: string;
  ruleName: string;
  description: string;
  recommendation?: string;
  confidence?: number;
  timestamp?: number;
};

type ComplianceBlock = {
  overallResult?: string; // pass | fail | ...
  overallRiskLevel?: RiskLevel;
  riskAlerts?: RiskAlert[];
  riskCount?: {
    high: number;
    medium: number;
    low: number;
  };
  items?: ComplianceItem[];
};

export type PanelResult = {
  fileName: string;
  fileType: string;
  fileSize?: number;
  storagePath?: string;
  md5?: string;
  previewUrl?: string;
  extractedFields: ExtractedField[];
  compliance?: ComplianceBlock;
};

const bytesTo = (n?: number) =>
  typeof n === "number" ? `${(n / 1024 / 1024).toFixed(2)} MB` : "—";

const badgeTone = (ok: boolean) =>
  ok
    ? "border-green-200 bg-green-50 text-green-700"
    : "border-red-200 bg-red-50 text-red-700";

const overallTone = (res?: string) => {
  const r = String(res || "").toLowerCase();
  if (!r) return "text-gray-500";
  return r === "pass" ? "text-green-600" : "text-red-600";
};

const sevBadge = (sev?: string) => {
  const s = String(sev || "").toLowerCase();
  if (!s) return "border-gray-200 bg-gray-50 text-gray-600";
  if (s.includes("high")) return "border-red-200 bg-red-50 text-red-700";
  if (s.includes("medium")) return "border-amber-200 bg-amber-50 text-amber-700";
  if (s.includes("low")) return "border-sky-200 bg-sky-50 text-sky-700";
  return "border-gray-200 bg-gray-50 text-gray-600";
};

// 风险级别样式函数
const riskLevelStyle = (level?: RiskLevel) => {
  const l = String(level || "").toUpperCase();
  if (l.includes("CRITICAL")) return "border-red-200 bg-red-50 text-red-700 font-medium";
  if (l.includes("HIGH")) return "border-orange-200 bg-orange-50 text-orange-700 font-medium";
  if (l.includes("MEDIUM")) return "border-amber-200 bg-amber-50 text-amber-700";
  if (l.includes("LOW")) return "border-blue-200 bg-blue-50 text-blue-700";
  return "border-gray-200 bg-gray-50 text-gray-600";
};

const ResultPanel: FC<{ result: PanelResult }> = ({ result }) => {
  const {
    fileName,
    fileType,
    fileSize,
    storagePath,
    md5,
    previewUrl,
    extractedFields = [],
    compliance,
  } = result;
  const [showPreview, setShowPreview] = useState(false);

  return (
    <div className="space-y-6">
      {/* 基本信息 */}
      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-white p-4">
          <div className="text-sm text-gray-500 mb-2">文件信息</div>
          <div className="space-y-1 text-sm">
            <div>
              <span className="text-gray-500">文件名：</span>
              <span className="text-gray-900">{fileName || "—"}</span>
            </div>
            <div>
              <span className="text-gray-500">类型：</span>
              <span className="text-gray-900">{fileType || "—"}</span>
            </div>
            <div>
              <span className="text-gray-500">大小：</span>
              <span className="text-gray-900">{bytesTo(fileSize)}</span>
            </div>
            <div>
              <span className="text-gray-500">存储路径：</span>
              <span className="text-gray-900 break-all">{storagePath || "—"}</span>
            </div>
            <div>
              <span className="text-gray-500">MD5：</span>
              <span className="text-gray-900 break-all">{md5 || "—"}</span>
            </div>
          </div>
        </div>

        {/* 提取结果（动态字段） */}
        <div className="rounded-lg border bg-white p-4">
          <div className="text-sm text-gray-500 mb-2">提取字段</div>
          {extractedFields.length === 0 ? (
            <div className="text-sm text-gray-500">暂无数据</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {extractedFields.map((f, i) => (
                <div key={`${f.fieldName}-${i}`} className="rounded-md border p-3">
                  <div className="text-xs text-gray-500">{f.fieldName}</div>
                  <div className="text-sm text-gray-900 mt-0.5 wrap-break-word">
                    {String(f.fieldValue)}
                  </div>
                  {typeof f.confidence === "number" && (
                    <div className="mt-1 text-[11px] text-gray-500">
                      置信度：{Math.round(f.confidence * 100)}%
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <div className="text-sm text-gray-500 mb-2">文件预览</div>
        {fileType.startsWith("image") && previewUrl ? (
          <div className="space-y-2">
            <img
              src={previewUrl}
              alt={fileName}
              className="h-32 w-auto rounded border cursor-zoom-in"
              onClick={() => setShowPreview(true)}
            />
            <div className="flex items-center gap-3">
              <a
                href={previewUrl}
                download={fileName}
                className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100"
              >
                下载
              </a>
              <button
                className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100"
                onClick={() => setShowPreview(true)}
              >
                放大查看
              </button>
            </div>
          </div>
        ) : previewUrl ? (
          <div className="space-y-2">
            {fileType.includes("pdf") ? (
              <iframe src={previewUrl} className="h-40 w-full rounded border" />
            ) : (
              <img src={previewUrl} alt={fileName} className="h-32 w-auto rounded border" />
            )}
            <div className="flex items-center gap-3">
              <a href={previewUrl} target="_blank" rel="noreferrer" className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100">在新标签预览</a>
              <a href={previewUrl} download={fileName} className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100">下载</a>
              <button className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100" onClick={() => setShowPreview(true)}>全屏查看</button>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-500">暂无预览</div>
        )}
      </section>

      {showPreview && previewUrl && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center" onClick={() => setShowPreview(false)}>
          <div className="w-[92vw] h-[86vh] bg-white rounded-lg shadow-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-2 border-b">
              <div className="text-sm font-medium text-gray-700 truncate">{fileName}</div>
              <div className="flex items-center gap-2">
                <a href={previewUrl} download={fileName} className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100">下载</a>
                <button className="inline-flex items-center px-2 py-1 rounded border text-xs bg-gray-50 hover:bg-gray-100" onClick={() => setShowPreview(false)}>关闭</button>
              </div>
            </div>
            <div className="w-full h-full flex items-center justify-center bg-gray-50">
              {fileType.startsWith("image") ? (
                <img src={previewUrl} alt={fileName} className="max-w-full max-h-full object-contain" />
              ) : (
                <iframe src={previewUrl} className="w-full h-full" />
              )}
            </div>
          </div>
        </div>
      )}

      {/* 风险评估摘要 */}
      {compliance?.overallRiskLevel && (
        <section className="rounded-lg border bg-white p-4">
          <div className="text-sm text-gray-500 mb-3">风险评估摘要</div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div className="rounded-md border p-3 bg-blue-50 border-blue-200">
              <div className="text-xs text-blue-700 mb-1">总体风险级别</div>
              <div className="flex items-center gap-2">
                <span 
                  className={`inline-flex items-center rounded border px-2 py-0.5 text-sm font-medium ${riskLevelStyle(
                    compliance.overallRiskLevel
                  )}`}
                >
                  {compliance.overallRiskLevel}
                </span>
              </div>
            </div>
            
            {compliance.riskCount && (
              <>
                <div className="rounded-md border p-3 bg-orange-50 border-orange-200">
                  <div className="text-xs text-orange-700 mb-1">高风险项目</div>
                  <div className="text-xl font-semibold text-orange-700">{compliance.riskCount.high || 0}</div>
                </div>
                <div className="rounded-md border p-3 bg-amber-50 border-amber-200">
                  <div className="text-xs text-amber-700 mb-1">中风险项目</div>
                  <div className="text-xl font-semibold text-amber-700">{compliance.riskCount.medium || 0}</div>
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {/* 风险警报详情 */}
      {compliance?.riskAlerts && compliance.riskAlerts.length > 0 && (
        <section className="rounded-lg border bg-white p-4">
          <div className="text-sm text-gray-500 mb-3">风险警报</div>
          <div className="space-y-3">
            {compliance.riskAlerts.map((alert, idx) => (
              <div key={`${alert.alertId || alert.ruleId}-${idx}`} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span 
                    className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${riskLevelStyle(
                      alert.riskLevel
                    )}`}
                  >
                    {alert.riskLevel}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {alert.ruleName || alert.alertType || "风险警报"}
                  </span>
                  {alert.confidence !== undefined && (
                    <span className="ml-auto inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] text-gray-700 bg-gray-50 border-gray-200">
                      置信度：{Math.round(alert.confidence * 100)}%
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-700 mb-2">{alert.description}</div>
                {alert.recommendation && (
                  <div className="text-xs text-blue-700 bg-blue-50 p-2 rounded">
                    <span className="font-medium">建议：</span>{alert.recommendation}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 合规检查（带“描述”） */}
      <section className="rounded-lg border bg-white p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm text-gray-500">合规检查</div>
          <div className="flex items-center gap-3">
            <div className={`text-sm font-medium ${overallTone(compliance?.overallResult)}`}>
              总体结论：{compliance?.overallResult ?? "—"}
            </div>
            {compliance?.overallRiskLevel && (
              <span 
                className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${riskLevelStyle(
                  compliance.overallRiskLevel
                )}`}
              >
                风险：{compliance.overallRiskLevel}
              </span>
            )}
          </div>
        </div>

        {!compliance?.items || compliance.items.length === 0 ? (
          <div className="text-sm text-gray-500">暂无规则明细</div>
        ) : (
          <div className="space-y-3">
            {compliance.items.map((it, idx) => (
              <div key={`${it.label}-${idx}`} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${badgeTone(
                      it.pass
                    )}`}
                  >
                    {it.pass ? "通过" : "未通过"}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {it.label || "规则"}
                  </span>

                  {it.code && (
                    <span className="ml-auto inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] text-gray-700 bg-gray-50 border-gray-200">
                      {it.code}
                    </span>
                  )}
                  {it.severity && (
                    <span
                      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] ${sevBadge(
                        it.severity
                      )}`}
                    >
                      严重级别：{String(it.severity)}
                    </span>
                  )}
                  {it.riskLevel && (
                    <span
                      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] ${riskLevelStyle(
                        it.riskLevel
                      )}`}
                    >
                      风险：{String(it.riskLevel)}
                    </span>
                  )}
                </div>

                <div className="mt-2 text-xs leading-5 text-gray-600 wrap-break-word">
                  {it.desc && String(it.desc).trim().length > 0 ? it.desc : "（无详情）"}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default ResultPanel;
