import type { ViewMode } from "../types";

interface Props {
  sessionId: string;
  connected: boolean;
  status: string;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
  onNewSession: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  idle: "就绪",
  processing: "处理中...",
  waiting_approval: "等待审批",
  error: "出错",
};

const NAV_ITEMS: { id: ViewMode; label: string; icon: string }[] = [
  { id: "chat", label: "对话", icon: "💬" },
  { id: "agents", label: "Agent", icon: "🤖" },
  { id: "skills", label: "Skill", icon: "📦" },
];

export default function Sidebar({
  sessionId,
  connected,
  status,
  view,
  onViewChange,
  onNewSession,
}: Props) {
  const dotClass =
    status === "processing" || status === "waiting_approval"
      ? "processing"
      : connected
        ? "connected"
        : "disconnected";

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🧠</div>
          <span>Deep Agent</span>
        </div>
      </div>

      <div className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${view === item.id ? "active" : ""}`}
            onClick={() => onViewChange(item.id)}
          >
            <span>{item.icon}</span> {item.label}
          </button>
        ))}
      </div>

      {view === "chat" && (
        <div className="sidebar-section">
          <button className="btn btn-primary" onClick={onNewSession}>
            + 新会话
          </button>
        </div>
      )}

      <div className="sidebar-section">
        <div className="sidebar-label">会话 ID</div>
        <div className="session-id">{sessionId}</div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">连接</div>
        <div className="sidebar-status">
          <span className={`status-dot ${dotClass}`} />
          {connected ? "已连接" : "未连接"}
          {view === "chat" && status !== "idle" && status !== "error"
            ? ` · ${STATUS_LABELS[status] || status}`
            : ""}
        </div>
      </div>
    </aside>
  );
}
