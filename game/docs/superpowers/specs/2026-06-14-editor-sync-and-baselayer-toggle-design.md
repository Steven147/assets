# 地图编辑器 — 底图切换 & 同步按钮

**日期：** 2026-06-14
**状态：** 已批准，待实现

## 目标

在 `just edit` 启动的地图编辑器里加 2 个小功能：

1. **底图切换按钮**：循环切换 OSM 底图可视性（实 / 半透 / 隐）。便于用户在专注绘制时隐藏底图，又能在需要时快速找回作为对齐参考。
2. **同步按钮**：手动把 Leaflet 地图当前视图（center lat/lng + span_km）写回工具栏输入框。便于用户拖动地图找准位置后，把状态固化到输入框里。

不动现有 [应用] 按钮语义（应用 = 从工具栏写回地图）。

## 架构

改动局限在 3 个类 + 1 个 HTML 文件，无新文件、无新依赖：

- `pipeline/editor/editor.html` — 工具栏新增 2 个按钮 + 1 个 section 标题。
- `pipeline/editor/editor_app.js` — `BackgroundAligner` 加 `setOpacity`，`Toolbar` 加 2 个 handler 注册点和按钮 DOM，`MapEditor` 加 2 个方法。
- `pipeline/editor/editor_lib.js` — **不动**（保持纯逻辑零 DOM 依赖）。
- `pipeline/editor/editor_server.py` — **不动**。

## 组件变化

### `BackgroundAligner`（在 `editor_app.js`）

新增 1 个方法：

```js
/** Set OSM tile layer opacity. value ∈ {0, 0.5, 1}. */
setOpacity(value) {
  this.tileLayer.setOpacity(value);
}
```

构造器内把 `L.tileLayer(...).addTo(this.map)` 的返回值保存为 `this.tileLayer`。

现有 `getView()` 已经返回 `{ center_lat, center_lng, span_km }` 形状，**直接复用**，无需改名或包装。

### `Toolbar`（在 `editor_app.js`）

构造器内新增 2 行 DOM 绑定：

```js
document.getElementById('sync-meta').onclick = () => handlers.syncMeta();
document.getElementById('toggle-base').onclick = () => handlers.toggleBaseLayer();
```

新增 1 个方法：

```js
/** Update the baselayer toggle button label. */
setBaseLayerLabel(text) {
  document.getElementById('toggle-base').textContent = `底图: ${text}`;
}
```

### `MapEditor`（在 `editor_app.js`）

构造器内 `Toolbar` handler 注册新增 2 项：

```js
syncMeta: () => this._syncMeta(),
toggleBaseLayer: () => this._toggleBaseLayer(),
```

新增 2 个实例方法：

```js
_syncMeta() {
  const view = this.aligner.getView();
  // Blur first so the input's focus state doesn't fight us.
  ['lat', 'lng', 'span'].forEach(id => document.getElementById(id).blur());
  this.toolbar.setMeta({
    ...this.toolbar.getMeta(),
    center_lat: view.center_lat,
    center_lng: view.center_lng,
    span_km: parseFloat(view.span_km.toFixed(1)),
  });
  this.toolbar.setStatus(`已同步: ${view.center_lat.toFixed(4)}, ${view.center_lng.toFixed(4)}`);
}

_toggleBaseLayer() {
  // Cycle 1 → 0.5 → 0 → 1
  const order = [1, 0.5, 0];
  const idx = order.indexOf(this._baseOpacity);
  const next = order[(idx + 1) % order.length];
  this._baseOpacity = next;
  this.aligner.setOpacity(next);
  const labels = { 1: '实', 0.5: '半透', 0: '隐' };
  this.toolbar.setBaseLayerLabel(labels[next]);
}
```

构造器内新增 1 行：`this._baseOpacity = 1;`（默认状态，匹配现有行为）。

## UI 改动

`pipeline/editor/editor.html` 工具栏「画布」section 末尾新增：

```html
<h2>底图</h2>
<button id="toggle-base">底图: 实</button>
<button id="sync-meta">同步</button>
```

**位置决策**：
- 「同步」按钮放在「画布」section 内，[应用] 按钮 **下面**。理由：和它作用的 3 个输入框同 section，用户一眼能看出关系。
- 底图切换按钮放在新 section「底图」内。理由：底图是地图渲染概念，独立于画布 meta。

## 数据流

### 同步按钮

1. 用户拖动 Leaflet 地图（pan / zoom）。
2. 工具栏的 lat/lng/span **不变**（不自动同步，按用户要求是手动）。
3. 用户点「同步」。
4. `_syncMeta()` → `aligner.getView()` → 返回 `{ center_lat, center_lng, span_km }`。
5. `Toolbar.setMeta()` 把 3 个值写进输入框（span 保留 1 位小数）。
6. 状态栏显示「已同步: <lat>, <lng>」。

### 底图切换按钮

1. 默认状态：`opacity = 1`，按钮显示「底图: 实」。
2. 用户点 → `_toggleBaseLayer()` → 状态切到 0.5 → `aligner.setOpacity(0.5)` → 按钮显示「底图: 半透」。
3. 再点 → 0 → 「底图: 隐」。
4. 再点 → 1 → 「底图: 实」（循环）。
5. 切换只影响 Leaflet tile layer，**不影响** canvas 网格绘制。
6. `setView` / 导出 / 撤销等现有功能不受影响。

## 错误处理

| 场景 | 行为 |
|------|------|
| 用户从未移动地图就点同步 | 工具栏值与地图一致，写回相同值，no-op，无报错 |
| `getView()` 异常（地图未初始化） | 现有 `Math.max(0.1, spanKm)` 兜底，行为不变 |
| 切到「隐」后想恢复 | 继续点按钮循环回「实」即可 |
| 同步时 lat/lng 输入框被聚焦 | 先 `blur()` 再写值，避免残留 focus 干扰 |

## 测试

### 自动化（pytest）

新增 `tests/test_editor_sync_and_baselayer.py`，端到端：

1. 启动 `editor_server.py`（子进程）。
2. 用 Playwright 打开 `editor.html`。
3. 断言初始底图按钮文案是「底图: 实」。
4. 点击底图按钮 1 次 → 断言文案「底图: 半透」+ Leaflet tileLayer.opacity === 0.5。
5. 再点 2 次 → 回到「底图: 实」+ opacity === 1。
6. 程序化调用 `aligner.setView({ center_lat: 31.5, center_lng: 121.5, span_km: 60 })`。
7. 点击「同步」按钮 → 断言 3 个输入框的值与设置的一致。
8. 关闭浏览器、子进程。

如果 Playwright 不可用，退化为纯 JS 单元测试：在 Node 环境加载 `editor_app.js` 的 `BackgroundAligner` 类，绕过 Leaflet 直接验证 `setOpacity` / `getView` 行为。

### 手动测试（更新 `docs/editor-usage.md`）

「操作」section 新增：

- **切换底图**：工具栏「底图」按钮循环「实 / 半透 / 隐」，对应 OSM 瓦片可见性。
- **同步视图**：拖动或缩放地图后，点「同步」会把当前中心点 + 跨度写回 lat / lng / span 输入框。

## 约束与非目标

- **不**自动同步：用户明确选择手动同步，避免工具栏值频繁抖动打断输入。
- **不**改 [应用] 按钮语义：仍然是「工具栏 → 地图」的反向。
- **不**改导出、撤销、清空、城市预设、画笔等其他功能。
- **不**新增服务端代码。
- **不**新增 npm 依赖。
- **不**引入滑块或更复杂的底图控制：三档循环是用户明确选择。
- 同步写回时不触发 `applyMeta` 副作用：因为我们不调 `setView`。

## 开放问题

（无——所有路径已和用户确认）
