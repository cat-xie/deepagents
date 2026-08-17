"""项目配置：从环境变量读取，供各模块共用。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_LIBRARY_DIR = PROJECT_ROOT / "skill_library"
AGENTS_DB = PROJECT_ROOT / "agents.db"

USE_DOCKER_SANDBOX = os.getenv("USE_DOCKER_SANDBOX", "true").lower() == "true"

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
DASHSCOPE_MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen-plus")
DASHSCOPE_BASE_URL = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

SKILL_SOURCES = ["/skill_library/"]
