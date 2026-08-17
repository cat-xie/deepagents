import { useCallback, useEffect, useState } from "react";
import type { SkillConfig } from "../types";

const EMPTY_FORM = { name: "", description: "", instructions: "" };

export default function SkillPanel() {
  const [skills, setSkills] = useState<SkillConfig[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const res = await fetch("/api/skills");
    setSkills(await res.json());
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/skills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(await res.text());
      setMessage("Skill 已安装，Agent 已重新加载");
      setForm(EMPTY_FORM);
      await load();
    } catch (e) {
      setMessage(`错误: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const remove = async (name: string) => {
    if (!confirm(`确定删除 Skill「${name}」？`)) return;
    await fetch(`/api/skills/${name}`, { method: "DELETE" });
    await load();
    setMessage(`Skill「${name}」已删除`);
  };

  return (
    <div className="manage-panel">
      <div className="manage-header">
        <h2>Skill 管理</h2>
        <span className="manage-hint">Agent 可根据需求自动安装 Skill，也可在此手动管理</span>
      </div>

      {message && <div className="manage-message">{message}</div>}

      <div className="manage-grid">
        <div className="manage-list">
          {skills.length === 0 ? (
            <p className="manage-empty">暂无 Skill，可在下方手动安装，或让 Agent 自动安装</p>
          ) : (
            skills.map((s) => (
              <div className="manage-card" key={s.name}>
                <div className="manage-card-header">
                  <strong>{s.name}</strong>
                </div>
                <p className="manage-card-desc">{s.description}</p>
                <div className="manage-card-tools">路径: {s.path}</div>
                <div className="manage-card-actions">
                  <button className="btn btn-danger" onClick={() => remove(s.name)}>
                    删除
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="manage-form">
          <h3>安装新 Skill</h3>
          <label>名称（小写英文连字符）</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="如：code-review"
          />
          <label>描述</label>
          <input
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="一句话说明用途"
          />
          <label>详细说明（Markdown）</label>
          <textarea
            rows={8}
            value={form.instructions}
            onChange={(e) => setForm({ ...form, instructions: e.target.value })}
            placeholder={"## When to Use\n- ...\n\n## Steps\n1. ..."}
          />
          <button
            className="btn btn-primary"
            disabled={loading || !form.name || !form.description}
            onClick={save}
          >
            {loading ? "安装中..." : "安装 Skill"}
          </button>
        </div>
      </div>
    </div>
  );
}
