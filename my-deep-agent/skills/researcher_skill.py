import time
from tavily import TavilyClient

# 初始化 Tavily 客户端（无密钥模式）
tavily = TavilyClient()

# 研究员记忆的 namespace（以后多用户改成 (user_id, "researcher")）
RESEARCHER_NS = ("default", "researcher")


def read_researcher_memory(limit: int = 20) -> str:
    """从 store 读取研究员的历史搜索记录，格式化成文本。

    用于注入到 system_prompt，让研究员知道自己之前搜过什么。
    """
    from stores.store_singleton import get_store

    store = get_store()
    if not store:
        return "（store 未初始化，暂无历史记录）"

    items = store.search(RESEARCHER_NS, limit=limit)
    if not items:
        return "暂无历史记录"

    lines = []
    for it in items:
        ts = it.value.get("timestamp", "?")
        topic = it.value.get("topic", "?")
        count = it.value.get("result_count", "?")
        lines.append(f"[{ts}] 搜索了 '{topic}'，找到 {count} 条结果")
    return "\n".join(lines)


def write_researcher_memory(topic: str, result_count: int) -> None:
    """把一次搜索记录写入 store。

    替代之前的 open("memories/researcher_memory.txt", "a") 方案。
    key 用时间戳保证唯一；value 是结构化 JSON。
    """
    from stores.store_singleton import get_store

    store = get_store()
    if not store:
        return  # store 没初始化时静默跳过（兼容旧模式）

    from datetime import datetime
    store.put(
        RESEARCHER_NS,
        key=f"search-{int(time.time() * 1000)}",  # 毫秒时间戳防重复
        value={
            "topic": topic,
            "result_count": result_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    )


def research_topic(topic: str) -> str:
    """使用 Tavily 搜索主题，并记录到 store 记忆"""
    print(f"🔍 [研究员] 正在使用 Tavily 搜索: {topic}")

    try:
        response = tavily.search(query=topic, max_results=5)
        results = response.get("results", [])

        if not results:
            return f"未找到关于 '{topic}' 的信息。"

        formatted_results = []
        for r in results[:5]:
            title = r.get("title", "无标题")
            content = r.get("content", "")[:300]
            url = r.get("url", "")
            formatted_results.append(f"【{title}】\n{content}...\n来源: {url}\n---")

        summary = "\n".join(formatted_results)
        result_text = f"关于 '{topic}' 的搜索结果：\n{summary}"

        # 写入 store（替代旧的 write_researcher_memory 文件方案）
        write_researcher_memory(topic, len(results))
        return result_text

    except Exception as e:
        error_msg = f"Tavily 搜索出错: {e}"
        print(f"❌ {error_msg}")
        return error_msg
