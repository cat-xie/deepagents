@echo off
REM 使用 Node.js 完整路径启动，不依赖 PATH
set "NODE=C:\Program Files\nodejs"
set "PATH=%NODE%;%PATH%"
cd /d %~dp0frontend

echo.
echo  Deep Agent Frontend
echo  http://localhost:5173
echo.

"%NODE%\npm.cmd" run dev
pause
