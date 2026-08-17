"""CLI 入口：交互式命令行模式。"""

from core.agent_app import (
    agent,
    new_session_id,
    run_config,
    stream_agent,
    resume_agent,
    extract_interrupt,
)
from skills.researcher_skill import read_researcher_memory
from skills.writer_skill import read_writer_memory

CONVERSATION_ID = new_session_id()
RUN_CONFIG = run_config(CONVERSATION_ID)

if __name__ == "__main__":
    print("=" * 50)
    print("👥 带记忆的研究-写作协作系统 (Tavily)")
    print(f"📌 会话 ID: {CONVERSATION_ID}（重启后用这个 ID 能继续对话）")
    print("=" * 50)
    print("输入 'exit' 退出 / 'new' 开新会话\n")

    while True:
        topic = input("👤 你: ")
        if topic.lower() in ["exit", "quit", "退出"]:
            print("👋 再见！")
            break
        if topic.lower() == "new":
            CONVERSATION_ID = new_session_id()
            RUN_CONFIG = run_config(CONVERSATION_ID)
            print(f"\n📌 新会话 ID: {CONVERSATION_ID}\n")
            continue

        print("\n⏳ 处理中...\n")
        try:
            last_state = {}
            for event in stream_agent(CONVERSATION_ID, topic):
                if event["type"] == "message":
                    pass
                elif event["type"] == "todos":
                    last_state["todos"] = event["data"]
                elif event["type"] == "rubric":
                    last_state["_rubric_status"] = event["data"]["status"]
                    last_state["_rubric_iterations"] = event["data"]["iterations"]

            state = agent.get_state(RUN_CONFIG)
            while state.next:
                interrupt = extract_interrupt(state)
                if not interrupt:
                    break

                print("🔔 需要审批的工具调用：")
                for ar in interrupt["action_requests"]:
                    print(f"   工具: {ar['name']}")
                    print(f"   参数: {ar['args']}")

                choice = input("是否批准？(y=批准 / n=拒绝): ").strip().lower()
                approved = choice in ["y", "yes", "批准"]

                for event in resume_agent(CONVERSATION_ID, approved):
                    if event["type"] == "todos":
                        last_state["todos"] = event["data"]
                    elif event["type"] == "rubric":
                        last_state["_rubric_status"] = event["data"]["status"]
                        last_state["_rubric_iterations"] = event["data"]["iterations"]

                state = agent.get_state(RUN_CONFIG)

            from core.agent_app import get_session_messages

            msgs = get_session_messages(CONVERSATION_ID)
            todos = last_state.get("todos", [])
            if todos:
                print("\n📋 任务清单：")
                for t in todos:
                    status = t.get("status", "?")
                    status_icon = {
                        "pending": "⏳",
                        "in_progress": "🔧",
                        "completed": "✅",
                    }.get(status, "❓")
                    print(f"   {status_icon} [{status}] {t.get('content', '')}")

            rubric_status = last_state.get("_rubric_status")
            rubric_iters = last_state.get("_rubric_iterations", 0)
            if rubric_status:
                status_map = {
                    "satisfied": "✅ 达标",
                    "needs_revision": "🔧 需要修改",
                    "max_iterations_reached": "⚠️ 达到最大重试次数",
                    "failed": "❌ 评估失败",
                    "grader_error": "❌ grader 出错",
                }
                status_text = status_map.get(rubric_status, rubric_status)
                print(f"\n🎯 自评结果: {status_text}（迭代 {rubric_iters} 次）")

            print("\n📝 最终回答:")
            if msgs:
                print(msgs[-1]["content"])

            print("\n" + "-" * 50)
            print("\n📖 当前研究员记忆（来自 SQLite Store）：")
            print(read_researcher_memory(limit=10))
            print("\n📖 当前作家记忆（来自 SQLite Store）：")
            print(read_writer_memory(limit=10))
            print("-" * 50 + "\n")

        except Exception as e:
            print(f"❌ 出错: {e}\n")
