import type { ChatMessage } from "../types";
import ReactMarkdown from "react-markdown";

interface Props {
  message: ChatMessage;
}

const ROLE_LABELS: Record<string, string> = {
  user: "你",
  assistant: "Agent",
  tool: "工具",
  system: "系统",
};

const ROLE_ICONS: Record<string, string> = {
  user: "👤",
  assistant: "🤖",
  tool: "🔧",
};

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className="message">
      <div className="message-header">
        <div className={`message-avatar ${message.role}`}>
          {ROLE_ICONS[message.role] || "💬"}
        </div>
        <span className="message-role">
          {message.tool_name || ROLE_LABELS[message.role] || message.role}
        </span>
      </div>

      <div className="message-body">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>

      {message.tool_calls && message.tool_calls.length > 0 && (
        <div className="tool-calls">
          {message.tool_calls.map((tc, i) => (
            <div className="tool-card" key={i}>
              <div className="tool-card-name">{tc.name}</div>
              <div className="tool-card-args">
                {JSON.stringify(tc.args, null, 2)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
