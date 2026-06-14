# 地图编辑器 — 拖动 / 绘制时网格对齐 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复编辑器里「拖动地图时像素网格不跟随」的 bug —— canvas 位置应该跟随 meta 中心的屏幕位置滑动，保持与地图瓦片 1:1 对齐。

**Architecture:** 监听 Leaflet `map.on('move', ...)` 事件，在回调里用 `map.latLngToContainerPoint(this._centerLatLng)` 算出锚点屏幕位置，再设置 `canvas.style.left/top` 让网格中心对齐到该位置。锚点 `this._centerLatLng` 在 4 个时机更新：构造器、`_applyMeta`、`_syncMeta`、`_applyCity`。另在 `BackgroundAligner` 加 `doubleClickZoom: false` 避免双击画画时被误触 zoom。Window resize 也调一次 `onMove` 让位置 / 尺寸同步。

**Tech Stack:** 原生 JS（无打包器）、Leaflet（CDN）、Python 3（http.server、pytest）。`editor_lib.js`（纯逻辑）和 `editor_server.py`（Python）不动。

---

## 文件结构

修改：
- `pipeline/editor/editor_app.js`（5 处：构造器 + 2 个新方法 + 3 个 handler 锚点更新 + resize 钩子 + 1 行 BackgroundAligner 构造器）
- `docs/editor-usage.md`（操作 section 新增 1 条说明）

新增：
- `tests/editor/test_editor_map_sync.py`（纯静态检查，3 个断言）

不动的：
- `pipeline/editor/editor.html`、`editor_lib.js`、`tile_paths.js`、`meta.json`
- `pipeline/editor/editor_server.py`
- `justfile`

---

## Task 1: BackgroundAligner disable doubleClickZoom

**Files:**
- Modify: `pipeline/editor/editor_app.js:125-131`（BackgroundAligner 构造器）

- [ ] **Step 1: 改 BackgroundAligner 构造器的 `L.map` 选项**

编辑 `pipeline/editor/editor_app.js`，把 BackgroundAligner 构造器：

```js
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true });
    this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.map);
  }
```

替换为：

```js
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true, doubleClickZoom: false });
    this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.map);
  }
```

效果：用户双击地图不再触发 zoom（避免双击画画时被误触，grid 也不会跳到双击点）。

- [ ] **Step 2: 语法检查**

Run: `node --check /Users/lsq/env/assets/game/pipeline/editor/editor_app.js`
Expected: `SYNTAX OK`（无输出 = 成功）

- [ ] **Step 3: 提交**

```bash
cd /Users/lsq/env/assets/game
git add pipeline/editor/editor_app.js
git commit -m "feat(editor): disable Leaflet doubleClickZoom to prevent accidental grid jump"
```

---

## Task 2: MapEditor 加 _onMapMove + _setupMapSync + 构造器初始化锚点

**Files:**
- Modify: `pipeline/editor/editor_app.js:221-263`（MapEditor 构造器 + 新增 2 个方法）

- [ ] **Step 1: 构造器内加锚点字段 + 调 `_setupMapSync()`**

编辑 `pipeline/editor/editor_app.js`，在 `MapEditor` 构造器内，把这一段：

```js
    this.toolbar.loadCityPresets(cityPresets);
    this.toolbar.setMeta(meta);
    this.pen = 'G';
    this._baseOpacity = 1;
    this._setupMouse();
    this._setupResize();
    this._loadDraft();
    this._fitGridToView();
    this.renderer.drawAll();
  }
```

替换为：

```js
    this.toolbar.loadCityPresets(cityPresets);
    this.toolbar.setMeta(meta);
    this.pen = 'G';
    this._baseOpacity = 1;
    this._centerLatLng = L.latLng(meta.center_lat, meta.center_lng);
    this._setupMouse();
    this._setupResize();
    this._loadDraft();
    this._fitGridToView();
    this.renderer.drawAll();
    this._setupMapSync();
  }
```

效果：构造器最后一步注册 Leaflet move 监听 + 设置初始 canvas 位置。

- [ ] **Step 2: 新增 `_setupMapSync` + `_onMapMove` 方法**

紧跟 `_fitGridToView` 方法（**注意**：在 `_fitGridToView` 之后、`_undo` 之前）插入：

```js
  _setupMapSync() {
    this.aligner.map.on('move', this._onMapMove.bind(this));
    this._onMapMove();
  }

  _onMapMove() {
    const pt = this.aligner.map.latLngToContainerPoint(this._centerLatLng);
    const cellSize = this.renderer.cellSize();
    this.canvas.style.left = (pt.x - this.grid.cols * cellSize / 2) + 'px';
    this.canvas.style.top = (pt.y - this.grid.rows * cellSize / 2) + 'px';
  }
```

完整位置（参考）：在 `MapEditor` 类内，方法顺序为：

```
constructor
_setupMouse
_setupResize
_fitGridToView
_setupMapSync    ← 新增
_onMapMove       ← 新增
_undo
_redo
_clear
_export
_syncMeta
_toggleBaseLayer
_applyMeta
_applyCity
_loadDraft
_saveDraft
```

效果：
- `_setupMapSync` 注册 Leaflet `move` 事件 + 立即调一次 `_onMapMove` 设置初始位置
- `_onMapMove` 算出 meta 中心的屏幕位置，把 canvas 中心对齐到该位置

- [ ] **Step 3: 语法检查**

Run: `node --check /Users/lsq/env/assets/game/pipeline/editor/editor_app.js`
Expected: 无输出（成功）

- [ ] **Step 4: 提交**

```bash
cd /Users/lsq/env/assets/game
git add pipeline/editor/editor_app.js
git commit -m "feat(editor): add _setupMapSync and _onMapMove to track grid on map pan"
```

---

## Task 3: MapEditor 3 个 handler 加锚点更新 + resize 联动

**Files:**
- Modify: `pipeline/editor/editor_app.js`（`_applyMeta` / `_syncMeta` / `_applyCity` / `_setupResize`）

- [ ] **Step 1: `_applyMeta` 加锚点更新**

找到 `_applyMeta` 方法（紧跟 `_toggleBaseLayer` 之后），把：

```js
  _applyMeta() {
    const m = this.toolbar.getMeta();
    if (m.rows !== this.grid.rows || m.cols !== this.grid.cols) {
      if (!confirm(`改变 grid 尺寸到 ${m.rows}x${m.cols}（破坏性）。继续？`)) return;
      this.history.push(this.grid);
      this.grid.resize(m.rows, m.cols);
      this._fitGridToView();
      this.renderer.drawAll();
    }
    this.aligner.setView(m);
  }
```

替换为：

```js
  _applyMeta() {
    const m = this.toolbar.getMeta();
    if (m.rows !== this.grid.rows || m.cols !== this.grid.cols) {
      if (!confirm(`改变 grid 尺寸到 ${m.rows}x${m.cols}（破坏性）。继续？`)) return;
      this.history.push(this.grid);
      this.grid.resize(m.rows, m.cols);
      this._fitGridToView();
      this.renderer.drawAll();
    }
    this._centerLatLng = L.latLng(m.center_lat, m.center_lng);
    this.aligner.setView(m);  // triggers Leaflet 'move' event → _onMapMove runs
  }
```

效果：用户点 [应用] 后锚点更新到新 meta，Leaflet `setView` 触发 `move` 事件 → `_onMapMove` 自动重定位 canvas。

- [ ] **Step 2: `_syncMeta` 加锚点更新 + 显式调 `_onMapMove`**

找到 `_syncMeta` 方法（紧跟 `_export` 之后），把：

```js
  _syncMeta() {
    const view = this.aligner.getView();
    // Blur inputs first so focus doesn't fight the value write.
    ['lat', 'lng', 'span'].forEach(id => document.getElementById(id).blur());
    this.toolbar.setMeta({
      ...this.toolbar.getMeta(),
      center_lat: view.center_lat,
      center_lng: view.center_lng,
      span_km: parseFloat(view.span_km.toFixed(1)),
    });
    this.toolbar.setStatus(`已同步: ${view.center_lat.toFixed(4)}, ${view.center_lng.toFixed(4)}`);
  }
```

替换为：

```js
  _syncMeta() {
    const view = this.aligner.getView();
    // Blur inputs first so focus doesn't fight the value write.
    ['lat', 'lng', 'span'].forEach(id => document.getElementById(id).blur());
    this.toolbar.setMeta({
      ...this.toolbar.getMeta(),
      center_lat: view.center_lat,
      center_lng: view.center_lng,
      span_km: parseFloat(view.span_km.toFixed(1)),
    });
    this.toolbar.setStatus(`已同步: ${view.center_lat.toFixed(4)}, ${view.center_lng.toFixed(4)}`);
    this._centerLatLng = L.latLng(view.center_lat, view.center_lng);
    this._onMapMove();
  }
```

效果：用户点 [同步] 后锚点更新到当前地图视图；`_onMapMove()` 显式触发（因为没调 setView，Leaflet 不会自动 fire move）。

- [ ] **Step 3: `_applyCity` 加锚点更新**

找到 `_applyCity` 方法（紧跟 `_applyMeta` 之后），把：

```js
  _applyCity(name) {
    // Use the existing resolve_meta semantics (best-effort without import).
    // For simplicity, hardcode the same 5 cities.
    const presets = {
      shanghai: { center_lat: 31.2304, center_lng: 121.4737, span_km: 50 },
      beijing:  { center_lat: 39.9042, center_lng: 116.4074, span_km: 50 },
      hangzhou: { center_lat: 30.2741, center_lng: 120.1551, span_km: 40 },
      syracuse: { center_lat: 43.0481, center_lng: -76.1474, span_km: 25 },
      tokyo:    { center_lat: 35.6762, center_lng: 139.6503, span_km: 40 },
    };
    const p = presets[name];
    if (!p) return;
    const cur = this.toolbar.getMeta();
    const newMeta = { ...cur, ...p };
    this.toolbar.setMeta(newMeta);
    this.aligner.setView(newMeta);
  }
```

替换为：

```js
  _applyCity(name) {
    // Use the existing resolve_meta semantics (best-effort without import).
    // For simplicity, hardcode the same 5 cities.
    const presets = {
      shanghai: { center_lat: 31.2304, center_lng: 121.4737, span_km: 50 },
      beijing:  { center_lat: 39.9042, center_lng: 116.4074, span_km: 50 },
      hangzhou: { center_lat: 30.2741, center_lng: 120.1551, span_km: 40 },
      syracuse: { center_lat: 43.0481, center_lng: -76.1474, span_km: 25 },
      tokyo:    { center_lat: 35.6762, center_lng: 139.6503, span_km: 40 },
    };
    const p = presets[name];
    if (!p) return;
    const cur = this.toolbar.getMeta();
    const newMeta = { ...cur, ...p };
    this.toolbar.setMeta(newMeta);
    this._centerLatLng = L.latLng(newMeta.center_lat, newMeta.center_lng);
    this.aligner.setView(newMeta);  // triggers Leaflet 'move' → _onMapMove runs
  }
```

效果：选城市预设后锚点更新到新城市中心，Leaflet `setView` 触发 `move` → canvas 重定位。

- [ ] **Step 4: `_setupResize` 加 `_onMapMove` 联动**

找到 `_setupResize` 方法（紧跟 `_setupMouse` 之后），把：

```js
  _setupResize() {
    this.renderer.resizeToContainer();
    window.addEventListener('resize', () => this.renderer.resizeToContainer());
  }
```

替换为：

```js
  _setupResize() {
    this.renderer.resizeToContainer();
    window.addEventListener('resize', () => {
      this.renderer.resizeToContainer();
      this._onMapMove();
    });
  }
```

效果：window resize 后 canvas 尺寸变了，位置也要重算（基于新尺寸的 cellSize）。

- [ ] **Step 5: 语法检查**

Run: `node --check /Users/lsq/env/assets/game/pipeline/editor/editor_app.js`
Expected: 无输出

- [ ] **Step 6: 提交**

```bash
cd /Users/lsq/env/assets/game
git add pipeline/editor/editor_app.js
git commit -m "feat(editor): update grid anchor on meta change and resize"
```

---

## Task 4: 新增静态测试

**Files:**
- Create: `tests/editor/test_editor_map_sync.py`

- [ ] **Step 1: 写测试**

```python
# tests/editor/test_editor_map_sync.py
"""Static smoke test: verify map-grid sync symbols are wired up.

The DOM-coupled JS code (BackgroundAligner / MapEditor) can't be unit-tested
in node without a browser. This catches the most common regressions:
- _setupMapSync / _onMapMove not added
- doubleClickZoom not disabled
- latLngToContainerPoint not called
"""
import http.client
import socketserver
import threading
import time

import pytest

from pipeline.editor.editor_server import (
    write_meta,
    write_tile_paths_to,
    resolve_meta,
    find_free_port,
    EditorHandler,
    EDITOR_DIR,
)


@pytest.fixture(scope="module")
def server_url():
    """Boot the editor server on a free port; yield base URL."""
    meta = resolve_meta(name="htmltest", city="shanghai", rows=3, cols=3)
    write_meta(meta, EDITOR_DIR / "meta.json")
    write_tile_paths_to(EDITOR_DIR / "tile_paths.js")

    port = find_free_port()
    httpd = socketserver.TCPServer(("127.0.0.1", port), EditorHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str) -> tuple[int, bytes]:
    """GET an http:// URL via stdlib http.client. Mirrors test_editor_html._get."""
    assert url.startswith("http://")
    after_scheme = url[len("http://"):]
    host_port, _, path = after_scheme.partition("/")
    host, port = host_port.split(":", 1)
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.request("GET", "/" + path, headers={"Connection": "close"})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_map_sync_symbols_present(server_url):
    """Editor app must wire up the map-grid sync feature."""
    status, body = _get(f"{server_url}/pipeline/editor/editor_app.js")
    assert status == 200
    text = body.decode("utf-8")
    assert "_setupMapSync" in text, "missing _setupMapSync method"
    assert "_onMapMove" in text, "missing _onMapMove method"
    assert "latLngToContainerPoint" in text, "missing latLngToContainerPoint call"
    assert "doubleClickZoom: false" in text, "doubleClickZoom not disabled"
```

- [ ] **Step 2: 跑测试确认通过**

Run: `cd /Users/lsq/env/assets/game && uv run --with pytest python3 -m pytest tests/editor/test_editor_map_sync.py -v`
Expected: `1 passed in 0.7s`

- [ ] **Step 3: 故意删一个关键符号，验证测试能 catch**

```bash
cd /Users/lsq/env/assets/game
sed -i.bak 's|_setupMapSync|_setupMapSync_X|' pipeline/editor/editor_app.js
uv run --with pytest python3 -m pytest tests/editor/test_editor_map_sync.py -v
# Expected: FAILED (assert on _setupMapSync)
sed -i.bak 's|_setupMapSync_X|_setupMapSync|' pipeline/editor/editor_app.js
rm pipeline/editor/editor_app.js.bak
```

- [ ] **Step 4: 提交**

```bash
cd /Users/lsq/env/assets/game
git add tests/editor/test_editor_map_sync.py
git commit -m "test(editor): add static smoke test for map-grid sync wiring"
```

---

## Task 5: 更新使用文档

**Files:**
- Modify: `docs/editor-usage.md:14-25`（操作 section）

- [ ] **Step 1: 在「移动底图」之后、「城市预设」之前插入 1 条新说明**

编辑 `docs/editor-usage.md`，把这一段：

```markdown
- **移动底图**：拖动地图（不要在画布上点，会进入绘制模式）。如果想用滚轮缩放，按 [应用] 让 span_km 同步。
- **城市预设**：工具栏下拉选城市，lat/lng/span 自动填好。
```

替换为：

```markdown
- **移动底图**：拖动地图（不要在画布上点，会进入绘制模式）。如果想用滚轮缩放，按 [应用] 让 span_km 同步。网格会自动跟随地图一起移动，保持与瓦片对齐。
- **城市预设**：工具栏下拉选城市，lat/lng/span 自动填好。
```

效果：在「移动底图」bullet 末尾追加一句说明网格跟随行为。无新增独立 bullet。

- [ ] **Step 2: 提交**

```bash
cd /Users/lsq/env/assets/game
git add docs/editor-usage.md
git commit -m "docs(editor): document grid follow-on-pan behavior"
```

---

## Task 6: 端到端 manual smoke（验证用，无 commit）

**Files:** none（验证用，不提交任何新文件）

- [ ] **Step 1: 跑现有测试套件确认未破坏**

Run: `cd /Users/lsq/env/assets/game && uv run --with pytest python3 -m pytest tests/ -v 2>&1 | tail -20`
Expected: 81+ passed, 2 pre-existing failed（与本计划无关）

- [ ] **Step 2: 9 项静态检查**

- [ ] `node --check pipeline/editor/editor_app.js` → SYNTAX OK
- [ ] `grep _setupMapSync pipeline/editor/editor_app.js` → 1 hit
- [ ] `grep _onMapMove pipeline/editor/editor_app.js` → 1 hit
- [ ] `grep "latLngToContainerPoint" pipeline/editor/editor_app.js` → 1 hit
- [ ] `grep "doubleClickZoom: false" pipeline/editor/editor_app.js` → 1 hit
- [ ] `grep "_centerLatLng" pipeline/editor/editor_app.js` → 5+ hits (constructor + 4 handlers)
- [ ] `git diff 8edbef9..HEAD -- pipeline/editor/editor_app.js` 只动 `MapEditor` + `BackgroundAligner` 类内部
- [ ] `tests/editor/test_editor_html.py` 仍 2 passed
- [ ] `tests/editor/test_editor_map_sync.py` 1 passed

- [ ] **Step 3: 清理 fixture 副作用（重要）**

每次跑 `test_editor_html.py` / `test_editor_map_sync.py` 都会覆盖 `pipeline/editor/meta.json` 和 `tile_paths.js`。smoke 结束后必须恢复：

```bash
cd /Users/lsq/env/assets/game
git checkout -- pipeline/editor/meta.json pipeline/editor/tile_paths.js
git status  # 确认无未提交改动
```

- [ ] **Step 4: 报告**

不需要 commit。把 Step 1-3 的输出和 git log 列在最终报告里。

---

## Self-Review

**1. Spec coverage：**
- 「拖动时网格跟随」行为 ✓ Task 2 (`_setupMapSync` 监听 move 事件)
- 「绘制时地图不动」行为 ✓ 无改动（canvas `pointer-events: auto` 保留）
- 「锁定到 meta 中心」语义 ✓ Task 2 (`_centerLatLng` 初始化) + Task 3 (3 个 handler 锚点更新)
- 「disable doubleClickZoom」✓ Task 1
- 「resize 联动」✓ Task 3 Step 4
- 「自动化测试」✓ Task 4（静态检查）
- 「手动 smoke」✓ Task 6
- 「文档更新」✓ Task 5

**2. 占位符扫描：** 无 TBD/TODO。所有代码块都是完整可粘贴的。

**3. 类型 / 方法名一致性：**
- `_setupMapSync` / `_onMapMove` 在 Task 2 定义 → Task 3 (4 处) 调用 → Task 4 测试断言
- `_centerLatLng` 字段名在 Task 2 初始化 → Task 3 4 处更新 → Task 6 grep 验证
- `L.latLng(...)` 在 Task 2 / 3 5 处使用一致
- `doubleClickZoom: false` 在 Task 1 加 → Task 4 测试断言

无不一致。
