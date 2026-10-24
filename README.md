# 青截 WX_OCR

类似微信操作方式的桌面截图工具：拖动框选、复制到剪贴板、保存 PNG、本地中英文 OCR、全局快捷键和系统托盘。

## 安装运行

推荐 Python 3.11 或 3.12（64 位），在**自己的桌面电脑**运行：

```bash
python -m venv .venv
```

Windows PowerShell 激活：`.venv\Scripts\Activate.ps1`；macOS / Linux 激活：`source .venv/bin/activate`。

```bash
python -m pip install -r requirements.txt
python main.py
```

默认快捷键：`Ctrl+Alt+A` 截图，`Ctrl+Alt+O` 框选后直接识字。在主窗口输入新组合并点击“保存快捷键”，立即替换旧绑定，并在下次启动时恢复。支持 Ctrl、Alt、Shift、Cmd 加字母、数字或 F1–F12，例如 macOS 可设 `Cmd+Shift+A`。两个功能不可使用相同组合。

## 使用

- 按快捷键或点击“开始截图”，在鼠标所在屏幕拖动框选区域。多显示器时先把鼠标移到目标屏幕；暂不支持跨屏框选。
- 框选后点击工具栏：复制、保存或识别文字；Enter 复制，Esc / 右键取消。拖动可重新框选。
- “截图识字”会在框选完成后自动识别；也可以打开现有图片。结果可编辑、复制。
- OCR 在后台运行，使用 RapidOCR 自带的中英文 ONNX 模型，无需 API Key；正常安装后识别不需要网络，不上传图片。不自动保存截图或识别历史。
- 有托盘的系统中，关闭窗口会常驻托盘；托盘菜单“退出”完全结束。没有托盘时关闭窗口直接退出。尚不包含标注或滚动长截图。

## 开机启动（Windows）

在主窗口“设置”中勾选“开机启动”，立即注册当前用户的启动项，无需管理员权限。取消勾选即可移除。首次运行默认关闭，界面每次从 Windows 注册表读取实际状态，不会仅保存一个无效的勾选标记。系统拒绝操作时会提示失败并恢复勾选状态。

下次登录 Windows 后，程序会后台启动并常驻托盘，不弹出主窗口；双击托盘图标可打开。若托盘不可用，会显示主窗口。手动双击程序仍正常显示窗口。便携版需保留程序目录；移动目录后请取消再重新勾选，使启动路径更新。Windows“启动应用”中的系统禁用策略仍会影响是否实际启动。macOS/Linux 上该选项置灰。

## 识别性能

启动后会在后台加载和预热 OCR，界面显示“OCR 已就绪”后即可使用。模型常驻内存，默认模式避免把小截图一律放大到短边 736 像素，ONNX 推理线程也作了限制。保留原有中英文模型和方向识别。对很小或密集的文字，可勾选“精细识别”恢复放大检测；该模式较慢。界面显示每次从点击到完成的实际耗时。速度依图片和硬件而变，未与微信作同机对比。

Windows 打包流程会比较旧版/优化版在相同中英文图片上的预热后耗时，并检查文字未丢失。报告随便携包提供；这组样例不代表所有截图或所有电脑。

## 系统说明

- **Windows**：建议 Windows 10/11。若其他应用以管理员运行，快捷键可能需要同等权限。被占用的组合可能无法触发，请换一个组合；监听启动成功不代表系统保证独占该组合。
- **macOS**：给启动程序（终端、Python 或打包后的应用）授予“屏幕录制”“辅助功能”，必要时授予“输入监控”权限，并重新启动应用。
- **Linux**：建议 X11。Wayland 的全局按键和直接屏幕读取通常受限，本项目未实现 portal 截图；出现问题请切换 X11 会话。某些发行版需要安装 Qt xcb 所需的系统库。
- 支持按屏幕像素比例裁剪高分屏截图；没有真实桌面的云端无法完成系统截图与全局按键的端到端验证。
- 快捷键设置使用 Qt QSettings 存储在当前用户配置中。OCR 正在运行时暂时禁止换图或再次截图，避免结果与图片错配。

## 打包为桌面程序

在目标操作系统中执行（Windows 的 exe 必须在 Windows 上打包）：

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --windowed --name QingJie --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-submodules pynput main.py
```

产物在 `dist/QingJie/`，需分发整个文件夹；包括 OCR 模型，体积较大。当前提供源码与打包命令，未生成或签名 Windows/macOS 安装包。

## 验证

```bash
python -m pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

Windows PowerShell 请先执行 `$env:QT_QPA_PLATFORM="offscreen"`，再执行 `python -m pytest -q`。
