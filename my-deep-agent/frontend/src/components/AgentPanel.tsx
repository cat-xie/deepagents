import { useCallback, useEffect, useState } from "react";
import type { AgentConfig } from "../types";

const EMPTY_FORM = {
  name: "",
  description: "",
  system_prompt: "",
  tools: "",
  enabled: true,
};

export default function AgentPanel() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [editing, setEditing] = useState<AgentConfig | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const res = await fetch("/api/agents");
    setAgents(await res.json());
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setMessage("");
  };

  const openEdit = (agent: AgentConfig) => {
    setEditing(agent);
    setForm({
      name: agent.name,
      description: agent.description,
      system_prompt: agent.system_prompt,
      tools: agent.tools.join("\n"),
      enabled: agent.enabled,
    });
    setMessage("");
  };

  const save = async () => {
    setLoading(true);
    setMessage("");
    const body = {
      name: form.name,
      description: form.description,
      system_prompt: form.system_prompt,
      tools: form.tools.split("\n").map((t) => t.trim()).filter(Boolean),
      enabled: form.enabled,
    };
    try {
      const url = editing ? `/api/agents/${editing.id}` : "/api/agents";
      const method = editing ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setMessage(editing ? "Agent 已更新并重建" : "Agent 已创建并重建");
      setEditing(null);
      setForm(EMPTY_FORM);
      await load();
    } catch (e) {
      setMessage(`错误: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("确定删除此 Agent？")) return;
    await fetch(`/api/agents/${id}`, { method: "DELETE" });
    await load();
    setMessage("Agent 已删除");
  };

  return (
    <div className="manage-panel">
      <div className="manage-header">
        <h2>Agent 管理</h2>
        <button className="btn btn-primary" style={{ width: "auto" }} onClick={openCreate}>
          + 新建 Agent
        </button>
      </div>

      {message && <div className="manage-message">{message}</div>}

      <div className="manage-grid">
        <div className="manage-list">
          {agents.map((a) => (
            <div className="manage-card" key={a.id}>
              <div className="manage-card-header">
                <strong>{a.name}</strong>
                <span className={`badge ${a.enabled ? "badge-green" : "badge-gray"}`}>
                  {a.enabled ? "启用" : "禁用"}
                </span>
              </div>
              <p className="manage-card-desc">{a.description}</p>
              <div className="manage-card-tools">
                工具: {a.tools.length ? a.tools.join(", ") : "无"}
              </div>
              <div className="manage-card-actions">
                <button className="btn" onClick={() => openEdit(a)}>编辑</button>
                <button className="btn btn-danger" onClick={() => remove(a.id)}>删除</button>
              </div>
            </div>
          ))}
        </div>

        <div className="manage-form">
          <h3>{editing ? `编辑: ${editing.name}` : "新建 Agent"}</h3>
          <label>名称</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="如：数据分析师"
          />
          <label>描述（主 Agent 委派时参考）</label>
          <input
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="负责..."
          />
          <label>System Prompt</label>
          <textarea
            rows={6}
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          />
          <label>工具（每行一个，格式 module:function）</label>
          <textarea
            rows={3}
            value={form.tools}
            onChange={(e) => setForm({ ...form, tools: e.target.value })}
            placeholder={"skills.researcher_skill:research_topic"}
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            启用
          </label>
          <button className="btn btn-primary" disabled={loading || !form.name} onClick={save}>
            {loading ? "保存中..." : editing ? "更新" : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}
