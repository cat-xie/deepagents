import type { TodoItem } from "../types";

interface Props {
  todos: TodoItem[];
}

const STATUS_ICONS: Record<string, string> = {
  pending: "⏳",
  in_progress: "🔧",
  completed: "✅",
};

export default function TodoPanel({ todos }: Props) {
  if (todos.length === 0) return null;

  return (
    <div className="todo-panel">
      <div className="todo-panel-title">📋 任务进度</div>
      {todos.map((todo, i) => (
        <div
          className={`todo-item ${todo.status === "completed" ? "completed" : ""}`}
          key={i}
        >
          <span className="todo-icon">
            {STATUS_ICONS[todo.status] || "❓"}
          </span>
          <span>{todo.content}</span>
        </div>
      ))}
    </div>
  );
}
