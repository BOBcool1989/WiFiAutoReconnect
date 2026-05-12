@echo off
chcp 65001 >nul 2>&1
title WiFi Auto Reconnect
mode con cols=60 lines=20

:: ═══════════════════════════════════════
::  WiFi 自动重连工具 (BAT 版)
::  兼容 Win7 32位 / 无需任何依赖
:: ═══════════════════════════════════════

setlocal enabledelayedexpansion

:: ── 配置 ──
set "POLL_INTERVAL=10"
set "PING_HOST=223.5.5.5"
set "RECONNECT_DELAY=3"
set "FAIL_THRESHOLD=2"

:: ── 路径 ──
set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%SCRIPT_DIR%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: 日期格式化（兼容 Win7）
for /f "tokens=1-3 delims=/" %%a in ('echo %date:~0,10%') do set "TODAY=%%a%%b%%c"
for /f "tokens=1-3 delims=:." %%a in ('echo %time%') do set "NOW=%%a%%b%%c"
set "LOG_FILE=%LOG_DIR%\wifi_%TODAY%.log"

:: ═══════════════════════════════════════
::  主逻辑
:: ═══════════════════════════════════════

call :log "========================================"
call :log "WiFi Auto Reconnect (BAT) 启动"
call :log "轮询间隔: %POLL_INTERVAL%s | 检测目标: %PING_HOST%"
call :log "日志文件: %LOG_FILE%"
call :log "========================================"

:: 启动时加载 WiFi 列表
call :load_profiles

set /a fail_count=0
set /a round=0
set "skip_ssid="

:main_loop
    set /a round+=1

    :: 检测网络
    call :check_internet is_online

    if "!is_online!"=="1" (
        set /a fail_count=0
        set "skip_ssid="
        :: 获取当前 SSID
        call :get_current_ssid current_ssid
        call :log "[OK] 网络正常 | WiFi: !current_ssid!"
        title WiFi Reconnect - 在线: !current_ssid!
        :: 每 30 轮刷新一次 WiFi 列表
        set /a mod=round %% 30
        if !mod!==0 call :load_profiles
    ) else (
        set /a fail_count+=1
        call :get_current_ssid current_ssid
        call :log "[WARN] 检测到断网 (!fail_count!/%FAIL_THRESHOLD%) | WiFi: !current_ssid!"
        title WiFi Reconnect - 断网中 (!fail_count!次)

        if !fail_count! GEQ %FAIL_THRESHOLD% (
            call :log "[ACT] 确认断网，开始自动重连..."
            call :try_reconnect
            set /a fail_count=0
        )
    )

    :: 等待
    ping -n %POLL_INTERVAL% 127.0.0.1 >nul 2>&1
    goto main_loop

:: ═══════════════════════════════════════
::  检测网络连通性
:: ═══════════════════════════════════════
:check_internet
    set "%~1=0"
    :: 方法1: ping 公网 DNS
    ping -n 1 -w 3000 %PING_HOST% >nul 2>&1
    if !errorlevel!==0 (
        set "%~1=1"
        exit /b
    )
    :: 方法2: ping 备用地址 (114 DNS)
    ping -n 1 -w 3000 114.114.114.114 >nul 2>&1
    if !errorlevel!==0 (
        set "%~1=1"
        exit /b
    )
    :: 方法3: ping 百度
    ping -n 1 -w 3000 baidu.com >nul 2>&1
    if !errorlevel!==0 (
        set "%~1=1"
        exit /b
    )
    exit /b

:: ═══════════════════════════════════════
::  获取当前 WiFi SSID
:: ═══════════════════════════════════════
:get_current_ssid
    set "%~1="
    for /f "tokens=2 delims=:" %%a in ('netsh wlan show interfaces 2^>nul ^| findstr /b /c:"    SSID"') do (
        set "ssid=%%a"
        set "ssid=!ssid: =!"
        if not "!ssid!"=="" set "%~1=!ssid!"
    )
    exit /b

:: ═══════════════════════════════════════
::  加载已保存的 WiFi 配置文件
:: ═══════════════════════════════════════
:load_profiles
    set "WIFI_LIST="
    set /a wifi_count=0
    for /f "tokens=2 delims=:" %%a in ('netsh wlan show profiles 2^>nul ^| findstr /c:"All User Profile" /c:"所有用户配置文件"') do (
        set "name=%%a"
        :: 去掉首尾空格
        for /f "tokens=* delims= " %%b in ("!name!") do set "name=%%b"
        if not "!name!"=="" (
            if "!WIFI_LIST!"=="" (
                set "WIFI_LIST=!name!"
            ) else (
                set "WIFI_LIST=!WIFI_LIST!|!name!"
            )
            set /a wifi_count+=1
        )
    )
    call :log "[INFO] 已加载 !wifi_count! 个已保存WiFi"
    exit /b

:: ═══════════════════════════════════════
::  自动重连逻辑
:: ═══════════════════════════════════════
:try_reconnect
    if "!WIFI_LIST!"=="" call :load_profiles
    if "!WIFI_LIST!"=="" (
        call :log "[ERROR] 没有已保存的WiFi，无法重连"
        exit /b
    )

    call :get_current_ssid cur_ssid

    :: 遍历所有已保存的 WiFi
    set "remaining=!WIFI_LIST!"
    set /a tried=0

    :next_wifi
    if "!remaining!"=="" goto :reconnect_done

    :: 取第一个（|分隔）
    for /f "tokens=1 delims=|" %%s in ("!remaining!") do set "target=%%s"

    :: 去掉已遍历的那个
    set "tail=!remaining!"
    set "found=0"
    set "new_remaining="
    for %%s in ("!remaining:|= !") do (
        set "item=%%~s"
        if !found!==0 (
            set "found=1"
        ) else (
            if "!new_remaining!"=="" (
                set "new_remaining=!item!"
            ) else (
                set "new_remaining=!new_remaining!|!item!"
            )
        )
    )
    set "remaining=!new_remaining!"

    :: 跳过当前已连但无网的、以及刚试过失败的
    if "!target!"=="!cur_ssid!" goto :next_wifi
    if "!target!"=="!skip_ssid!" goto :next_wifi

    set /a tried+=1
    call :log "[TRY] (!tried!) 正在连接: !target!"
    title WiFi Reconnect - 尝试: !target!

    :: 执行连接
    netsh wlan connect name="!target!" >nul 2>&1
    if !errorlevel!==0 (
        :: 等待连接稳定
        ping -n %RECONNECT_DELAY% 127.0.0.1 >nul 2>&1
        :: 验证网络
        call :check_internet recheck
        if "!recheck!"=="1" (
            call :log "[OK] 成功连接: !target! - 网络已恢复"
            title WiFi Reconnect - 已连接: !target!
            set "skip_ssid="
            exit /b
        ) else (
            call :log "[WARN] 连上 !target! 但仍无网络，继续尝试"
            set "skip_ssid=!target!"
        )
    ) else (
        call :log "[FAIL] 连接失败: !target!"
        set "skip_ssid=!target!"
    )

    ping -n %RECONNECT_DELAY% 127.0.0.1 >nul 2>&1
    goto :next_wifi

    :reconnect_done
    if !tried!==0 (
        call :log "[WARN] 没有可用的备用WiFi"
    ) else (
        call :log "[WARN] 所有WiFi均已尝试失败，等待下一轮"
    )
    :: 重置 skip 以便下轮重试
    set "skip_ssid="
    exit /b

:: ═══════════════════════════════════════
::  日志函数
:: ═══════════════════════════════════════
:log
    set "msg=%~1"
    :: 时间戳
    for /f "tokens=1-3 delims=:. " %%a in ('echo %time%') do set "ts=%%a:%%b:%%c"
    echo [%ts%] %msg%
    echo [%date% %ts%] %msg% >> "%LOG_FILE%"

    :: 日志文件大小控制 (>5MB 则截断保留最后500行)
    for %%F in ("%LOG_FILE%") do (
        if %%~zF GTR 5242880 (
            more +500 "%LOG_FILE%" > "%LOG_FILE%.tmp" 2>nul
            move /y "%LOG_FILE%.tmp" "%LOG_FILE%" >nul 2>&1
        )
    )
    exit /b
