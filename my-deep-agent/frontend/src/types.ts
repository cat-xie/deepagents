export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  tool_calls?: ToolCall[];
  tool_name?: string;
}

export interface TodoItem {
  content: string;
  status: "pending" | "in_progress" | "completed";
}

export interface ActionRequest {
  name: string;
  args: Record<string, unknown>;
}

export interface InterruptData {
  action_requests: ActionRequest[];
}

export type AgentStatus = "idle" | "processing" | "waiting_approval" | "error";

export type ViewMode = "chat" | "agents" | "skills";

export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  tools: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SkillConfig {
  name: string;
  description: string;
  path: string;
  content?: string;
}

export interface WSEvent {
  type: string;
  data?: unknown;
  session_id?: string;
}
