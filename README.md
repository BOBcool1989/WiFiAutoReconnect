# WiFi Auto Reconnect

Windows WiFi 自动重连工具。当检测到网络断开时，自动遍历已保存密码的 WiFi 网络尝试重连。

## 功能

- 🔄 **自动检测** - 每 10 秒轮询网络连通性（HTTP + ping 双保险）
- 📶 **自动重连** - 断网后自动遍历所有已保存 WiFi 逐一尝试连接
- 🖥️ **系统托盘** - 最小化到系统托盘，右键菜单可查看状态、手动切换 WiFi
- 📝 **日志记录** - 自动记录网络状态变化，方便排查问题

## 使用方法

### 直接运行（需要 Python 环境）

```bash
pip install pystray Pillow
python wifi_auto_reconnect.py
```

### 使用打包好的 EXE

从 [Releases](https://github.com/BOBcool1989/WiFiAutoReconnect/releases) 下载 `WiFiAutoReconnect.exe`，双击运行即可。

### 开机自启

1. 按 `Win+R`，输入 `shell:startup` 回车
2. 将 `WiFiAutoReconnect.exe` 的快捷方式放入打开的文件夹

## 自行打包

```bash
pip install pystray Pillow pyinstaller
python build_exe.py
```

打包后的 EXE 在 `dist/` 目录下。

## 前提条件

- Windows 10/11
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
