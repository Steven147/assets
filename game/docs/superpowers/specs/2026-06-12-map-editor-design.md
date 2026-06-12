# 地图编辑器 — 设计文档

**日期：** 2026-06-12
**状态：** 草案（等待用户审阅）

## 目标

在现有地图管道上新增一个浏览器端的地图编辑器。用户在一张活的 OpenStreetMap 底图上绘制瓦片网格（单字符：G/S/O/R/r/L），并导出一个标准的 `*_decl.json`，可以直接喂给 `stage1-local` → `stage2` → `stage3` → `stage4`。

编辑器是纯绘制工具。它**不会**从 OSM 拉取数据填入网格——OSM 瓦片仅作视觉参考。字符网格 100% 由用户手写。

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  用户: just edit [<name>] [--city X] [--rows N --cols M]│
└────────────────────┬────────────────────────────────────┘
                     ↓
        pipeline/editor/editor_server.py
        ┌────────────────────────────────────┐
        │ 1. 读取瓦片注册表（或用默认）    │
        │ 2. 生成 JS 解析器 lookup          │
        │ 3. 注入 tiles.js（仅路径）       │
        │ 4. 注入 meta.json                 │
        │ 5. 启动 http.server，打开浏览器   │
        └────────────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────────┐
│  浏览器                                              │
│  ┌──────────────────────────────────────────────┐    │
│  │ Leaflet 地图（OSM 瓦片、平移、缩放）         │    │
│  │   ↑                                          │    │
│  │ Canvas 叠加层（网格线 + 瓦片渲染）           │    │
│  │   ↑                                          │    │
│  │ 鼠标事件（绘制、拖动、撤销）                 │    │
│  └──────────────────────────────────────────────┘    │
│  工具栏：画笔、尺寸、撤销/重做、导出、城市选择器      │
│  状态栏：光标下 lat/lng、单元格 (r,c)                │
└────────────────────────────────────────────────────────┘
                     ↓ 用户点击 [导出]
        input/<name>_decl.json  (匹配现有 schema)
                     ↓
        just build <name>   (现有管道)
```

## 组件

### `pipeline/editor/editor_server.py`

轻量 Python 包装器。职责：
- 接收 CLI 参数：可选 name、city 预设、rows、cols。
- 生成 `meta.json`（center_lat、center_lng、span_km、rows、cols）。
- 生成 `lookup.js`（一个大对象，映射 char × 4 邻居组合 → 瓦片文件路径）。
- 把 `editor.html` 复制到工作目录。
- 启动一个空闲端口的 `http.server`。
- 打开浏览器到 `http://localhost:PORT/editor.html`。

### `pipeline/editor/editor.html`

单一 HTML 文件，内联 CSS 和 `<script>` 标签。无构建步骤。从 CDN 加载 Leaflet。

### `pipeline/editor/editor.js`

模块化 JS（无打包工具）。类：
- `MapEditor` — 协调器。持有状态、绑定 DOM 事件。
- `GridModel` — `string[][]`（rows × cols）。方法：`get`、`set`、`clear`、`fillRect`、`toDeclMap`。
- `TileResolver` — 预加载的 lookup。`resolve(grid, r, c) → tilePath`。
- `Renderer` — 单一 `<canvas>`。`drawAll()`、`drawCell(r, c)`。跟踪已加载的瓦片图片。
- `BackgroundAligner` — 从 meta 配置 Leaflet bounds。中心点变化时重新锚定网格。
- `History` — `push(snapshot)`、`undo()`、`redo()`。策略：每次笔触（按下到松开）做一次完整网格快照。最多保留 50 笔触。内存预算：50 × 200 × 200 × 1 字节 ≈ 2MB 最坏情况，可接受。
- `TileLoader` — 按需懒加载 `kenney_pixel-shmup/Tiles/*.png`，用 `<img>` + 缓存。
- `Toolbar` — 画笔选择、尺寸输入、城市下拉、撤销/重做按钮、导出按钮。
- `DeclExporter` — 构造 JSON 对象并触发下载 / 写入 `input/`。

### `pipeline/editor/lookup.js`（生成产物）

一个大的 JS 对象，映射 (char + 4 位邻居掩码) → 瓦片文件路径。服务启动时通过在合成网格上重放 `resolve.py` 规则生成。示例形态：

```js
window.TILE_LOOKUP = {
  "S":     { "any": "kenney_pixel-shmup/Tiles/tile_0098.png" },
  "G_0000":{ "any": "kenney_pixel-shmup/Tiles/tile_0050.png" },
  "G_0001":{ "top": "kenney_pixel-shmup/Tiles/tile_0108.png", ... },
  // ... 约 80-120 项
};
```

### `pipeline/editor/meta.json`（生成产物）

```json
{
  "name": "shanghai_50km",
  "center_lat": 31.2304,
  "center_lng": 121.4737,
  "span_km": 50,
  "rows": 60,
  "cols": 80,
  "city_presets": ["shanghai", "beijing", "hangzhou", "syracuse"]
}
```

## 数据流

### 启动

1. 用户运行 `just edit`（或 `just edit shanghai_50km --rows 60 --cols 80`）。
2. `editor_server.py` 解析 city 预设 → meta（center、span_km）。
3. Python 重放 `resolve.py` 规则以构建 `lookup.js`。瓦片文件路径来自 `kenney_pixel-shmup/Tiles/` 目录；脚本扫描该目录并使用 `resolve.py` 中已知的瓦片后缀来为每个 (char, 邻居掩码) 分配瓦片。
4. 写入 `meta.json`。`editor.html` 和 `editor.js` 直接对外服务。
5. 浏览器打开，Leaflet 以 `meta.center_lat/lng` 为中心、按 `span_km` 设定合适缩放级别初始化。
6. Canvas 叠加层尺寸覆盖可见地图区域，划分为 `rows × cols` 网格。

### 绘制

1. Canvas 上 `mousedown` → 像素 → 单元格 (r, c) 换算 → `GridModel.set(r, c, penChar)`。
2. `TileResolver.resolve(grid, r, c)` → 返回瓦片文件路径。
3. `TileLoader.load(path)` → 返回缓存的 `<img>` 或发起 fetch。加入渲染队列。
4. `Renderer.drawCell(r, c)` → 把图片 blit 到 canvas。
5. `History.push(gridSnapshot)`。
6. 防抖（300ms）把 `grid` 保存到 `localStorage`，用于崩溃恢复。

### 重新锚定 / 调整尺寸

1. 用户在工具栏改变 center lat/lng 或 span_km。
2. `BackgroundAligner.reconfigure(meta)` 更新 Leaflet bounds，把地图重新居中到新坐标。
3. 已绘制的单元格保持原位（字符内容保留）；只有 OSM 底图移动。单元格到 lat/lng 的映射重算，但网格数组本身不变。
4. 用户改变 rows/cols → 弹确认框（破坏性操作）。确认后，网格重新分配；已有单元格按左上对齐保留，新单元格默认为 `S`（海），超出新边界的单元格丢弃。

### 导出

1. 用户点击 [导出] → 弹模态框显示生成的 JSON。
2. `DeclExporter.build()` 构造：
   ```json
   {
     "name": "<name>",
     "kind": "single",
     "rows": <rows>,
     "cols": <cols>,
     "center_lat": <center_lat>,
     "center_lng": <center_lng>,
     "span_km": <span_km>,
     "map": ["SSS...", "SGG...", ...]
   }
   ```
3. 三种操作可选：
   - **下载** — 通过浏览器下载保存 `<name>_decl.json`。
   - **复制** — 复制 JSON 到剪贴板。
   - **保存到 input/** — POST 到 `editor_server.py`，写入 `input/<name>_decl.json` 并返回 200。
4. 保存后，终端显示：`Saved input/<name>_decl.json — run: just build <name>`。

## 瓦片解析器（resolve.py 的 JS 移植）

直接翻译 `pipeline/resolve.py` 中的 `_beach`、`_road`、`resolve_tile`。同样的字符集、同样的邻居分析、同样的 desc 字符串格式。Lookup 在服务启动时通过遍历所有 `(char, 4 位掩码)` 组合、针对合成最小网格调用 Python `resolve_tile` 并记录结果 desc → 文件映射来生成。

JS 端只做字典查找；真正的逻辑在 `resolve.py` 中，是单一事实来源。

## 存储

- **草稿状态**（编辑中）：`localStorage`，以 `<name>` 为 key。每 300ms 自动保存。
- **导出文件**：`input/<name>_decl.json`（匹配现有 schema，喂给 `stage1-local`）。
- **`output/` 中无中间文件**。编辑器位于管道上游。

## 约束与非目标

- **无构建步骤**。单一 HTML 文件，原生 JS，CDN Leaflet。
- **无新依赖**。使用现有的 `kenney_pixel-shmup/Tiles/*.png` 和 `pipeline/resolve.py`。
- **无服务端状态**。`editor_server.py` 只是一个静态文件服务器 + 一个 `POST /save` 端点。
- **同时只编辑一张地图**。无多地图 UI。换图就关标签页。
- **无多人 / 协作**。单浏览器会话。
- **「清空全部」/「调整尺寸」操作不支持撤销**。这些是破坏性操作，会弹确认框。
- **不支持自定义瓦片上传**。用户从固定集合（G/S/O/R/r/L）选画笔；瓦片变体来自 `kenney_pixel-shmup/Tiles/` 默认集合，由 `pipeline/resolve.py` 解析。

## 错误处理

| 场景 | 行为 |
|------|------|
| 城市预设未找到 | 回退到空中心 (0,0)，提示用户 |
| 瓦片图 404 | 显示红色格 + 控制台错误，允许继续编辑 |
| `localStorage` 满 | 禁用自动保存，状态栏显示警告 |
| 导出：rows/cols 与 map 形状不匹配 | 显式拒绝，模态框报错 |
| `POST /save` 失败 | 显示错误，建议「下载」作为备选 |
| 调整尺寸到 > 200×200 | 确认框（性能警告：10 万+ 单元格） |

## 测试

- **单元（Python）**：测试 `editor_server.py` 为所有 char × mask 组合生成合法的 `lookup.js`。
- **单元（JS）**：用 `resolve.py` 生成的 fixture 测试 `TileResolver`。
- **集成**：端到端测试：`just edit foo` → 绘制几个格 → 导出 → `just build foo` → 断言 `output/foo/foo_resolved.json` 符合预期。
- **手动**：在 smoke test 工作流加入编辑器后用 `just smoke` 验证。

## 启动 / CLI

```bash
# 空白编辑器，用户在 UI 选城市
just edit

# 预填已知城市
just edit shanghai_50km --city shanghai --span-km 50 --rows 60 --cols 80

# 打开已有草稿（从 localStorage 加载）
just edit shanghai_50km
```

`justfile` 中新增的 recipe：
```makefile
edit name="":
    @if [ -z "{{name}}" ]; then \
        {{PY}} pipeline/editor/editor_server.py; \
    else \
        {{PY}} pipeline/editor/editor_server.py --name {{name}}; \
    fi
```

## 开放问题

（无——头脑风暴阶段全部已解决）
