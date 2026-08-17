"""Agent 初始化与运行逻辑，供 CLI 和 Web API 共用。"""

import importlib
import os
import sqlite3
import uuid

from langchain.agents.middleware import TodoListMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from backends.docker_sandbox import DockerSandboxBackend
from core.agent_registry import get_agent_registry
from core.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_MODEL,
    PROJECT_ROOT,
    SKILL_SOURCES,
    USE_DOCKER_SANDBOX,
)
from core.skill_service import seed_default_skills, sync_skills_to_backend
from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware import RubricMiddleware
from skills.skill_installer import install_skill_for_agent, list_skills_for_agent
from stores.sqlite_store import SqliteStore
from stores.store_singleton import set_store

DEFAULT_RUBRIC = """
任务完成标准：
1. 回复必须使用中文
2. 如果任务涉及写文件，文件必须已成功写入指定路径
3. 回复内容必须直接回应用户请求，不能只说"已完成"而不给出具体内容
4. 如果是写作类任务（笑话/诗歌/报告），内容不少于 50 字
"""

AGENTS_MD = """
# 项目记忆

## 协作规范
- 研究员负责搜索，作家负责写作
- 先研究员后作家，按顺序执行
- 所有结果用中文回复
- 遇到没有合适 Skill 的任务，可使用 install_skill 工具安装新 Skill
"""

FS_PERMISSIONS = [
    FilesystemPermission(operations=["write"], paths=["/output/**"], mode="allow"),
    FilesystemPermission(operations=["read"], paths=["/output/**"], mode="allow"),
    FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="deny"),
    FilesystemPermission(operations=["write"], paths=["/AGENTS.md"], mode="interrupt"),
    FilesystemPermission(operations=["write"], paths=["/skills/**/*.py"], mode="interrupt"),
    FilesystemPermission(operations=["write"], paths=["/subagents/**/*.py"], mode="interrupt"),
    FilesystemPermission(operations=["write"], paths=["/skill_library/**"], mode="allow"),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="interrupt"),
]

SYSTEM_PROMPT = """你是一个研究协调员。根据任务复杂度选择不同的执行路径：

## 路径 A：简单任务（不需要联网搜索的任务）
例如：写个笑话、写首短诗、做个简单总结、生成示例文本等。
- 直接使用 `write_file` 工具把内容写到 `output/` 目录下即可。
- 不要调用子Agent，不要使用 `write_todos`。

## 路径 B：复杂任务（需要联网搜索 + 写作的报告类任务）
例如：调研某主题并写报告、分析某个新闻事件等。
1. **使用 `write_todos` 工具**，将任务分解为具体步骤。
2. 按计划执行：先委派给"研究员"子Agent，获取结果后再委派给"作家"子Agent。
3. 作家返回内容后，**由你亲自使用 `write_file` 工具**，将报告保存到 `output/` 目录下。
4. 任务完成后，向用户汇报最终结果和文件保存路径。

## Skill 系统
- 系统已加载 skill_library/ 中的 Skill，可通过 read_file 读取 SKILL.md 获取详细指导。
- 若现有 Skill 不足以完成任务，使用 `list_available_skills` 查看已有 Skill。
- 若需要新 Skill，使用 `install_skill_for_agent` 工具安装（name 用小写英文连字符，description 简述用途，instructions 写详细步骤）。

## 通用规则
- 所有回复使用中文。
- 写文件时使用相对路径 `output/文件名.txt`。
- 文件名要语义清晰。
"""


class TaskResult(BaseModel):
    summary: str = Field(description="任务执行的简短摘要")
    file_path: str = Field(description="产出文件路径，无则为空")
    success: bool = Field(description="是否成功")
    detail: str = Field(description="补充说明")


_backend = None
_checkpointer = None
_store = None
_agent = None


def _write_agents_md():
    with open(PROJECT_ROOT / "AGENTS.md", "w", encoding="utf-8") as f:
        f.write(AGENTS_MD)


def _init_backend():
    global _backend
    if USE_DOCKER_SANDBOX:
        _backend = DockerSandboxBackend(
            image="python:3.11-slim-bookworm",
            memory_limit_mb=1024,
            cpu_quota=50000,
            network_disabled=False,
        )
    else:
        backend = FilesystemBackend(root_dir=str(PROJECT_ROOT))
        os.makedirs(PROJECT_ROOT / "output", exist_ok=True)
        _backend = backend
    return _backend


def _load_tool(spec: str):
    module_name, func_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def _build_subagents():
    registry = get_agent_registry()
    subagents = []
    for record in registry.list_all(enabled_only=True):
        tools = []
        for spec in record.tools:
            try:
                tools.append(_load_tool(spec))
            except (ImportError, AttributeError) as e:
                print(f"[AgentFactory] 跳过工具 {spec}: {e}")
        if not tools:
            continue
        subagents.append(record.to_subagent_dict(tools))
    return subagents


def create_agent_instance():
    global _checkpointer, _store, _agent

    _write_agents_md()
    seed_default_skills()

    model = ChatOpenAI(
        model=DASHSCOPE_MODEL,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        temperature=0.1,
        extra_body={"enable_thinking": False},
    )

    checkpoint_conn = sqlite3.connect(
        str(PROJECT_ROOT / "checkpoints.db"), check_same_thread=False
    )
    memory_conn = sqlite3.connect(
        str(PROJECT_ROOT / "memories.db"), check_same_thread=False
    )

    _checkpointer = SqliteSaver(checkpoint_conn)
    _store = SqliteStore(conn=memory_conn)
    set_store(_store)

    project_backend = _init_backend()
    sync_skills_to_backend(project_backend)
    subagents = _build_subagents()

    _agent = create_deep_agent(
        model=model,
        tools=[install_skill_for_agent, list_skills_for_agent],
        subagents=subagents,
        skills=SKILL_SOURCES,
        **({"memory": ["AGENTS.md"]} if not USE_DOCKER_SANDBOX else {}),
        backend=project_backend,
        **({"permissions": FS_PERMISSIONS} if not USE_DOCKER_SANDBOX else {}),
        interrupt_on={"edit_file": True},
        checkpointer=_checkpointer,
        store=_store,
        middleware=[
            TodoListMiddleware(),
            RubricMiddleware(model=model, max_iterations=2),
        ],
        system_prompt=SYSTEM_PROMPT,
    )

    return _agent, _checkpointer, _store


def rebuild_agent():
    """Agent/Skill 变更后重建实例。"""
    global _backend, _agent
    if _backend and hasattr(_backend, "stop_and_remove"):
        try:
            _backend.stop_and_remove()
        except Exception:
            pass
    _backend = None
    create_agent_instance()
    print("[AgentApp] Agent 已重建")


create_agent_instance()
agent = _agent
checkpointer = _checkpointer
store = _store


def new_session_id() -> str:
    return str(uuid.uuid4())[:8]


def run_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def extract_interrupt(state) -> dict | None:
    if not state.next:
        return None
    task = state.tasks[0]
    hitl_request = task.interrupts[0].value
    return {"action_requests": hitl_request.get("action_requests", [])}


def serialize_message(msg) -> dict:
    role = getattr(msg, "type", "unknown")
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    elif role == "tool":
        role = "tool"

    content = getattr(msg, "content", "")
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        content = "\n".join(text_parts)

    result = {"role": role, "content": str(content) if content else ""}

    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        result["tool_calls"] = [
            {"name": tc.get("name", ""), "args": tc.get("args", {})}
            for tc in tool_calls
        ]

    tool_name = getattr(msg, "name", None)
    if tool_name:
        result["tool_name"] = tool_name

    return result


def get_session_messages(session_id: str) -> list[dict]:
    state = agent.get_state(run_config(session_id))
    if not state or not state.values:
        return []
    messages = state.values.get("messages", [])
    return [serialize_message(m) for m in messages]


def stream_agent(session_id: str, user_message: str):
    config = run_config(session_id)
    messages_input = {
        "messages": [{"role": "user", "content": user_message}],
        "rubric": DEFAULT_RUBRIC,
    }

    last_msg_count = len(get_session_messages(session_id))

    for event in agent.stream(messages_input, config=config, stream_mode="values"):
        state_messages = event.get("messages", [])
        if len(state_messages) > last_msg_count:
            for msg in state_messages[last_msg_count:]:
                yield {"type": "message", "data": serialize_message(msg)}
            last_msg_count = len(state_messages)

        todos = event.get("todos")
        if todos:
            yield {"type": "todos", "data": todos}

        rubric_status = event.get("_rubric_status")
        if rubric_status:
            yield {
                "type": "rubric",
                "data": {
                    "status": rubric_status,
                    "iterations": event.get("_rubric_iterations", 0),
                },
            }

    state = agent.get_state(config)
    interrupt = extract_interrupt(state)
    if interrupt:
        yield {"type": "interrupt", "data": interrupt}


def resume_agent(session_id: str, approved: bool):
    config = run_config(session_id)
    state = agent.get_state(config)
    interrupt = extract_interrupt(state)
    if not interrupt:
        return

    decision = {"type": "approve" if approved else "reject"}
    response = {"decisions": [decision for _ in interrupt["action_requests"]]}

    last_msg_count = len(get_session_messages(session_id))

    for event in agent.stream(Command(resume=response), config=config, stream_mode="values"):
        state_messages = event.get("messages", [])
        if len(state_messages) > last_msg_count:
            for msg in state_messages[last_msg_count:]:
                yield {"type": "message", "data": serialize_message(msg)}
            last_msg_count = len(state_messages)

        todos = event.get("todos")
        if todos:
            yield {"type": "todos", "data": todos}

        rubric_status = event.get("_rubric_status")
        if rubric_status:
            yield {
                "type": "rubric",
                "data": {
                    "status": rubric_status,
                    "iterations": event.get("_rubric_iterations", 0),
                },
            }

    state = agent.get_state(config)
    interrupt = extract_interrupt(state)
    if interrupt:
        yield {"type": "interrupt", "data": interrupt}
