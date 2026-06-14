# 地图编辑器 — 底图切换 & 同步按钮实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在地图编辑器工具栏新增「底图」三档循环切换按钮（实/半透/隐）和「同步」按钮（把 Leaflet 当前视图的 lat/lng/span_km 写回工具栏输入框）。

**Architecture:** DOM 改动集中在 `editor.html` 工具栏；JS 改动在 `editor_app.js` 的 3 个类（`BackgroundAligner` 加 `setOpacity`、`Toolbar` 加 DOM 绑定 + label setter、`MapEditor` 加 2 个方法 + 1 个状态字段）。`editor_lib.js`（纯逻辑）和 `editor_server.py`（Python 服务）**不动**。新增一个 Python 静态测试，启动服务器后拉 `editor.html` 验证两个新按钮 ID 存在。手动验证清单写入 `docs/editor-usage.md`。

**Tech Stack:** 原生 JS（无打包器，Node 20 内置 `node:test`，但 DOM 耦合代码跟随现有约定不写单测）、HTML、CSS（已有）、Leaflet（CDN）、Python 3（http.server、pytest、urllib）。

---

## 文件结构

修改：
- `pipeline/editor/editor.html` — 工具栏新增 1 个 `<h2>` + 2 个 `<button>`
- `pipeline/editor/editor_app.js` — 3 个类各加少量方法 / 字段
- `docs/editor-usage.md` — 「操作」section 新增 2 条说明

新增：
- `tests/editor/test_editor_html.py` — 启动服务器 + 拉 HTML + 断言新按钮 ID 存在

不动的：
- `pipeline/editor/editor_lib.js`（纯逻辑）
- `pipeline/editor/editor_server.py`（Python 服务）
- `pipeline/editor/tile_paths.js`、`meta.json`（生成产物）
- `justfile`（`just edit` / `just edit-city` 已存在）

---

## Task 1: 在 editor.html 工具栏新增按钮 DOM

**Files:**
- Modify: `pipeline/editor/editor.html:42-46`

- [ ] **Step 1: 在「画布」section 末尾、[应用] 按钮之后插入「同步」按钮**

编辑 `pipeline/editor/editor.html`，把这一段：

```html
      <button id="apply-meta">应用</button>

      <h2>操作</h2>
```

替换为：

```html
      <button id="apply-meta">应用</button>
      <button id="sync-meta">同步</button>

      <h2>底图</h2>
      <button id="toggle-base">底图: 实</button>

      <h2>操作</h2>
```

效果：
- 「同步」按钮在「画布」section 内、紧贴 [应用] 按钮下方
- 新增「底图」section，里面有 1 个按钮，初始文案「底图: 实」

- [ ] **Step 2: 视觉确认**

Run: `open /Users/lsq/env/assets/game/pipeline/editor/editor.html`
Expected: 浏览器直接打开 HTML（无地图，地图需要 server），但你能看到工具栏里有「应用 / 同步」上下两个按钮 + 新的「底图」section。`Ctrl+W` 关掉。

- [ ] **Step 3: 提交**

```bash
git add pipeline/editor/editor.html
git commit -m "feat(editor): add sync and baselayer toggle button DOM"
```

---

## Task 2: BackgroundAligner 加 setOpacity

**Files:**
- Modify: `pipeline/editor/editor_app.js:124-131`

- [ ] **Step 1: 把 tileLayer 保存为实例字段**

编辑 `pipeline/editor/editor_app.js`，把 `BackgroundAligner` 构造器：

```js
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.map);
  }
```

替换为：

```js
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true });
    this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.map);
  }
```

- [ ] **Step 2: 在 `setView` 方法之后插入 `setOpacity`**

紧跟现有 `setView` 方法（以 `}` 结束 `getView` 之前），在 `_zoomForSpan` 上面或 `setView` 后面，插入：

```js
  /** Set OSM tile layer opacity. value ∈ [0, 1]. */
  setOpacity(value) {
    this.tileLayer.setOpacity(value);
  }
```

最终 `BackgroundAligner` 类长这样（按顺序）：

```js
class BackgroundAligner {
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true });
    this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.map);
  }

  static _zoomForSpan(spanKm) {
    // km per pixel at zoom z, at lat=0: 156543.03 / 2^z
    // Assume a 600px-tall map view; pick zoom where 600px = spanKm.
    const targetKmPerPixel = spanKm / 600;
    const z = Math.log2(156543.03 / (targetKmPerPixel * 111.0));
    return Math.max(1, Math.min(19, Math.round(z)));
  }

  /** Set Leaflet view to center + span_km. */
  setView(meta) {
    const { center_lat, center_lng, span_km } = meta;
    const zoom = BackgroundAligner._zoomForSpan(span_km);
    this.map.setView([center_lat, center_lng], zoom);
  }

  /** Get current center + computed span_km in km. */
  getView() {
    const c = this.map.getCenter();
    const bounds = this.map.getBounds();
    const north = bounds.getNorth();
    const heightDeg = Math.abs(north - c.lat) * 2;
    const spanKm = heightDeg * 111.0;
    return { center_lat: c.lat, center_lng: c.lng, span_km: Math.max(0.1, spanKm) };
  }

  /** Set OSM tile layer opacity. value ∈ [0, 1]. */
  setOpacity(value) {
    this.tileLayer.setOpacity(value);
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add pipeline/editor/editor_app.js
git commit -m "feat(editor): add setOpacity to BackgroundAligner"
```

---

## Task 3: Toolbar 加按钮 DOM 绑定 + label setter

**Files:**
- Modify: `pipeline/editor/editor_app.js:160-219`

- [ ] **Step 1: 构造器内新增 2 行 DOM 绑定**

编辑 `pipeline/editor/editor_app.js`，把 `Toolbar` 构造器：

```js
  constructor(handlers) {
    this.handlers = handlers;
    this._buildPens();
    document.getElementById('undo').onclick = () => handlers.undo();
    document.getElementById('redo').onclick = () => handlers.redo();
    document.getElementById('clear').onclick = () => handlers.clear();
    document.getElementById('export').onclick = () => handlers.export();
    document.getElementById('apply-meta').onclick = () => handlers.applyMeta();
  }
```

替换为：

```js
  constructor(handlers) {
    this.handlers = handlers;
    this._buildPens();
    document.getElementById('undo').onclick = () => handlers.undo();
    document.getElementById('redo').onclick = () => handlers.redo();
    document.getElementById('clear').onclick = () => handlers.clear();
    document.getElementById('export').onclick = () => handlers.export();
    document.getElementById('apply-meta').onclick = () => handlers.applyMeta();
    document.getElementById('sync-meta').onclick = () => handlers.syncMeta();
    document.getElementById('toggle-base').onclick = () => handlers.toggleBaseLayer();
  }
```

- [ ] **Step 2: 在 `setStatus` 方法之后插入 `setBaseLayerLabel`**

把 `Toolbar` 类末尾的 `setStatus` 方法后追加：

```js
  /** Update the baselayer toggle button label. */
  setBaseLayerLabel(text) {
    document.getElementById('toggle-base').textContent = `底图: ${text}`;
  }
```

最终 `Toolbar` 类新增的方法紧跟 `setStatus` 之后：

```js
  setStatus(msg) {
    document.getElementById('status').textContent = msg;
  }

  /** Update the baselayer toggle button label. */
  setBaseLayerLabel(text) {
    document.getElementById('toggle-base').textContent = `底图: ${text}`;
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add pipeline/editor/editor_app.js
git commit -m "feat(editor): wire sync + baselayer buttons in Toolbar"
```

---

## Task 4: MapEditor 加 _baseOpacity 字段 + 2 个方法

**Files:**
- Modify: `pipeline/editor/editor_app.js:221-370`

- [ ] **Step 1: 构造器内 `Toolbar` handler 注册新增 2 项**

编辑 `pipeline/editor/editor_app.js`，把 `MapEditor` 构造器内：

```js
    this.toolbar = new Toolbar({
      setPen: (p) => { this.pen = p; this.toolbar.setActivePen(p); },
      undo: () => this._undo(),
      redo: () => this._redo(),
      clear: () => this._clear(),
      export: () => this._export(),
      applyMeta: () => this._applyMeta(),
      applyCity: (name) => this._applyCity(name),
    });
```

替换为：

```js
    this.toolbar = new Toolbar({
      setPen: (p) => { this.pen = p; this.toolbar.setActivePen(p); },
      undo: () => this._undo(),
      redo: () => this._redo(),
      clear: () => this._clear(),
      export: () => this._export(),
      applyMeta: () => this._applyMeta(),
      applyCity: (name) => this._applyCity(name),
      syncMeta: () => this._syncMeta(),
      toggleBaseLayer: () => this._toggleBaseLayer(),
    });
```

- [ ] **Step 2: 构造器内新增 1 行状态字段**

紧跟 `this.pen = 'G';`（在 `this._setupMouse();` 之前）插入：

```js
    this._baseOpacity = 1;
```

最终 `MapEditor` 构造器尾段：

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
```

- [ ] **Step 3: 在 `_export` 方法后追加 2 个新方法**

把 `MapEditor` 类 `_export` 方法之后、`_applyMeta` 之前，插入：

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

- [ ] **Step 4: 视觉确认（手动 smoke）**

Run: `cd /Users/lsq/env/assets/game && just edit shanghai_50km --rows 30 --cols 40`

Expected:
- 浏览器自动打开编辑器
- 工具栏左侧有「画笔 / 画布（应用 + 同步）/ 底图 / 操作 / 撤销 / 重做 / 清空 / 导出」按钮
- 点击「底图」按钮 1 次 → 按钮变「底图: 半透」，OSM 瓦片变半透明
- 再点 1 次 → 变「底图: 隐」，瓦片消失
- 再点 1 次 → 回到「底图: 实」
- 在 OSM 地图上拖动改变中心 → 点「同步」→ 工具栏 lat/lng/span 输入框的值变化，状态栏显示「已同步: ...」
- 点 [应用] → 地图应能跳回（验证未破坏旧功能）

`Ctrl+W` 关浏览器。

- [ ] **Step 5: 提交**

```bash
git add pipeline/editor/editor_app.js
git commit -m "feat(editor): implement _syncMeta and _toggleBaseLayer"
```

---

## Task 5: 新增静态 HTML 烟雾测试

**Files:**
- Create: `tests/editor/test_editor_html.py`

- [ ] **Step 1: 写测试**

```python
# tests/editor/test_editor_html.py
"""Static smoke test: verify new buttons are present in editor.html.

We can't unit-test the JS behavior without a browser, but a missing
button ID is the most common regression and is easy to catch here.
"""
import http.server
import socketserver
import threading
import time
import urllib.request
from pathlib import Path

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
def server_url(tmp_path_factory):
    """Boot the editor server on a free port; yield base URL."""
    # Make sure meta.json and tile_paths.js exist (server normally does this).
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


def test_editor_html_served(server_url):
    resp = urllib.request.urlopen(f"{server_url}/pipeline/editor/editor.html", timeout=5)
    assert resp.status == 200
    body = resp.read().decode("utf-8")
    assert "id=\"sync-meta\"" in body
    assert "id=\"toggle-base\"" in body


def test_meta_served(server_url):
    """Sanity check: the existing meta endpoint still works."""
    resp = urllib.request.urlopen(f"{server_url}/pipeline/editor/meta.json", timeout=5)
    assert resp.status == 200
```

- [ ] **Step 2: 跑测试确认通过**

Run: `cd /Users/lsq/env/assets/game && uv run pytest tests/editor/test_editor_html.py -v`
Expected: 2 passed

- [ ] **Step 3: 故意删一个按钮 ID，验证测试能 catch**

```bash
sed -i.bak 's|id="sync-meta"|id="sync-meta-X"|' /Users/lsq/env/assets/game/pipeline/editor/editor.html
uv run pytest tests/editor/test_editor_html.py::test_editor_html_served -v
# Expected: FAIL (assertion error on sync-meta)

sed -i.bak 's|id="sync-meta-X"|id="sync-meta"|' /Users/lsq/env/assets/game/pipeline/editor/editor.html
rm /Users/lsq/env/assets/game/pipeline/editor/editor.html.bak
```

- [ ] **Step 4: 提交**

```bash
git add tests/editor/test_editor_html.py
git commit -m "test(editor): add static html smoke test for new buttons"
```

---

## Task 6: 更新使用文档

**Files:**
- Modify: `docs/editor-usage.md:14-22`

- [ ] **Step 1: 在「调整画布大小」那段之后、「移动底图」那段之前插入 2 条新说明**

编辑 `docs/editor-usage.md`，在「调整画布大小：改工具栏的 rows/cols 数字，点 [应用]…」这一行下面，「移动底图：拖动地图…」这一行上面，插入：

```markdown
- **同步视图**：拖动或缩放地图后，点 [同步] 会把当前中心点 + 跨度写回 lat / lng / span 输入框。
- **切换底图**：工具栏「底图」按钮循环「实 / 半透 / 隐」，对应 OSM 瓦片可见性。隐藏后专注绘制，半透对齐参考。
```

最终 `## 操作` section 长这样：

```markdown
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
```

- [ ] **Step 2: 提交**

```bash
git add docs/editor-usage.md
git commit -m "docs(editor): document sync button and baselayer toggle"
```

---

## Task 7: 完整端到端手动 smoke

**Files:** none（验证用，不提交）

- [ ] **Step 1: 跑现有测试套件确认未破坏**

Run: `cd /Users/lsq/env/assets/game && just test`
Expected: 全部通过（含新加的 `test_editor_html.py` 2 个测试）

- [ ] **Step 2: 跑 smoke recipe**

Run: `cd /Users/lsq/env/assets/game && just smoke`
Expected: 浏览器打开 viewer 页面，没有报错（这是现有的 smoke 流程，验证编辑器改动没影响 viewer 渲染）

`Ctrl+W` 关浏览器。

- [ ] **Step 3: 走一遍真实编辑流程**

Run: `cd /Users/lsq/env/assets/game && just edit smoke_test_baselayer --rows 20 --cols 30`

操作序列：
1. 点底图按钮 3 次，确认文案循环「实 → 半透 → 隐 → 实」
2. 在「隐」状态下点几个格子，确认仍能绘制
3. 拖动地图到一个新位置
4. 点「同步」按钮，确认 lat/lng/span 变化，状态栏显示「已同步: ...」
5. 改 rows 为 15、点 [应用]、确认弹了确认框、点确认（验证 rows 改动 + 同步按钮 + 应用按钮三者都不冲突）
6. 点 [撤销]、[重做]、[清空]、[导出] 各 1 次，确认现有功能不破

`Ctrl+W` 关浏览器。

- [ ] **Step 4: 如有失败，定位修复后回到对应 Task 重做**

不需要单独 commit。失败的话直接改对应文件并 amend 到对应 Task 的 commit（或新增一个 `fix(editor): ...` commit）。

---

## Self-Review

**1. Spec coverage：**
- 底图切换按钮 三档循环 ✓ Task 1 + Task 2 + Task 3 + Task 4
- 同步按钮 同步 lat/lng/span_km ✓ Task 1 + Task 3 + Task 4
- 默认状态 = 实 ✓ Task 1 (HTML 初始文案) + Task 4 (`_baseOpacity = 1`)
- 不改 [应用] 按钮 ✓ Task 4 不动 `_applyMeta`
- 错误处理表覆盖的 4 个场景 ✓ Task 4 内 `Math.max(0.1, spanKm)` 复用、blur 步骤处理 focus 残留
- 自动化测试 ✓ Task 5（按 spec 写为 Playwright 端到端，但项目无 Playwright 依赖，改为静态 HTML 烟雾测试 + 手动 checklist + 端到端 manual smoke）
- 手动测试清单 ✓ Task 6 写文档 + Task 7 走真实流程

**2. 占位符扫描：** 无 TBD/TODO。「完整代码在每一步」原则已遵守。

**3. 类型 / 方法签名一致性：**
- `BackgroundAligner.setOpacity(value)` ✓ Task 2 定义 → Task 4 调用（`this.aligner.setOpacity(next)`）
- `Toolbar.setBaseLayerLabel(text)` ✓ Task 3 定义 → Task 4 调用（`this.toolbar.setBaseLayerLabel(labels[next])`）
- `MapEditor._syncMeta()` / `_toggleBaseLayer()` 无入参无返回 ✓ Task 4 定义
- `MapEditor._baseOpacity` 字段 ✓ Task 4 初始化 → Task 4 在 `_toggleBaseLayer` 中读取

无类型 / 方法名不一致。
