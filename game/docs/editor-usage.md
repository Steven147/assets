# 地图编辑器使用说明

## 启动

```bash
just edit                                  # 空白编辑器（用户在 UI 选城市）
just edit shanghai_50km                    # 命名草稿（自动从 localStorage 恢复同名草稿）
just edit-city shanghai_test shanghai     # 预填 shanghai 坐标
```

浏览器会自动打开 `http://127.0.0.1:<port>/pipeline/editor/editor.html`。

## 操作

- **画笔**：点工具栏的 G/O/R/r/L/S 按钮（默认 G）。
- **画**：在画布上点击或拖动。松开鼠标前所有改动合并为一次撤销单位。
- **调整画布大小**：改工具栏的 rows/cols 数字，点 [应用]。会弹确认框（破坏性）。
- **同步视图**：拖动或缩放地图后，点 [同步] 会把当前中心点 + 跨度写回 lat / lng / span 输入框。
- **切换底图**：工具栏「底图」按钮循环「实 / 半透 / 隐」，对应 OSM 瓦片可见性。隐藏后专注绘制，半透对齐参考。
- **移动底图**：拖动地图（不要在画布上点，会进入绘制模式）。如果想用滚轮缩放，按 [应用] 让 span_km 同步。
- **城市预设**：工具栏下拉选城市，lat/lng/span 自动填好。
- **撤销 / 重做**：用按钮。
- **清空**：会弹确认框。

## 导出

点 [导出] 触发两件事：
1. 浏览器下载 `<name>_decl.json` 到本地。
2. 自动 POST 到 `/save` 端点，写入 `input/<name>_decl.json`。

保存成功后在底栏看到 `已保存: input/<name>_decl.json`。

## 跑 pipeline

```bash
just build <name>
```

`stage1-local` 会读取刚保存的 `*_decl.json`，`stage2-4` 生成 viewer HTML。

## 故障排查

| 现象 | 解决 |
|------|------|
| 画布上某些格显示红色 | 该 desc 在 `kenney_pixel-shmup/Tiles/` 里没对应 PNG。改 `pipeline/editor/tile_paths_gen.py` 加 mapping。 |
| 浏览器显示 "Boot error" | 确认 `pipeline/editor/meta.json` 和 `tile_paths.js` 存在（启动时会生成）。 |
| 看不到 OSM 底图 | 检查网络；Leaflet 从 `unpkg.com` 加载。 |
| localStorage 满 | 底栏会显示警告；导出 JSON 重置。 |
| 撤销/重做次数超限 | 只保留最近 50 笔触（计划内的设计）。 |
