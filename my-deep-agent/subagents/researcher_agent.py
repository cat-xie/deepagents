import sys
sys.path.append('.')

from skills.researcher_skill import research_topic, read_researcher_memory

def create_researcher_agent():
    # 启动时从 store 读取历史搜索记忆，注入到 system_prompt
    # 这样研究员知道自己之前搜过什么，避免重复搜索、能关联历史
    memory_text = read_researcher_memory(limit=20)

    return {
        "name": "研究员",
        "description": "负责搜索互联网，查找给定主题的最新信息，并记住自己的搜索历史。",
        "system_prompt": f"""你是一个研究员。你的工作流程：
        1. 用户给主题后，先调用 research_topic 搜索
        2. 搜索完成后，把结果返回
        3. 不需要额外操作，记忆会自动记录

        ## 你的历史搜索记录
        {memory_text}

        ## 注意
        - 如果用户问的主题和最近搜过的类似，可以参考历史结果，不必重复搜索
        - 搜索时关键词要精准，避免无效搜索
        """,
        "tools": [research_topic],
    }
