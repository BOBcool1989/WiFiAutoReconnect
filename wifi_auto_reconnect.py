# -*- coding: utf-8 -*-
"""
WiFi 自动重连工具 (WiFi Auto Reconnect)
- 自动检测网络连通性（默认 10 秒轮询）
- 断网时自动切换已保存的 WiFi 网络
- 系统托盘图标，可查看状态和退出
- 日志记录
"""

import os
import sys
import time
import logging
import subprocess
import threading
from datetime import datetime
from pathlib import Path

# ── 尝试导入托盘依赖 ──
try:
    from pystray import Icon, MenuItem, Menu
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("[警告] 缺少 pystray/PIL 依赖，将使用无托盘模式。安装: pip install pystray Pillow")

# ══════════════════════════════════════════════
#  配置
# ══════════════════════════════════════════════

APP_NAME = "WiFi Auto Reconnect"
POLL_INTERVAL = 10          # 轮询间隔（秒）
CHECK_URL = "http://www.msftconnecttest.com/connecttest.txt"  # Windows 默认检测地址
CHECK_TIMEOUT = 5           # 网络检测超时（秒）
RECONNECT_DELAY = 3         # 重连间隔（秒）
MAX_LOG_SIZE_MB = 5        # 日志文件最大大小(MB)

# ── 路径 ──
BASE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "wifi_reconnect.log"

# ══════════════════════════════════════════════
#  日志
# ══════════════════════════════════════════════

LOG_DIR.mkdir(exist_ok=True)


def _rotating_logger():
    """简单日志轮转：超大小则清空重新开始"""
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE_MB * 1024 * 1024:
        # 保留最后 200 行
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
            LOG_FILE.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
        except Exception:
            pass

    log = logging.getLogger("wifi_reconnect")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)

    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    log.addHandler(fh)
    log.addHandler(sh)
    return log


logger = _rotating_logger()


# ══════════════════════════════════════════════
#  网络检测
# ══════════════════════════════════════════════

def check_internet() -> bool:
    """
    检测网络是否连通。
    优先用 HTTP 请求（更准确），失败则 fallback 到 ping。
    """
    # 方法1：HTTP 请求
    try:
        import urllib.request
        req = urllib.request.Request(CHECK_URL, method='GET')
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # 方法2：ping 公网 DNS
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "3000", "223.5.5.5"],  # 阿里 DNS
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW  # type: ignore
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    return False


def get_current_ssid() -> str | None:
    """获取当前连接的 WiFi SSID"""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW  # type: ignore
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("SSID") and ":" in line:
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    return ssid
    except Exception as e:
        logger.debug(f"获取当前SSID异常: {e}")
    return None


# ══════════════════════════════════════════════
#  WiFi 管理
# ══════════════════════════════════════════════

def get_saved_wifi_profiles() -> list[str]:
    """获取所有已保存密码的 WiFi 配置文件名称列表"""
    profiles = []
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW  # type: ignore
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if "All User Profile" in line and ":" in line:
                name = line.split(":", 1)[1].strip()
                if name:
                    profiles.append(name)
    except Exception as e:
        logger.error(f"获取WiFi列表失败: {e}")
    return profiles


def connect_wifi(ssid: str) -> bool:
    """尝试连接指定 WiFi，返回是否成功"""
    try:
        logger.info(f"正在尝试连接: {ssid}")
        result = subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            capture_output=True, text=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW  # type: ignore
        )
        output = (result.stdout + result.stderr).strip()
        success = "was successfully connected" in output or "已成功完成" in output
        if success:
            logger.info(f"✅ 成功连接: {ssid}")
        else:
            logger.warning(f"❌ 连接失败: {ssid} → {output[:120]}")
        return success
    except subprocess.TimeoutExpired:
        logger.error(f"⏱ 连接超时: {ssid}")
        return False
    except Exception as e:
        logger.error(f"连接异常({ssid}): {e}")
        return False


# ══════════════════════════════════════════════
#  核心逻辑
# ══════════════════════════════════════════════

class WiFiWatcher:
    """WiFi 断网自动重连守护进程"""

    def __init__(self):
        self.running = True
        self.current_ssid: str | None = None
        self.status_text = "🔄 初始化..."
        self.fail_count = 0
        self.success_count = 0
        self.last_profiles: list[str] = []
        self._last_connected_ssid: str | None = None
        self._skip_ssid: str | None = None  # 当前已知失败的SSID，暂时跳过
        self._lock = threading.Lock()

    def get_status(self) -> str:
        return self.status_text

    def refresh_profiles(self) -> list[str]:
        """刷新已保存的 WiFi 列表"""
        profiles = get_saved_wifi_profiles()
        self.last_profiles = profiles
        logger.info(f"发现 {len(profiles)} 个已保存的 WiFi: {', '.join(profiles) if profiles else '(无)'}")
        return profiles

    def try_reconnect(self):
        """断网时的重连逻辑"""
        profiles = self.last_profiles
        if not profiles:
            profiles = self.refresh_profiles()

        if not profiles:
            logger.error("没有找到任何已保存的 WiFi 配置文件！无法自动重连。")
            self.status_text = "❌ 无可用 WiFi"
            return

        current = get_current_ssid()

        # 构建候选列表：排除当前已连但没网的、以及刚刚尝试失败的
        candidates = [p for p in profiles if p != current and p != self._skip_ssid]

        if not candidates:
            # 全部试过了，重置跳过列表再试一轮
            logger.info("所有 WiFi 都已尝试过，重置并重新开始...")
            self._skip_ssid = None
            candidates = [p for p in profiles if p != current]
            if not candidates:
                return

        # 尝试逐个连接
        for ssid in candidates:
            if not self.running:
                break
            self.status_text = f"🔄 正在尝试: {ssid}"
            if connect_wifi(ssid):
                self._skip_ssid = None
                self._last_connected_ssid = ssid
                self.fail_count = 0
                self.success_count += 1
                # 等待连接稳定
                time.sleep(RECONNECT_DELAY)
                # 验证是否真的联网了
                if check_internet():
                    self.status_text = f"✅ 已连接: {ssid}"
                    logger.info(f"🌐 网络恢复正常！当前 WiFi: {ssid}")
                    return
                else:
                    logger.warning(f"已连上 {ssid} 但仍无网络，继续尝试下一个...")
                    self._skip_ssid = ssid
            else:
                self._skip_ssid = ssid
            time.sleep(RECONNECT_DELAY)

        self.fail_count += 1
        self.status_text = f"⚠️ 所有 WiFi 均失败 (第{self.fail_count}轮)"

    def run(self):
        """主循环"""
        logger.info("=" * 50)
        logger.info(f"{APP_NAME} 启动")
        logger.info(f"轮询间隔: {POLL_INTERVAL}s | 检测地址: {CHECK_URL}")
        logger.info("=" * 50)

        # 启动时先加载 WiFi 列表
        self.refresh_profiles()
        time.sleep(2)

        consecutive_fails = 0

        while self.running:
            try:
                online = check_internet()
                ssid = get_current_ssid()
                self.current_ssid = ssid

                if online:
                    consecutive_fails = 0
                    self.fail_count = 0
                    self._skip_ssid = None
                    self.status_text = f"✅ 在线 | WiFi: {ssid or '(未连接)'}"
                    # 每 5 分钟刷新一次 WiFi 列表
                    if int(time.time()) % 300 < POLL_INTERVAL:
                        self.refresh_profiles()
                else:
                    consecutive_fails += 1
                    if consecutive_fails >= 2:  # 连续 2 次确认断网才行动（避免误判）
                        logger.warning(f"⚠️ 检测到断网 (连续{consecutive_fails}次) | 当前SSID: {ssid}")
                        self.status_text = f"⚠️ 断网中 ({consecutive_fails}次)"
                        self.try_reconnect()
                        consecutive_fails = 0  # 不管成功与否，避免频繁触发
                    else:
                        self.status_text = f"⏳ 可能断网 ({consecutive_fails}次)"

            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)

            time.sleep(POLL_INTERVAL)

        logger.info("WiFi 监控已停止")


# ══════════════════════════════════════════════
#  系统托盘
# ══════════════════════════════════════════════

def _create_tray_image() -> Image.Image:
    """生成托盘图标 (WiFi 波形)"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 绘制 WiFi 图标（简化版：三条弧线 + 一个点）
    color = (66, 133, 244, 255)  # 蓝色
    cx, cy = size // 2 + 2, size // 2 + 8

    # 三条弧线（从外到内）
    for i, r in enumerate([26, 17, 9]):
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=15, end=165, fill=color, width=3)

    # 底部圆点
    dot_r = 4
    draw.ellipse([cx - dot_r, cy - 2 - dot_r, cx + dot_r, cy - 2 + dot_r], fill=color)

    return img


class TrayApp:
    """系统托盘应用"""

    def __init__(self, watcher: WiFiWatcher):
        self.watcher = watcher
        self.icon: Icon | None = None

    def _get_status_menu_item(self):
        status = self.watcher.get_status()
        return MenuItem(text=lambda item: f"状态: {self.watcher.get_status()}", action=None, enabled=False)

    def _get_wifi_list_menu(self):
        """动态生成 WiFi 列表子菜单"""
        items = []
        for p in self.watcher.last_profiles[:10]:  # 最多显示10个
            current = " ✅" if p == self.watcher.current_ssid else ""
            items.append(MenuItem(
                text=f"{p}{current}",
                action=lambda _, s=p: connect_wifi(s),
            ))
        if not items:
            items.append(MenuItem(text="(无已保存WiFi)", action=None, enabled=False))
        return items

    def _refresh(self, icon, _):
        """刷新 WiFi 列表"""
        self.watcher.refresh_profiles()
        icon.menu = self._build_menu()

    def _open_log(self, _icon, _):
        """打开日志文件夹"""
        os.startfile(str(LOG_DIR))  # type: ignore

    def _quit(self, icon, _):
        """退出"""
        self.watcher.running = False
        icon.stop()

    def _build_menu(self):
        return Menu(
            MenuItem(text=lambda item: f"状态: {self.watcher.get_status()[:35]}", action=None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(text="📋 已保存 WiFi", action=None, enabled=False),
            *self._get_wifi_list_menu(),
            Menu.SEPARATOR,
            MenuItem(text="🔄 刷新 WiFi 列表", action=self._refresh),
            MenuItem(text="📂 打开日志文件夹", action=self._open_log),
            Menu.SEPARATOR,
            MenuItem(text="❌ 退出", action=self._quit),
        )

    def run(self):
        if not HAS_TRAY:
            logger.warning("无托盘支持，将直接运行（Ctrl+C 可退出）")
            self.watcher.run()
            return

        image = _create_tray_image()
        self.icon = Icon(APP_NAME, image, menu=self._build_menu())
        # 后台线程运行监控
        t = threading.Thread(target=self.watcher.run, daemon=True)
        t.start()
        self.icon.run_detail()


# ══════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════

def main():
    print(f"\n{'='*50}")
    print(f"  {APP_NAME}")
    print(f"  轮询间隔: {POLL_INTERVAL}s")
    print(f"  日志位置: {LOG_FILE}")
    print(f"{'='*50}\n")

    watcher = WiFiWatcher()
    app = TrayApp(watcher)

    try:
        app.run()
    except KeyboardInterrupt:
        watcher.running = False
        logger.info("用户中断，程序退出")


if __name__ == "__main__":
    main()
