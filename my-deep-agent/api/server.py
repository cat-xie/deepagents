"""FastAPI Web 服务：聊天 + Agent/Skill 管理 API。"""

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import core.agent_app as agent_app
from core.agent_registry import AgentRecord, get_agent_registry
from core.skill_service import delete_skill, get_skill, install_skill, list_skills
from skills.researcher_skill import read_researcher_memory
from skills.writer_skill import read_writer_memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Deep Agent Control UI", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas ----------

class SessionResponse(BaseModel):
    session_id: str


class MemoryResponse(BaseModel):
    researcher: str
    writer: str


class AgentCreate(BaseModel):
    name: str
    description: str
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[str]] = None
    enabled: Optional[bool] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    tools: list[str]
    enabled: bool
    created_at: str
    updated_at: str


class SkillCreate(BaseModel):
    name: str
    description: str
    instructions: str


class SkillResponse(BaseModel):
    name: str
    description: str
    path: str


class RebuildResponse(BaseModel):
    status: str
    message: str


def _agent_to_response(record: AgentRecord) -> AgentResponse:
    return AgentResponse(
        id=record.id,
        name=record.name,
        description=record.description,
        system_prompt=record.system_prompt,
        tools=record.tools,
        enabled=record.enabled,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# ---------- Health & Sessions ----------

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agent": "ready",
        "model": os.getenv("DASHSCOPE_MODEL", "qwen-plus"),
    }


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session():
    return SessionResponse(session_id=agent_app.new_session_id())


@app.get("/api/sessions/{session_id}/messages")
async def session_messages(session_id: str):
    return {
        "session_id": session_id,
        "messages": agent_app.get_session_messages(session_id),
    }


@app.get("/api/memory", response_model=MemoryResponse)
async def get_memory():
    return MemoryResponse(
        researcher=read_researcher_memory(limit=10),
        writer=read_writer_memory(limit=10),
    )


# ---------- Agent CRUD ----------

@app.get("/api/agents", response_model=list[AgentResponse])
async def list_agents():
    registry = get_agent_registry()
    return [_agent_to_response(a) for a in registry.list_all()]


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    record = get_agent_registry().get(agent_id)
    if not record:
        raise HTTPException(404, "Agent 不存在")
    return _agent_to_response(record)


@app.post("/api/agents", response_model=AgentResponse)
async def create_agent(body: AgentCreate):
    record = AgentRecord(
        id="",
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        tools=body.tools,
        enabled=body.enabled,
    )
    created = get_agent_registry().create(record)
    agent_app.rebuild_agent()
    return _agent_to_response(created)


@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, body: AgentUpdate):
    updated = get_agent_registry().update(
        agent_id,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        tools=body.tools,
        enabled=body.enabled,
    )
    if not updated:
        raise HTTPException(404, "Agent 不存在")
    agent_app.rebuild_agent()
    return _agent_to_response(updated)


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not get_agent_registry().delete(agent_id):
        raise HTTPException(404, "Agent 不存在")
    agent_app.rebuild_agent()
    return {"status": "deleted", "id": agent_id}


@app.post("/api/agents/rebuild", response_model=RebuildResponse)
async def rebuild_agents():
    agent_app.rebuild_agent()
    return RebuildResponse(status="ok", message="Agent 已重建")


# ---------- Skill CRUD ----------

@app.get("/api/skills", response_model=list[SkillResponse])
async def list_all_skills():
    return [
        SkillResponse(name=s.name, description=s.description, path=s.path)
        for s in list_skills()
    ]


@app.get("/api/skills/{name}")
async def get_skill_detail(name: str):
    skill = get_skill(name)
    if not skill:
        raise HTTPException(404, "Skill 不存在")
    return {
        "name": skill.name,
        "description": skill.description,
        "path": skill.path,
        "content": skill.content,
    }


@app.post("/api/skills", response_model=SkillResponse)
async def create_skill(body: SkillCreate):
    result = install_skill(body.name, body.description, body.instructions)
    skill = get_skill(body.name.lower().replace(" ", "-"))
    if not skill:
        skills = list_skills()
        skill = skills[-1] if skills else None
    if not skill:
        raise HTTPException(500, result)
    return SkillResponse(name=skill.name, description=skill.description, path=skill.path)


@app.delete("/api/skills/{name}")
async def remove_skill(name: str):
    if not delete_skill(name):
        raise HTTPException(404, "Skill 不存在")
    return {"status": "deleted", "name": name}


# ---------- WebSocket ----------

@app.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    await websocket.send_json({"type": "connected", "session_id": session_id})

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            msg_type = payload.get("type")

            if msg_type == "chat":
                user_message = payload.get("message", "").strip()
                if not user_message:
                    continue

                await websocket.send_json({"type": "status", "data": "processing"})

                try:
                    for event in agent_app.stream_agent(session_id, user_message):
                        await websocket.send_json(event)
                        if event["type"] == "interrupt":
                            break

                    state = agent_app.agent.get_state(
                        {"configurable": {"thread_id": session_id}}
                    )
                    while state.next:
                        approval_raw = await websocket.receive_text()
                        approval = json.loads(approval_raw)
                        if approval.get("type") != "approve":
                            continue

                        approved = approval.get("approved", False)
                        for event in agent_app.resume_agent(session_id, approved):
                            await websocket.send_json(event)
                            if event["type"] == "interrupt":
                                break

                        state = agent_app.agent.get_state(
                            {"configurable": {"thread_id": session_id}}
                        )

                    await websocket.send_json({"type": "status", "data": "done"})

                except Exception as e:
                    await websocket.send_json({"type": "error", "data": str(e)})

            elif msg_type == "approve":
                approved = payload.get("approved", False)
                try:
                    for event in agent_app.resume_agent(session_id, approved):
                        await websocket.send_json(event)
                    await websocket.send_json({"type": "status", "data": "done"})
                except Exception as e:
                    await websocket.send_json({"type": "error", "data": str(e)})

    except WebSocketDisconnect:
        pass


_frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"
)
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
