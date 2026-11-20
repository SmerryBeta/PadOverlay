# PadOverlay 假装用手柄玩游戏

键盘 / 鼠标操作 → Xbox 手柄按键高亮悬浮窗（**只可视化，不注入虚拟手柄**）。

<img width="956" height="820" alt="f860eeaa-885f-456d-98ed-e1db548e8287" src="https://github.com/user-attachments/assets/fac1a08a-84f2-4e5c-a2da-eb8fd296aa95" />

默认带《猛兽派对》键位（出拳 R、表情 T / 动作 G 轮盘等）；如果你要在别的游戏使用，可在设置里点手柄键再录键盘改映射。
鼠标移动始终驱动右摇杆高亮（镜头 / 轮盘选向）；停下后回中。
Windows 下用 Raw Input 读相对位移，游戏锁光标/全屏也能跟上（不要用屏幕坐标差分）。

## 三层

| 层 | 目录 | 职责 |
|----|------|------|
| listen | `listen/` | 全局键鼠监听 |
| mapping | `mapping/` + `config/keymap.yml` | YAML 映射与点亮状态 |
| display | `display/` | 置顶手绘手柄高亮 |
| ui | `ui/` | 托盘与映射设置 |

## 运行

```bash
pip install -r requirements.txt
python main.py
```

全屏游戏下若收不到键鼠，请以**管理员身份**运行（游戏若提权，钩子否则听不到）。

鼠标 → 右摇杆：同时用 Raw Input、低级鼠标钩子、以及 `GetCursorPos` 轮询（游戏自绘指针时也能跟上）。

## 悬浮窗

- 右上角 **⚙** 打开映射设置，**✕** 退出程序（命令行一并结束）
- 仅隐藏悬浮窗、保持后台：用托盘菜单「隐藏悬浮窗」
- **滚轮** 缩放；右下角拖动手柄也可缩放（缩放/位置写入 `config/window.yml`，下次启动恢复）
- 拖动窗口空白处移动；拖动中防抖保存，隐藏/退出时也会写入位置

## 托盘

- **左键**：打开映射设置
- **显示 / 隐藏悬浮窗**
- **映射设置…**：点手柄键 → 按键盘/鼠标绑定 → 保存
- **锁定拖动**
- **退出**

无全局软件热键。

## 映射 / 布局 / 皮肤

- [`config/keymap.yml`](config/keymap.yml) — 物理键 → 手柄部件
- [`skins/`](skins/) — 样式包（见其中 README）
  - 每套皮肤：`skin.yml` + `layout.yml` +（图片模式）`base.png` / `active/` / `inactive/`
- [`config/window.yml`](config/window.yml) — 缩放、位置、当前 `skin`

设置页可选皮肤；勾选 **布置布局** 拖拽按键 → **保存布局**（写入当前皮肤的 `layout.yml`）。

悬浮窗手柄外透明；鼠标移到**右上角 / 底部**热区才会显示设置、关闭与缩放提示。
