"""Agent 注册表：SQLite 持久化，支持 UI 增删改。"""

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from core.config import AGENTS_DB, PROJECT_ROOT


@dataclass
class AgentRecord:
    id: str
    name: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    def to_subagent_dict(self, tool_objects: list):
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools": tool_objects,
        }


DEFAULT_AGENTS = [
    AgentRecord(
        id="researcher",
        name="研究员",
        description="负责搜索互联网，查找给定主题的最新信息，并记住自己的搜索历史。",
        system_prompt="""你是一个研究员。你的工作流程：
1. 用户给主题后，先调用 research_topic 搜索
2. 搜索完成后，把结果返回
3. 不需要额外操作，记忆会自动记录

## 注意
- 搜索时关键词要精准，避免无效搜索
- 如果用户问的主题和最近搜过的类似，可以参考历史结果""",
        tools=["skills.researcher_skill:research_topic"],
        enabled=True,
    ),
    AgentRecord(
        id="writer",
        name="作家",
        description="负责根据提供的材料，撰写简短的总结，并记住自己的写作历史。",
        system_prompt="""你是一个作家。你的工作流程：
1. 收到材料和主题后，调用 write_summary 生成总结
2. 记忆会自动记录你的写作历史

## 注意
- 写作风格要简洁明了
- 所有内容使用中文""",
        tools=["skills.writer_skill:write_summary"],
        enabled=True,
    ),
]


class AgentRegistry:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or AGENTS_DB)
        self._init_db()
        self._seed_defaults()

    def _conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    tools TEXT NOT NULL DEFAULT '[]',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _seed_defaults(self):
        if self.list_all():
            return
        now = datetime.now(timezone.utc).isoformat()
        for agent in DEFAULT_AGENTS:
            agent.created_at = now
            agent.updated_at = now
            self.create(agent)

    def _row_to_record(self, row) -> AgentRecord:
        return AgentRecord(
            id=row[0],
            name=row[1],
            description=row[2],
            system_prompt=row[3],
            tools=json.loads(row[4]),
            enabled=bool(row[5]),
            created_at=row[6],
            updated_at=row[7],
        )

    def list_all(self, enabled_only: bool = False) -> list[AgentRecord]:
        with self._conn() as conn:
            if enabled_only:
                rows = conn.execute(
                    "SELECT * FROM agents WHERE enabled=1 ORDER BY created_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agents ORDER BY created_at"
                ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, agent_id: str) -> AgentRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE id=?", (agent_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def create(self, record: AgentRecord) -> AgentRecord:
        now = datetime.now(timezone.utc).isoformat()
        if not record.id:
            record.id = str(uuid.uuid4())[:8]
        record.created_at = record.created_at or now
        record.updated_at = now
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO agents
                   (id, name, description, system_prompt, tools, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.name,
                    record.description,
                    record.system_prompt,
                    json.dumps(record.tools, ensure_ascii=False),
                    int(record.enabled),
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def update(self, agent_id: str, **fields) -> AgentRecord | None:
        existing = self.get(agent_id)
        if not existing:
            return None

        for key, value in fields.items():
            if value is not None and hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            conn.execute(
                """UPDATE agents SET name=?, description=?, system_prompt=?,
                   tools=?, enabled=?, updated_at=? WHERE id=?""",
                (
                    existing.name,
                    existing.description,
                    existing.system_prompt,
                    json.dumps(existing.tools, ensure_ascii=False),
                    int(existing.enabled),
                    existing.updated_at,
                    agent_id,
                ),
            )
        return existing

    def delete(self, agent_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        return cur.rowcount > 0


_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
