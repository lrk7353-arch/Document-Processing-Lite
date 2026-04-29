import React from "react";

export type StageKey =
  | "idle" | "uploading" | "uploaded"
  | "parsing" | "extracting" | "checking"
  | "completed";

const STAGES: { key: StageKey; label: string }[] = [
  { key: "idle",       label: "空闲" },
  { key: "uploading",  label: "上传中" },
  { key: "uploaded",   label: "上传完成" },
  { key: "parsing",    label: "解析中" },
  { key: "extracting", label: "模型提取" },
  { key: "checking",   label: "合规检查" },
  { key: "completed",  label: "处理完成" },
];

export default function StageStepper({ current }: { current: StageKey }) {
  const idx = Math.max(0, STAGES.findIndex(s => s.key === current));
  return (
    <div className="bg-white p-4 rounded-lg shadow-sm">
      <div className="flex flex-wrap items-center gap-2 md:gap-4 text-xs md:text-sm">
        {STAGES.map((s, i) => {
          const active = i === idx;
          const done   = i < idx;
          const base =
            "w-6 h-6 mr-1 md:mr-2 rounded-full flex items-center justify-center " +
            (active ? "bg-indigo-600 text-white"
              : done ? "bg-green-100 text-green-700"
              : "bg-gray-200 text-gray-600");
          return (
            <React.Fragment key={s.key}>
              <div className="flex items-center">
                <span className={base}>{i + 1}</span>
                <span className={active ? "text-indigo-600 font-medium" : "text-gray-600"}>
                  {s.label}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <span className="text-gray-300 text-xs">→</span>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
