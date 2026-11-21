# PadOverlay 图片皮肤手册（给 AI / 制作流程）

本文约定如何从一张拼图做出可切换的 `skins/<id>/` 皮肤包，并保证其他 AI 按同样步骤可复现。

参考实现：`neon_pad`（已人工布置）、`calico_pad`（猫纹）、导入脚本 `tools/import_ps_skin.py` / `tools/import_calico_skin.py`。

---

## 1. 目录与文件（硬约定）

```
skins/<skin_id>/
  skin.yml              # 必填：name / mode / base / 目录名
  layout.yml            # 必填：画布 + 部件锚点（可后调）
  base.png              # 必填：手柄底板（透明底，键位开孔）
  inactive/             # 未按下态，文件名 = 部件 id
    btn_a.png …
  active/               # 按下态，文件名与 inactive 完全一致
    btn_a.png …
  _source_sheet.png     # 可选：原始拼图备份
```

- `<skin_id>`：小写英文/下划线，勿以 `_` 开头（`_` 目录会被跳过）。
- `mode` 必须为 `image`（`vector` 走线稿，不读 png）。
- 文件名 **必须** 用下列 id，程序按 stem 匹配，不认中文。

### 1.1 `skin.yml` 模板

```yaml
name: 显示名称
mode: image
base: base.png
active_dir: active
inactive_dir: inactive
```

### 1.2 部件 id 清单（必须齐全更佳）

| id | 含义 | layout type |
|----|------|-------------|
| `lt` `rt` | 扳机 | `bumper` |
| `lb` `rb` | 肩键 | `bumper` |
| `btn_a` `btn_b` `btn_x` `btn_y` | 面键 | `face` |
| `btn_view` `btn_menu` | 小键 | `small` |
| `ls` `rs` | 摇杆帽 | `stick` |
| `dpad` | 十字键整体 | `dpad` |
| `dpad_up` `dpad_down` `dpad_left` `dpad_right` | 方向高亮 | （跟 dpad 画） |
| `guide` | 可选，可只写 layout 不放图 | `guide` |

**禁止**对 `lt/rt/lb/rb` 做非等比拉伸变形；裁切后 PNG 保持原图像素宽高，用 `layout.scale` 统一缩放。

---

## 2. 源拼图规范（给画师 / 提示词）

整张图建议 **1024×682**（或等比），**必须带真实 alpha**（透明背景，不要烘焙黑底）。

推荐排版（与现有两套图一致）：

```
┌──────────────────────┬────────────────────────────┐
│                      │  INACTIVE 部件网格          │
│   底板 base          │  A B X Y | LT RT            │
│   （仅壳体+开孔）    │  LB RB | view menu          │
│                      │  ls rs dpad | 四向           │
├──────────────────────┼────────────────────────────┤
│   （可空）           │  ACTIVE 同构图高亮态         │
│                      │  与上方一一对齐             │
└──────────────────────┴────────────────────────────┘
```

规则：

1. **左上**：完整底板，按键位镂空；不要画可拆键帽。
2. **右上**：未激活部件，彼此分开、透明间隙足够裁切。
3. **右下**：激活态，与右上 **同尺寸、同相对位置**（便于 `y + offset` 或分栏检测）。
4. 小字标签可有可无；裁切时用 alpha 连通域，并过滤过扁的文字块。
5. **不要**让 AI/脚本按亮度抠黑底；只用源图 alpha。

---

## 3. 裁切方案（必须遵守）

### 3.1 原则

1. **只认 alpha，不认亮度**  
   - `A == 0`：丢弃，并清掉脏 RGB。  
   - `A > 0`：原样保留 RGB+A（含软边）。  
   - **禁止** flood 亮度阈值 / 把半透明锐化成 0/255。
2. **只裁切，不缩放、不旋转、不变形**  
   - 导出 PNG 像素 = 源图像素包围盒。  
   - LT/RT/LB/RB 尤其禁止改宽高比。
3. **加载时再处理合成**  
   - `display/skin.py`：`A==0` 清脏色 → `Format_ARGB32_Premultiplied`（等价 RGB×A/255）。

### 3.2 推荐步骤

1. 读入源图 `Format_ARGB32`，确认四角 `alpha=0`。
2. **底板**：在左栏用 `alpha > thr` 求包围盒 → `crop` → 可选再 `tighten` → `base.png`。
3. **部件**：对右上 / 右下分别做 alpha 连通域，或使用实测框常量。  
   阅读序（现有拼图）：
   - 行1：`btn_a btn_b btn_x btn_y lt rt`
   - 行2：`lb rb btn_view btn_menu`
   - 行3：`ls rs dpad`
   - 行4：`dpad_up dpad_down dpad_left dpad_right`（或上/左/右/下按几何）
4. 每个框：`pad 1px` → crop → 清 `A=0` 脏色 → 按 alpha 紧裁 → 写入 `inactive/` 或 `active/`。
5. 写 `skin.yml`；写 `layout.yml`（见下节）。
6. 复制源图为 `_source_sheet.png` 备查。

参考脚本：

- `tools/import_ps_skin.py`（neon，INACTIVE 框 + `y+341`）
- `tools/import_calico_skin.py`（猫纹，INACTIVE/ACTIVE 分表）

新主题：可复制其一，改 `SRC` / `OUT` / 包围盒即可。

### 3.3 验收

- `base` / 键图在棋盘格或品红底上边缘应光滑，开孔透底。  
- `list_skins()` 出现新 id；`set_skin(id)` 后 overlay/设置预览有图。  
- 按下 `btn_a` 等应切换 active 贴图。

---

## 4. `layout.yml`（锚点与变换）

### 4.1 画布与底板

```yaml
canvas:
  w: <与 base 像素宽一致，或略大>
  h: <与 base 像素高一致，或略大>
  base_x: 0.0          # 底板左上角偏移
  base_y: 0.0
  base_scale: 1.0      # 底板缩放（绕中心）
  base_rot: 0.0        # 底板旋转，单位度
```

绘制：底板按 `base_x/y + base 尺寸×base_scale`，再绕矩形中心旋转 `base_rot`。

### 4.2 部件字段

| type | 锚点含义 | 尺寸字段 | 绘制矩形 |
|------|----------|----------|----------|
| `bumper` | **左上角** `(x,y)` | `w` `h`（= 图片原始宽高） | `(x,y,w·s,h·s)` |
| `face` / `small` / `stick` | **中心** `(x,y)` | `r` | 边长 `2·r·s` |
| `dpad` | **中心** `(x,y)` | `arm` | 十字臂长 `arm·s` |
| `guide` | 中心 | `r` | 可无图 |

公共可选：

- `scale`：默认 `1.0`，等比缩放（**保持比例**）
- `rot`：默认 `0`，度，绕部件中心旋转
- `label`：面键/肩键文字（矢量回退用）

有效尺寸：`display/layout.py` → `part_metrics()` = 原始尺寸 × `scale`。

### 4.3 布局从哪里抄

**以已调好的 `skins/neon_pad/layout.yml` 为位置参考**（人工布置过）。

换新皮肤时：

1. 新 `canvas.w/h` = 新 `base.png` 尺寸。  
2. 将 neon 的各部件 `x,y`（及 `base_x/y/scale/rot`）按画布比例映射：

   ```text
   x' = neon.x * (new_w / neon.w)
   y' = neon.y * (new_h / neon.h)
   ```

3. `bumper` 的 `w/h` 换成 **本套裁切出的图片像素尺寸**（勿抄 neon 的 w/h）。  
4. `face/stick/dpad` 的 `r`/`arm` 可按比例缩放，或先抄 neon 再靠 `scale` 微调。  
5. `scale`/`rot` 可先抄 neon，再在设置里微调。

然后在设置页勾选 **布置布局**：

- 拖拽移动  
- 滚轮缩放  
- Shift+滚轮旋转  
- 点空白选底板  
- Ctrl+Z / Ctrl+Y 撤销重做  
- **保存布局** → 写回当前皮肤目录的 `layout.yml`

### 4.4 绘制层注意

- 图片皮肤：**不要**在底板下铺整块半透明命中黑底（会啃软边）；命中靠底板自身 alpha。  
- `active` 优先于 `inactive`；缺图时回退。  
- `dpad_*` 贴在 dpad 中心附近，并随 `dpad.rot` 旋转。

---

## 5. 接入应用

1. 文件夹放入 `skins/<id>/` 且含 `skin.yml`。  
2. 设置页皮肤下拉会自动列出；或改 `config/window.yml`：

   ```yaml
   skin: calico_pad
   ```

3. 切换皮肤会加载该目录 `layout.yml` 并刷新悬浮窗。

代码入口：

- 加载：`display/skin.py`  
- 布局：`display/layout.py`  
- 绘制：`display/skin_draw.py`  
- 布置 UI：`ui/settings.py`（ControllerPicker）

---

## 6. 检查清单（交付前）

- [ ] `skin.yml` `mode: image`  
- [ ] `base.png` 透明底、开孔正确  
- [ ] `inactive/` + `active/` 同名文件齐全（至少面键+肩键+摇杆+dpad）  
- [ ] bumper PNG 未被拉伸改比例；`layout` 里 `w/h` = 图片像素  
- [ ] `layout.yml` 位置参考 `neon_pad` 并按新画布比例映射  
- [ ] 设置中可切换；按下有高亮  
- [ ] 未使用亮度抠图毁掉源 alpha  

---

## 7. 现有皮肤 id

| id | 说明 |
|----|------|
| `vector_default` | 矢量线稿 |
| `drawn_pad` | 程序化示例图 |
| `neon_pad` | Neon 拼图（**布局参考基准**） |
| `sakura_pad` | 樱花拼图 |
| `vicksy_pad` | Vicksy |
