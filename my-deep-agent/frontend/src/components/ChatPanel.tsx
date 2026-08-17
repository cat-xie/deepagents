import { useEffect, useRef, useState } from "react";
import type { AgentStatus, ChatMessage, InterruptData, TodoItem } from "../types";
import MessageBubble from "./MessageBubble";
import TodoPanel from "./TodoPanel";
import ApprovalDialog from "./ApprovalDialog";

interface Props {
  messages: ChatMessage[];
  todos: TodoItem[];
  status: AgentStatus;
  interrupt: InterruptData | null;
  error: string | null;
  onSend: (text: string) => void;
  onApprove: (approved: boolean) => void;
}

const SUGGESTIONS = [
  "写一个关于程序员的冷笑话",
  "调研 2026 年 AI Agent 发展趋势并写报告",
  "写一首关于代码的短诗",
];

export default function ChatPanel({
  messages,
  todos,
  status,
  interrupt,
  error,
  onSend,
  onApprove,
}: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isProcessing = status === "processing" || status === "waiting_approval";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, todos, status]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isProcessing) return;
    onSend(text);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  return (
    <div className="main-content">
      <div className="chat-header">
        <h1>Control UI</h1>
        <div className="chat-header-status">
          {status === "processing" && (
            <>
              <span className="status-dot processing" />
              Agent 正在工作...
            </>
          )}
          {error && <span style={{ color: "var(--error)" }}>{error}</span>}
        </div>
      </div>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="messages-empty">
            <div className="messages-empty-icon">🧠</div>
            <h2>Deep Agent Control UI</h2>
            <p>
              企业级多 Agent 协作平台。输入任务，Agent 团队会自动协调完成——
              简单任务直接执行，复杂任务由研究员搜索 + 作家撰写。
            </p>
            <div className="suggestion-chips">
              {SUGGESTIONS.map((s) => (
                <button
                  className="chip"
                  key={s}
                  onClick={() => onSend(s)}
                  disabled={isProcessing}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble message={msg} key={msg.id} />)
        )}

        {status === "processing" && messages.length > 0 && (
          <div className="typing-indicator">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <TodoPanel todos={todos} />

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder="输入任务... (Enter 发送, Shift+Enter 换行)"
            rows={1}
            disabled={isProcessing}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isProcessing}
            title="发送"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <div className="input-hint">Deep Agent v0.1 · 研究员 + 作家协作</div>
      </div>

      {interrupt && (
        <ApprovalDialog interrupt={interrupt} onApprove={onApprove} />
      )}
    </div>
  );
}
