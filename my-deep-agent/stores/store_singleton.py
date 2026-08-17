"""Store 单例：skills 和 subagents 通过这里访问全局 store 实例。

用法：
    # agent.py 初始化时设置
    from stores.store_singleton import set_store
    set_store(my_store)

    # skills 里读取
    from stores.store_singleton import get_store
    store = get_store()
    store.put(("default", "researcher"), "key", {...})
"""
from __future__ import annotations

from langgraph.store.base import BaseStore

_store: BaseStore | None = None


def set_store(store: BaseStore) -> None:
    """初始化全局 store（agent.py 启动时调用一次）"""
    global _store
    _store = store


def get_store() -> BaseStore | None:
    """获取全局 store（skills/subagents 里调用）"""
    return _store
