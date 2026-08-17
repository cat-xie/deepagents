"""Skill 安装工具：供主 Agent 根据用户需求自动安装 Skill。"""

from core.skill_service import install_skill, list_skills, match_skills


def install_skill_for_agent(name: str, description: str, instructions: str) -> str:
    """根据用户需求安装新 Skill。

    Args:
        name: Skill 名称，小写英文和连字符，如 web-scraping
        description: 一句话描述 Skill 用途（最多 200 字）
        instructions: Skill 详细说明，包含何时使用、步骤、注意事项（Markdown 格式）

    Returns:
        安装结果消息
    """
    return install_skill(name, description, instructions)


def list_skills_for_agent() -> str:
    """列出当前已安装的所有 Skill，返回名称和描述。"""
    skills = list_skills()
    if not skills:
        return "当前没有已安装的 Skill。可使用 install_skill_for_agent 安装新 Skill。"
    lines = ["已安装的 Skill："]
    for s in skills:
        lines.append(f"- {s.name}: {s.description}")
    return "\n".join(lines)


def suggest_skills_for_task(task: str) -> str:
    """根据任务描述推荐可能相关的 Skill。"""
    matched = match_skills(task)
    if not matched:
        return f"没有找到与「{task}」匹配的 Skill，建议使用 install_skill_for_agent 安装新 Skill。"
    lines = [f"与「{task}」可能相关的 Skill："]
    for s in matched:
        lines.append(f"- {s.name}: {s.description}")
    return "\n".join(lines)
