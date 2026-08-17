import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentStatus,
  ChatMessage,
  InterruptData,
  TodoItem,
  WSEvent,
} from "../types";

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

export function useAgentChat(sessionId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const intentionalCloseRef = useRef(false);
  const reconnectTimerRef = useRef<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<AgentStatus>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [interrupt, setInterrupt] = useState<InterruptData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    intentionalCloseRef.current = false;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/${sessionId}`);

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onclose = () => {
      setConnected(false);
      if (!intentionalCloseRef.current) {
        reconnectTimerRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      }
    };

    ws.onerror = () => {
      if (!intentionalCloseRef.current) {
        setError("WebSocket 连接失败，正在重试...");
      }
    };

    ws.onmessage = (ev) => {
      const event: WSEvent = JSON.parse(ev.data);

      switch (event.type) {
        case "connected":
          setConnected(true);
          setError(null);
          break;

        case "status":
          if (event.data === "processing") setStatus("processing");
          else if (event.data === "done") {
            setStatus("idle");
            setInterrupt(null);
          }
          break;

        case "message": {
          const msg = event.data as Omit<ChatMessage, "id">;
          setMessages((prev) => [...prev, { ...msg, id: uid() }]);
          break;
        }

        case "todos":
          setTodos(event.data as TodoItem[]);
          break;

        case "interrupt":
          setInterrupt(event.data as InterruptData);
          setStatus("waiting_approval");
          break;

        case "error":
          setError(event.data as string);
          setStatus("error");
          break;
      }
    };

    wsRef.current = ws;
  }, [sessionId]);

  useEffect(() => {
    connect();
    return () => {
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "user", content: text },
      ]);
      setError(null);
      setStatus("processing");

      wsRef.current.send(JSON.stringify({ type: "chat", message: text }));
    },
    [],
  );

  const approve = useCallback((approved: boolean) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    setInterrupt(null);
    setStatus("processing");
    wsRef.current.send(JSON.stringify({ type: "approve", approved }));
  }, []);

  const newSession = useCallback(async () => {
    const res = await fetch("/api/sessions", { method: "POST" });
    const data = await res.json();
    return data.session_id as string;
  }, []);

  return {
    connected,
    status,
    messages,
    todos,
    interrupt,
    error,
    sendMessage,
    approve,
    newSession,
  };
}
