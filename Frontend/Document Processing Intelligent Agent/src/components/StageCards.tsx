export type DetailLine = {
  label: string;
  value: string;
  /** 行样式：默认灰；ok=绿，danger=红，warn=黄，muted=浅灰 */
  tone?: "muted" | "ok" | "danger" | "warn";
};

export type StageCard = {
  status: string;
  progress: number; // 0-100
  lines: DetailLine[];
};

export type StageCardsData = {
  upload: StageCard;
  parse: StageCard;
  model: StageCard;
  compliance: StageCard;
};

const toneCls: Record<NonNullable<DetailLine["tone"]>, string> = {
  muted: "text-gray-500",
  ok: "text-green-600",
  danger: "text-red-600",
  warn: "text-amber-600",
};

type CardProps = {
  title: string;
  status: string;
  progress: number;
  color: "indigo" | "amber" | "purple" | "green";
  lines: DetailLine[];
};

const colorBar: Record<CardProps["color"], string> = {
  indigo: "bg-indigo-600",
  amber: "bg-amber-500",
  purple: "bg-purple-500",
  green: "bg-green-600",
};

function Card({ title, status, progress, color, lines }: CardProps) {
  const bar = colorBar[color];
  const pct = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <div className="bg-white rounded-lg shadow-sm p-5 border border-gray-100">
      <div className="flex justify-between items-start mb-3">
        <h3 className="font-medium">{title}</h3>
        <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600">
          {status || "—"}
        </span>
      </div>

      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-3">
        <div className={`h-full ${bar}`} style={{ width: `${pct}%` }} />
      </div>

      <ul className="space-y-1 text-xs">
        {lines.map((l, i) => (
          <li key={i} className="flex justify-between gap-2">
            <span className="text-gray-600">{l.label}</span>
            <span className={`truncate ${l.tone ? toneCls[l.tone] : "text-gray-900"}`}>
              {l.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function StageCards({ data, currentStage }: { data: StageCardsData; currentStage: string }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <Card
        title="文件上传"
        status={data.upload.status}
        progress={data.upload.progress}
        color="indigo"
        lines={data.upload.lines}
      />
      <Card
        title="文件解析"
        status={data.parse.status}
        progress={data.parse.progress}
        color="amber"
        lines={data.parse.lines}
      />
      <Card
        title="模型提取"
        status={data.model.status}
        progress={data.model.progress}
        color="purple"
        lines={data.model.lines}
      />
      <Card
        title="合规检查"
        status={data.compliance.status}
        progress={data.compliance.progress}
        color="green"
        lines={data.compliance.lines}
      />
    </div>
  );
}
