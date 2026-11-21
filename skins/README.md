# 手柄皮肤目录

**完整制作规范（裁切 / alpha / layout / 检查清单）见：[HANDBOOK.md](HANDBOOK.md)**  
布局位置以已调好的 **`neon_pad/layout.yml`** 为参考基准。

```
skins/
  vector_default/          # 矢量线稿
  drawn_pad/               # 程序化示例
  neon_pad/                # Neon（布局参考）
  calico_pad/              # 猫纹主题
  _template/               # 复制改名用模板
```

每套图片皮肤最少包含：

```
skin.yml + layout.yml + base.png + active/ + inactive/
```

部件文件名必须用英文 id（`btn_a`、`lt`、`ls`、`dpad_up` …），见手册。

重生成示例：

- 猫纹：`python tools/import_calico_skin.py`
- Neon：`python tools/import_ps_skin.py`
- 矢量贴图样例：`python tools/gen_drawn_pad_skin.py`

设置里切换皮肤，或改 `config/window.yml` 的 `skin:`。
