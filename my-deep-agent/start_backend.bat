@echo off
REM 使用 deep-agent-env 环境启动后端，避免包装错 Python 环境
call C:\Users\xieheng\miniconda3\Scripts\activate.bat deep-agent-env
cd /d %~dp0
python -m uvicorn api.server:app --reload --port 8000
