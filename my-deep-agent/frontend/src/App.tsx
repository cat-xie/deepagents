import { useCallback, useState } from "react";
import { useAgentChat } from "./hooks/useAgentChat";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import AgentPanel from "./components/AgentPanel";
import SkillPanel from "./components/SkillPanel";
import type { ViewMode } from "./types";

function generateSessionId() {
  return Math.random().toString(36).slice(2, 10);
}

export default function App() {
  const [sessionId, setSessionId] = useState(generateSessionId);
  const [key, setKey] = useState(0);
  const [view, setView] = useState<ViewMode>("chat");

  const {
    connected,
    status,
    messages,
    todos,
    interrupt,
    error,
    sendMessage,
    approve,
    newSession,
  } = useAgentChat(sessionId);

  const handleNewSession = useCallback(async () => {
    const id = await newSession();
    setSessionId(id);
    setKey((k) => k + 1);
  }, [newSession]);

  return (
    <div className="app-layout" key={key}>
      <Sidebar
        sessionId={sessionId}
        connected={connected}
        status={status}
        view={view}
        onViewChange={setView}
        onNewSession={handleNewSession}
      />
      {view === "chat" && (
        <ChatPanel
          messages={messages}
          todos={todos}
          status={status}
          interrupt={interrupt}
          error={error}
          onSend={sendMessage}
          onApprove={approve}
        />
      )}
      {view === "agents" && <AgentPanel />}
      {view === "skills" && <SkillPanel />}
    </div>
  );
}
