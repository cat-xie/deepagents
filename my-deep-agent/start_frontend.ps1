# 使用 Node.js 完整路径启动前端（不依赖 PATH）
$NodeDir = "C:\Program Files\nodejs"
$env:Path = "$NodeDir;$env:Path"
Set-Location "$PSScriptRoot\frontend"

Write-Host ""
Write-Host " Deep Agent Frontend" -ForegroundColor Cyan
Write-Host " http://localhost:5173" -ForegroundColor Green
Write-Host ""

& "$NodeDir\npm.cmd" run dev
