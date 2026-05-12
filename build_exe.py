# -*- coding: utf-8 -*-
"""
WiFi Auto Reconnect 打包脚本
将 Python 脚本打包为独立 Windows EXE 文件
"""

import subprocess
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MAIN_SCRIPT = SCRIPT_DIR / "wifi_auto_reconnect.py"
DIST_DIR = SCRIPT_DIR / "dist"
SPEC_FILE = SCRIPT_DIR / "wifi_auto_reconnect.spec"

def build():
    print("=" * 50)
    print("  WiFi Auto Reconnect - 打包为 EXE")
    print("=" * 50)

    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("⏳ 正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])
        print("✅ PyInstaller 安装完成")

    # 检查依赖
    print("\n⏳ 确保依赖已安装...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "pystray>=0.19",
        "Pillow>=10.0",
        "-q"
    ])

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=WiFiAutoReconnect",
        "--onefile",           # 单文件
        "--windowed",          # 无控制台窗口（GUI模式）
        "--noconfirm",         # 覆盖输出
        f"--distpath={DIST_DIR}",
        f"--workpath={SCRIPT_DIR / 'build'}",
        f"--specpath={SCRIPT_DIR}",
        "--icon=NONE",         # 使用内置图标
        str(MAIN_SCRIPT)
    ]

    print(f"\n📦 开始打包...")
    print(f"   源文件: {MAIN_SCRIPT}")
    print(f"   输出目录: {DIST_DIR}")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = DIST_DIR / "WiFiAutoReconnect.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n{'='*50}")
            print(f"  ✅ 打包成功！")
            print(f"  📁 文件: {exe_path}")
            print(f"  📏 大小: {size_mb:.1f} MB")
            print(f"{'='*50}")
            print(f"\n使用方法:")
            print(f"  双击 WiFiAutoReconnect.exe 即可运行")
            print(f"  程序会在系统托盘显示图标")
            print(f"  右键托盘图标可查看状态、手动切换 WiFi 或退出")
        else:
            print("\n❌ 未找到输出文件")
    else:
        print(f"\n❌ 打包失败 (返回码: {result.returncode})")

if __name__ == "__main__":
    build()
