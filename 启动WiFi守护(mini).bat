@echo off
:: 最小化启动 WiFi 自动重连
:: 双击此文件即可后台运行（窗口自动最小化）

if "%1"=="min" goto :run

:: 用 mshta 实现最小化启动（兼容 Win7）
mshta vbscript:CreateObject("WScript.Shell").Run("cmd /c ""%~f0"" min",7,True)(window.close)
exit

:run
call "%~dp0wifi_auto_reconnect.bat"
