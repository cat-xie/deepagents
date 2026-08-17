import sys
sys.path.append('.')

from skills.writer_skill import write_summary, read_writer_memory

def create_writer_agent():
    # 启动时从 store 读取历史写作记忆，注入到 system_prompt
    memory_text = read_writer_memory(limit=20)

    return {
        "name": "作家",
        "description": "负责根据提供的材料，撰写简短的总结，并记住自己的写作历史。",
        "system_prompt": f"""你是一个作家。你的工作流程：
        1. 收到材料和主题后，调用 write_summary 生成总结
        2. 记忆会自动记录你的写作历史

        ## 你的历史写作记录
        {memory_text}

        ## 注意
        - 写作风格要简洁明了
        - 如果之前写过类似主题，可以参考历史风格保持一致
        """,
        "tools": [write_summary],
    }
