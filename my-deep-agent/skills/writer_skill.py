import time
from datetime import datetime

# 作家记忆的 namespace
WRITER_NS = ("default", "writer")


def read_writer_memory(limit: int = 20) -> str:
    """从 store 读取作家的历史写作记录，格式化成文本。

    用于注入到 system_prompt，让作家知道自己之前写过什么。
    """
    from stores.store_singleton import get_store

    store = get_store()
    if not store:
        return "（store 未初始化，暂无历史记录）"

    items = store.search(WRITER_NS, limit=limit)
    if not items:
        return "暂无历史记录"

    lines = []
    for it in items:
        ts = it.value.get("timestamp", "?")
        topic = it.value.get("topic", "?")
        action = it.value.get("action", "撰写")
        lines.append(f"[{ts}] {action}了 '{topic}'")
    return "\n".join(lines)


def write_writer_memory(topic: str, action: str = "撰写") -> None:
    """把一次写作记录写入 store。

    替代之前的 open("memories/writer_memory.txt", "a") 方案。
    """
    from stores.store_singleton import get_store

    store = get_store()
    if not store:
        return  # store 没初始化时静默跳过

    store.put(
        WRITER_NS,
        key=f"write-{int(time.time() * 1000)}",
        value={
            "topic": topic,
            "action": action,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    )


def write_summary(material: str, topic: str) -> str:
    """根据材料生成总结，并记录到 store 记忆"""
    print(f"✍️ [作家] 正在为 '{topic}' 撰写总结...")

    summary = f"关于 '{topic}' 的总结：\n"
    summary += f"基于资料：{material[:200]}...\n"
    summary += "结论：这是一个值得进一步探索的主题。"

    # 写入 store（替代旧的 write_writer_memory 文件方案）
    write_writer_memory(topic, "撰写总结")
    return summary
