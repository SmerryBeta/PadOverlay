# 手柄皮肤目录

```
skins/
  vector_default/          # 内置线稿（mode: vector）
  drawn_pad/               # 图片样例（程序化生成）
  neon_pad/                # 从拼图裁切的 neon 皮肤（推荐）
    skin.yml
    layout.yml
    base.png
    active/  inactive/
    _source_sheet.png      # 原始上下拼图（可选）
  我的皮肤/                 # 复制 _template 改名
    skin.yml               # mode: image
    layout.yml             # 按键坐标
    base.png               # 手柄底图
    active/                # 按下态 png（部件 id 命名）
      btn_a.png
      lt.png
      ...
    inactive/              # 未按下态 png
  _template/               # 模板，不要直接当皮肤用
```

重生成样例图：`python tools/gen_drawn_pad_skin.py`

在设置里切换皮肤，或改 `config/window.yml` 的 `skin:` 字段。
