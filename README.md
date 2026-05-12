# WiFi Auto Reconnect

Windows WiFi 自动重连工具。当检测到网络断开时，自动遍历已保存密码的 WiFi 网络尝试重连。

## 功能

- 🔄 **自动检测** - 每 10 秒轮询网络连通性（HTTP + ping 双保险）
- 📶 **自动重连** - 断网后自动遍历所有已保存 WiFi 逐一尝试连接
- 📝 **日志记录** - 自动记录网络状态变化，方便排查问题

## 两种版本

| | EXE 版 (Python) | BAT 版 (纯命令行) |
|--|-----------------|-------------------|
| 文件 | `WiFiAutoReconnect.exe` | `wifi_auto_reconnect.bat` |
| 兼容系统 | Win10 / Win11 | **Win7 / XP 等老系统** |
| 依赖 | 无（已打包） | **零依赖** |
| 系统托盘 | ✅ 右下角托盘图标 | ❌ 最小化到任务栏 |
| 体积 | ~25MB | **8KB** |

> 💡 **老系统用户请使用 BAT 版**，无需安装任何环境，拷贝即用。

## 使用方法

### 方式一：BAT 版（推荐 Win7/XP 用户）

零依赖，拷贝即用：

1. 下载 `wifi_auto_reconnect.bat` 和 `启动WiFi守护(mini).bat`
2. 双击 `启动WiFi守护(mini).bat` 即可运行（窗口自动最小化）
3. 也可以直接双击 `wifi_auto_reconnect.bat`（会显示命令行窗口，可实时查看状态）

### 方式二：EXE 版（Win10/11 用户）

从 [Releases](https://github.com/BOBcool1989/WiFiAutoReconnect/releases) 下载 `WiFiAutoReconnect.exe`，双击运行即可。运行后会在系统托盘显示图标，右键可查看状态、手动切换 WiFi 或退出。

### 方式三：Python 源码运行

```bash
pip install pystray Pillow
python wifi_auto_reconnect.py
```

### 开机自启

1. 按 `Win+R`，输入 `shell:startup` 回车
2. 将程序快捷方式放入打开的文件夹：
   - EXE 版：放 `WiFiAutoReconnect.exe` 的快捷方式
   - BAT 版：放 `启动WiFi守护(mini).bat` 的快捷方式

## 自行打包 EXE

```bash
pip install pystray Pillow pyinstaller
python build_exe.py
```

打包后的 EXE 在 `dist/` 目录下。

## 前提条件

- Windows 系统（Win7 及以上）
- 需要已保存过密码的 WiFi 网络（即 `netsh wlan show profiles` 能列出的）

## 工作原理

1. 每 10 秒通过 HTTP 请求（Microsoft 连接测试）和 ping（阿里 DNS 223.5.5.5）检测网络
2. 连续 2 次检测失败后确认断网
3. 获取所有已保存的 WiFi 配置文件列表
4. 排除当前已连但无网的 WiFi，逐一尝试连接其他 WiFi
5. 连接后再次验证网络是否恢复
6. 成功则继续正常监控，全部失败则等待下一轮

## License

MIT
