# PossibleKey

PossibleKey 是一个 Windows 键鼠映射小工具。你可以把一个键盘按键、鼠标左键、右键、中键或滚轮动作映射成另一个快捷键组合或鼠标动作，例如按 `S` 触发 `Ctrl+C`，或按 `Space` 触发鼠标左键单击。

## 安装运行

```powershell
cd D:\study\code\codex\PossibleKey
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m possiblekey
```

也可以双击 `run.bat` 启动。

> 如果键盘拦截、鼠标监听或模拟输入不生效，请用管理员权限运行终端或 `run.bat`。

## 使用方式

1. 点击左侧捕获框，按一个键，或点击鼠标左键、右键、中键、侧键、滚轮。
2. 点击右侧捕获框，输入要触发的快捷键组合或鼠标动作，然后点击「确认目标」。右侧支持重复动作，例如按两次 `C` 会记录为 `C + C`；为了避免系统长按连发误录，重复动作需要松开后再按一次。
3. 点击「添加映射」保存配置。
4. 在下方列表里使用双态开关单独开启或关闭映射：开关在右侧表示开启，在左侧表示关闭。
5. 顶部「全部映射」开关可以一次性开启或关闭所有映射。

配置会自动保存到项目目录下的 `mappings.json`。

## 打包

项目已经可以打包成 exe。打包后的配置文件会保存在 exe 同目录。为了让全局键鼠映射更稳定，exe 会请求管理员权限。
