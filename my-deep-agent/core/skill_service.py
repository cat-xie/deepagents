"""Skill 库管理：SKILL.md 读写 + deepagents SkillsMiddleware 集成。"""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.config import PROJECT_ROOT, SKILL_LIBRARY_DIR


@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    content: str = ""


def _ensure_library():
    SKILL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def _parse_skill_md(content: str) -> tuple[dict, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return meta, body


def _build_skill_md(name: str, description: str, body: str) -> str:
    meta = {
        "name": name,
        "description": description,
    }
    frontmatter = yaml.dump(meta, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def list_skills() -> list[SkillInfo]:
    _ensure_library()
    skills: list[SkillInfo] = []
    for skill_dir in sorted(SKILL_LIBRARY_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        content = skill_md.read_text(encoding="utf-8")
        meta, _ = _parse_skill_md(content)
        skills.append(
            SkillInfo(
                name=meta.get("name", skill_dir.name),
                description=meta.get("description", ""),
                path=str(skill_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                content=content,
            )
        )
    return skills


def get_skill(name: str) -> SkillInfo | None:
    for skill in list_skills():
        if skill.name == name:
            return skill
    return None


def install_skill(name: str, description: str, instructions: str) -> str:
    """安装新 Skill 到 skill_library/，供 Agent 按需加载。"""
    _ensure_library()
    safe_name = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    if not safe_name:
        return "错误：skill 名称无效，请使用小写英文和连字符"

    skill_dir = SKILL_LIBRARY_DIR / safe_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    body = instructions.strip()
    if not body.startswith("#"):
        body = f"# {safe_name.replace('-', ' ').title()} Skill\n\n{body}"

    skill_md = _build_skill_md(safe_name, description, body)
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    from core.agent_app import rebuild_agent

    rebuild_agent()
    return f"Skill '{safe_name}' 已安装，Agent 已重新加载。"


def delete_skill(name: str) -> bool:
    skill = get_skill(name)
    if not skill:
        return False
    skill_path = PROJECT_ROOT / skill.path
    if skill_path.exists():
        import shutil

        shutil.rmtree(skill_path)

    from core.agent_app import rebuild_agent

    rebuild_agent()
    return True


def match_skills(query: str, limit: int = 5) -> list[SkillInfo]:
    """简单关键词匹配，返回可能相关的 Skill。"""
    query_lower = query.lower()
    scored: list[tuple[int, SkillInfo]] = []
    for skill in list_skills():
        score = 0
        text = f"{skill.name} {skill.description}".lower()
        for word in query_lower.split():
            if len(word) > 1 and word in text:
                score += 1
        if score > 0:
            scored.append((score, skill))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:limit]]


def sync_skills_to_backend(backend) -> None:
    """将 host 上的 skill_library 同步到 Docker 沙箱（如适用）。"""
    if not SKILL_LIBRARY_DIR.exists():
        return
    if not hasattr(backend, "upload_files"):
        return

    files: list[tuple[str, bytes]] = []
    for root, _, filenames in os.walk(SKILL_LIBRARY_DIR):
        for filename in filenames:
            full_path = Path(root) / filename
            rel = full_path.relative_to(PROJECT_ROOT).as_posix()
            container_path = f"/workspace/{rel}"
            files.append((container_path, full_path.read_bytes()))

    if files:
        backend.upload_files(files)


def seed_default_skills():
    """初始化默认 Skill（若不存在）。"""
    _ensure_library()
    defaults = [
        (
            "web-research",
            "结构化互联网搜索与研究方法",
            """# Web Research Skill

## When to Use
- 用户需要调研某个主题
- 需要联网搜索最新信息

## Steps
1. 明确搜索关键词
2. 使用 research_topic 工具搜索
3. 整理搜索结果，标注来源
4. 输出结构化摘要
""",
        ),
        (
            "content-writing",
            "根据材料撰写报告、总结和文案",
            """# Content Writing Skill

## When to Use
- 用户需要根据材料写报告或总结
- 需要将搜索结果转化为可读文档

## Steps
1. 阅读提供的材料
2. 提取关键信息
3. 使用 write_summary 生成内容
4. 确保使用中文，结构清晰
""",
        ),
    ]
    for name, desc, body in defaults:
        skill_dir = SKILL_LIBRARY_DIR / name
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_md_path.write_text(
                _build_skill_md(name, desc, body), encoding="utf-8"
            )
