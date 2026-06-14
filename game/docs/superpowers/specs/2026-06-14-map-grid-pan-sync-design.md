# 地图编辑器 — 拖动 / 绘制时网格对齐

**日期：** 2026-06-14
**状态：** 已批准，待实现

## 目标

修复 `just edit` 编辑器里「拖动地图时像素网格不跟随」的 bug。当用户在 Leaflet 地图上拖动（pan）时，画布上的像素网格应当跟随 meta 中心点（`center_lat` / `center_lng`）在屏幕上的位置一起滑动，从而保持与地图瓦片 1:1 对齐。绘制（点击/拖动画格）的行为不变 —— 只改单元格内容，不触发地图 pan。

不引入显式「拖动模式 / 绘制模式」开关。两种行为是同一交互的两个动作分支：
- 拖动（鼠标点 canvas 之外的地图区域并拖） → pan 地图，网格跟随
- 绘制（鼠标点 canvas 内部） → paint 单元格，地图不动

## 架构

改动局限在 `pipeline/editor/editor_app.js` 的 `MapEditor` 类，新增 1 个方法 + 4 个改动点（构造器 / `_applyMeta` / `_syncMeta` / `_applyCity`）。`BackgroundAligner` 不动（或最小化加 1 行）。

DOM 树不变：canvas 仍是 `#map` div 的子元素（不是 Leaflet pane 的子元素）。在 `MapEditor` 监听 Leaflet 的 `move` 事件，根据锚点 lat/lng 的当前屏幕位置调整 canvas 的 `left` / `top`。

## 组件变化

### `MapEditor`（在 `editor_app.js`）

构造器内新增：
- 紧跟 `this._baseOpacity = 1;` 之后：
  ```js
  this._centerLatLng = L.latLng(meta.center_lat, meta.center_lng);
  this._setupMapSync();
  ```

新增方法：
```js
_setupMapSync() {
  const onMove = () => {
    const pt = this.aligner.map.latLngToContainerPoint(this._centerLatLng);
    const cellSize = this.renderer.cellSize();
    this.canvas.style.left = (pt.x - this.grid.cols * cellSize / 2) + 'px';
    this.canvas.style.top = (pt.y - this.grid.rows * cellSize / 2) + 'px';
  };
  this.aligner.map.on('move', onMove);
  onMove();  // initial position
}
```

锚点更新点（4 处，都在一两行内）：

- `_applyMeta()`：调 `this.aligner.setView(m)` **之前**更新锚点：
  ```js
  this._centerLatLng = L.latLng(m.center_lat, m.center_lng);
  ```
  之后 Leaflet 的 `setView` 触发 `move` 事件，`onMove` 自动重定位。

- `_syncMeta()`：写回 lat/lng 之后：
  ```js
  this._centerLatLng = L.latLng(view.center_lat, view.center_lng);
  ```

- `_applyCity(name)`：应用城市预设之后（写在 `this.toolbar.setMeta(newMeta); this.aligner.setView(newMeta);` 后面）：
  ```js
  this._centerLatLng = L.latLng(newMeta.center_lat, newMeta.center_lng);
  ```

- 构造器（见上）已处理初始锚点。

### `BackgroundAligner`（在 `editor_app.js`）

最小改动：在构造器内 `L.map(mapElId, { zoomControl: true })` 改为 `L.map(mapElId, { zoomControl: true, doubleClickZoom: false })`。

理由：Leaflet 默认双击地图会重置中心到双击点并 zoom in。这会和「点击 canvas 之外的地图」pan 行为冲突；用户双击想缩放时会发现网格跳走。Disable 后用户如需缩放，用左上角 zoom control 按钮即可。

不动 `setView` / `getView` / `setOpacity` / 其它方法。

### `editor_lib.js`（不动）

纯逻辑零 DOM 依赖，保持不变。

### `editor_server.py`（不动）

Python 服务只启动静态服务 + `/save` 端点。

## UI 改动

无新增 HTML 元素。canvas 元素、工具栏、地图容器全部不变。

`docs/editor-usage.md` 操作 section 新增 1 条说明（位置在「切换底图」之后、「移动底图」之前或之后均可）：

> - **拖动时网格跟随**：拖动地图（点击地图上 canvas 之外的区域）时，像素网格会自动跟随 meta 中心点的屏幕位置一起移动，保持与地图瓦片对齐。

## 数据流

### 初始加载

1. 用户运行 `just edit shanghai_50km`
2. `MapEditor` 构造器：创建 `GridModel` / `BackgroundAligner` / 调用 `aligner.setView(meta)` / 调 `Renderer.drawAll()` / 调 `_setupMapSync()`
3. `_setupMapSync`：
   - 设置 `this._centerLatLng = L.latLng(31.2304, 121.4737)`
   - 调一次 `onMove()`：算出 meta 中心当前在地图 div 中心，把 canvas 定位到该位置
   - 注册 `map.on('move', onMove)`
4. 用户看到 canvas 网格覆盖在地图中心区域（meta 中心），地图瓦片 1:1 对齐

### 用户拖动地图

1. 用户在 canvas 之外的地图区域按下鼠标并拖动
2. Leaflet 处理 pan，更新 mapPane 的 transform
3. Leaflet 触发 `move` 事件（连续触发，~30Hz）
4. `onMove`：
   - 算出 meta 中心当前屏幕位置 `pt = map.latLngToContainerPoint(_centerLatLng)`
   - 更新 `canvas.style.left` / `top` 让网格中心 = `pt`
5. 用户看到网格和地图内容一起滑动，对齐保持

### 用户绘制

1. 用户在 canvas 上 mousedown
2. canvas `pointer-events: auto; z-index: 400` 拦截事件
3. Leaflet 不触发 pan / `move`
4. `onMove` 不被调用，canvas 位置不变
5. `onMove` (mouse handler) 读取 canvas 当前 rect → 计算 (r, c) → `grid.set` → 渲染

### 用户点击 [同步]

1. 拖动后点击 [同步]
2. `_syncMeta()`：
   - 读 `view = aligner.getView()` → 拿到当前 center_lat, center_lng, span_km
   - blur 输入框
   - `toolbar.setMeta(...)` 写回
   - 状态栏显示「已同步: ...」
   - **新增**：`this._centerLatLng = L.latLng(view.center_lat, view.center_lng)`
3. Leaflet 不自动触发 `move`（因为我们没调 setView）
4. **手动补一次** `this._onMapMoveRef?.()` 或直接调 `onMove`：因为 setMeta 不触发 move，且现在锚点换了，canvas 位置要重新算
5. 实际上：`_syncMeta` 不调 setView，所以 `_centerLatLng` 改了后**不会**自动重定位 canvas。**需要在 `_syncMeta` 末尾显式调一次 `onMove()`**（用闭包引用）

### 用户点击 [应用]

1. 用户改 rows/cols/lat/lng/span 后点 [应用]
2. `_applyMeta()`：
   - 读 `m = toolbar.getMeta()`
   - 如果 rows/cols 变了 → resize grid（弹确认框）
   - **`this._centerLatLng = L.latLng(m.center_lat, m.center_lng)`**（新增）
   - `this.aligner.setView(m)` → Leaflet 触发 `move` 事件 → `onMove` 自动重定位

## 错误处理

| 场景 | 行为 |
|------|------|
| Leaflet 还没初始化 | 不会发生（`_setupMapSync` 在 `setView` 之后调） |
| `_centerLatLng` 未初始化 | 不会发生（构造器内显式赋值） |
| Window resize | 现有 `window.addEventListener('resize', ...)` 调 `renderer.resizeToContainer()`，会改 `canvas.width/height`。**新增**：resize 监听里**也**调一次 `onMove()`，否则 canvas 位置会基于旧的中心 / 新的尺寸不一致 |
| 用户双击地图 | `doubleClickZoom: false` 禁用；Leaflet 不响应，行为 = 单击（无 pan） |
| 缩放控制（+/- 按钮） | Leaflet zoom 触发 `move`；`onMove` 重定位 canvas；网格保持以 meta 中心为锚 |
| 滚轮缩放 | Leaflet 默认开启 `scrollWheelZoom`；在 cursor 处缩放。触发 `move`；canvas 位置基于 meta 中心（**不**在 cursor 下）→ 网格保持在 meta 中心，不会"飞"。这是 spec 用户选择的"锁定到 meta 中心"语义的直接结果 |
| `view.center_lat` 是非法值 | 现有 `getView()` 用 `map.getCenter()` 返回的是 Leaflet 内部值，合法；行为不变 |
| 极端 zoom（lat/lng 接近 ±90） | 现有代码用 lat=0 估算 `span_km`，行为不变；canvas 位置可能跑到屏幕外但不报错 |

## 测试

### 自动化（pytest）

新增 `tests/editor/test_editor_map_sync.py`，和 `test_editor_html.py` 同样的 server-fixture 模式：

```python
def test_canvas_positioned_at_meta_center_on_load(server_url):
    """After load, canvas center should be at the screen position of meta center."""
    # Fetch editor.html, then fetch meta.json
    # Parse meta center (default is shanghai 31.2304, 121.4737)
    # Verify editor_app.js contains _setupMapSync and latLngToContainerPoint
    # (Cannot run JS in node without a browser, so verify by string presence)
    body = _get(f"{server_url}/pipeline/editor/editor_app.js").body.decode("utf-8")
    assert "_setupMapSync" in body
    assert "latLngToContainerPoint" in body
    assert "doubleClickZoom: false" in body
```

退路（如果上面的 server fixture 不可用）：**纯静态检查**——grep `editor_app.js` 文件确认关键符号存在。

**最终方案**：退路（项目无 Playwright 依赖；和上一轮 spec 一致）。

### 手动测试（更新 `docs/editor-usage.md`）

新增 1 条说明 + 1 个手动 smoke 流程：

> - **拖动时网格跟随**：拖动地图（点击地图上 canvas 之外的区域）时，像素网格会自动跟随 meta 中心点的屏幕位置一起移动，保持与地图瓦片对齐。

手动 smoke 流程（写在 spec 末尾「开放问题」之外的 checklist 段，但实施 plan 里会展开）：

1. `just edit shanghai_50km`
2. 浏览器打开后，canvas 网格覆盖在地图中心
3. 点击地图上 canvas 之外的区域，按住拖动
4. 网格跟随地图内容一起滑动
5. 松开，网格停在拖动后的位置（不是回到中心）
6. 点击 [同步]，状态栏显示「已同步: ...」
7. 改 lat/lng 输入框，点 [应用]，地图跳到新位置，网格随之
8. 选一个城市预设，网格跳到城市中心
9. 双击地图（应该是无操作，因为 `doubleClickZoom: false`）
10. 用 zoom 控件 +/- 缩放，网格保持在 meta 中心

## 约束与非目标

- **不**改 `editor_lib.js`（纯逻辑）和 `editor_server.py`（Python 服务）
- **不**改 cellSize 行为（cells 仍是固定 CSS 像素；zoom 时不重算 size）
- **不**支持「拖动整张网格重新定位」（pan 只改 Leaflet 的 view；meta 不变）
- **不**新增显式模式切换按钮（拖动 / 绘制是同一交互的两个动作）
- **不**改 [应用] / [同步] / [城市预设] 按钮的语义
- **不**新增服务端代码、npm 依赖、配置文件
- `BackgroundAligner` 改动**仅一行**（`doubleClickZoom: false`）

## 开放问题

（无——所有路径已和用户确认）
