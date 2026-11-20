# PadOverlay 假装用手柄玩游戏

假装用手柄玩游戏，实际是键盘 / 鼠标在操作（**只可视化高亮，不注入虚拟手柄**）。

Pretend you're on a gamepad — it's really keyboard & mouse behind the scenes (**visual overlay only, no virtual gamepad injection**).

<img width="956" height="820" alt="PadOverlay screenshot" src="https://github.com/user-attachments/assets/fac1a08a-84f2-4e5c-a2da-eb8fd296aa95" />

默认带《猛兽派对》键位（出拳 R、表情 T / 动作 G 轮盘等）；如果你要在别的游戏使用，可在设置里点手柄键再录键盘改映射。  
鼠标移动始终驱动右摇杆高亮（镜头 / 轮盘选向）；停下后回中。  
Windows 下用 Raw Input 读相对位移，游戏锁光标 / 全屏也能跟上。

Ships with *Party Animals*-style defaults (punch on R, emote T / action G wheels, etc.); for other games, remapping is done in Settings by clicking a pad button then pressing a key.  
Mouse movement always drives the right-stick highlight (camera / radial menus); recenters when idle.  
On Windows, Raw Input tracks relative motion even when the game locks the cursor or goes fullscreen.

## 架构 / Architecture

| 层 Layer | 目录 Dir | 职责 Role |
|----------|----------|-----------|
| listen | `listen/` | 全局键鼠监听 / Global keyboard & mouse hooks |
| mapping | `mapping/` + `config/keymap.yml` | YAML 映射与点亮状态 / Keymap & highlight state |
| display | `display/` | 置顶手柄高亮悬浮窗 / Always-on-top pad overlay |
| ui | `ui/` | 托盘与映射设置 / Tray & mapping settings |

## 运行 / Run

```bash
pip install -r requirements.txt
python main.py
```

## 打包 exe / Build exe

```bash
build_exe.bat
```

产物：`dist\PadOverlay.exe`（单文件，内嵌 `config/` + `skins/`）。放到任意目录运行；旁边若没有这些文件，会自动拷出一份（已有文件不覆盖）。

Output: `dist\PadOverlay.exe` (one-file, embeds `config/` + `skins/`). Run from any folder; if local copies of those dirs are missing, they are extracted once (existing files are not overwritten).

控制台 **Ctrl+C** 可退出。右上角 ✕ / 托盘「退出」也会结束进程（卸钩子带超时，避免卡死关不掉）。

**Ctrl+C** in the console exits. The overlay ✕ / tray Quit also ends the process (hook teardown has a timeout so exit won't hang).

全屏游戏下若收不到键鼠，请以**管理员身份**运行（游戏若提权，钩子否则听不到）。

If input is missed under a fullscreen elevated game, run PadOverlay **as Administrator**.

鼠标 → 右摇杆：同时用 Raw Input、低级鼠标钩子、以及 `GetCursorPos` 轮询（游戏自绘指针时也能跟上）。

Mouse → right stick uses Raw Input, a low-level mouse hook, and `GetCursorPos` polling (works when the game draws its own cursor).

## 悬浮窗 / Overlay

- 右上角 **⚙** 打开映射设置，**✕** 退出程序（命令行一并结束）  
  Top-right **⚙** opens mapping settings; **✕** quits (also ends the console process)
- 仅隐藏悬浮窗、保持后台：用托盘菜单「隐藏悬浮窗」  
  Hide overlay but keep running: tray → Hide overlay
- **滚轮** 缩放；右下角拖动手柄也可缩放（缩放 / 位置写入 `config/window.yml`）  
  **Scroll** to scale; or drag the bottom-right handle (scale / position saved to `config/window.yml`)
- 拖动窗口空白处移动；拖动中防抖保存，隐藏 / 退出时也会写入位置  
  Drag empty areas to move; position is debounced while dragging and flushed on hide / quit

## 托盘 / Tray

- **左键** / Left-click：打开映射设置 / Open mapping settings
- **显示 / 隐藏悬浮窗** / Show / Hide overlay
- **映射设置…** / Mapping…：点手柄键 → 按键盘 / 鼠标绑定 → 保存  
  Click a pad button → press a key/mouse button → Save
- **锁定拖动** / Lock drag
- **退出** / Quit

无全局软件热键。 / No global hotkeys.

## 映射 / 布局 / 皮肤 · Mapping / Layout / Skins

- [`config/keymap.yml`](config/keymap.yml) — 物理键 → 手柄部件 / Physical key → pad part
- [`skins/`](skins/) — 样式包（见其中 README）/ Skin packs (see README inside)
  - 每套皮肤：`skin.yml` + `layout.yml` +（图片模式）`base.png` / `active/` / `inactive/`
  - Each skin: `skin.yml` + `layout.yml` + (image mode) `base.png` / `active/` / `inactive/`
- [`config/window.yml`](config/window.yml) — 缩放、位置、当前 `skin` / Scale, position, active `skin`

设置页可选皮肤；勾选 **布置布局** 拖拽按键 → **保存布局**（写入当前皮肤的 `layout.yml`）。

In Settings, pick a skin; enable **Edit layout**, drag buttons, then **Save layout** (writes the current skin's `layout.yml`).

悬浮窗手柄外透明；鼠标移到**右上角 / 底部**热区才会显示设置、关闭与缩放提示。

Outside the pad art the window is transparent; hover the **top-right / bottom** hot zones to show settings, close, and scale UI.
