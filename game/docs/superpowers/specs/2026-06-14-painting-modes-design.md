# 地图编辑器 — 三种画笔模式

**日期：** 2026-06-14
**状态：** 已批准（用户跳过 review），待实现

## 目标

把当前单一「拖动 = 画 1 格」的行为升级为 3 种互斥的画笔模式：

1. **拖动（map dragger）**：拖动 = 平移地图，不画格
2. **画格（drag painter）**：拖动 = 画 1 格（当前默认行为）
3. **画 6×6（bigger drag painter）**：拖动 = 以鼠标点为中心画 6×6 区域，边画边显示虚线轮廓

切换通过工具栏的 3 个按钮。默认是「画格」。

## 架构

改动局限在 `pipeline/editor/editor.html`（加 3 个按钮 + 1 个 brush outline div + CSS）和 `pipeline/editor/editor_app.js`（MapEditor 加 1 个字段 + 1 个 setter + 改 `_setupMouse` + 1 个 outline 更新方法）。`BackgroundAligner` / `Toolbar` / `Renderer` / `TileLoader` / `editor_lib.js` 都不动。

## 组件变化

### `MapEditor`（在 `editor_app.js`）

构造器内新增（紧跟 `this._baseOpacity = 1;` 之后）：
```js
this._mode = 'painter';  // default mode (current behavior)
this._setupBrushOutline();
```

新增 2 个方法：
```js
_setMode(mode) {
  this._mode = mode;
  // Disable canvas mouse capture in dragger mode so Leaflet gets events.
  this.canvas.style.pointerEvents = (mode === 'dragger') ? 'none' : 'auto';
  // Update toolbar active state.
  ['dragger', 'painter', 'bigger'].forEach(m => {
    document.getElementById(`mode-${m}`).classList.toggle('active', m === mode);
  });
  // Hide brush outline when not in bigger mode.
  if (mode !== 'bigger') {
    this._brushOutline.style.display = 'none';
  }
  this.toolbar.setStatus(`模式: ${this._modeLabel(mode)}`);
}

_modeLabel(mode) {
  return { dragger: '拖动', painter: '画格', bigger: '画 6×6' }[mode] || mode;
}

_setupBrushOutline() {
  // Create the brush outline element programmatically (no HTML edit needed).
  const div = document.createElement('div');
  div.id = 'brush-outline';
  div.style.cssText = 'position:absolute;pointer-events:none;border:2px dashed rgba(255,255,255,0.85);display:none;z-index:401;box-sizing:border-box;';
  this.canvas.parentElement.appendChild(div);
  this._brushOutline = div;
}

_updateBrushOutline(r, c) {
  if (this._mode !== 'bigger' || r < 0 || c < 0 || r >= this.grid.rows || c >= this.grid.cols) {
    this._brushOutline.style.display = 'none';
    return;
  }
  const cellSize = this.renderer.cellSize();
  this._brushOutline.style.width = (6 * cellSize) + 'px';
  this._brushOutline.style.height = (6 * cellSize) + 'px';
  this._brushOutline.style.left = ((c - 3) * cellSize) + 'px';
  this._brushOutline.style.top = ((r - 3) * cellSize) + 'px';
  this._brushOutline.style.display = 'block';
}
```

改 `_setupMouse`：
- 在 `onMove` 闭包内，根据 `this._mode` 决定 paint 范围
- 提取 `_paintAt(r, c)` 方法

```js
_paintAt(r, c) {
  if (this._mode === 'bigger') {
    // 6x6 area centered on (r, c). Out-of-bounds skipped.
    for (let dr = -3; dr <= 2; dr++) {
      for (let dc = -3; dc <= 2; dc++) {
        const nr = r + dr;
        const nc = c + dc;
        if (nr < 0 || nr >= this.grid.rows || nc < 0 || nc >= this.grid.cols) continue;
        if (this.grid.get(nr, nc) !== this.pen) {
          this.grid.set(nr, nc, this.pen);
          this.renderer.redrawAround(nr, nc);
        }
      }
    }
  } else {
    // painter mode: 1 cell
    if (this.grid.get(r, c) !== this.pen) {
      this.grid.set(r, c, this.pen);
      this.renderer.redrawAround(r, c);
    }
  }
}

_setupMouse() {
  let isPainting = false;
  const onMove = (ev) => {
    const rect = this.canvas.getBoundingClientRect();
    const { r, c } = this.renderer.pixelToCell(ev.clientX - rect.left, ev.clientY - rect.top);
    if (r < 0 || c < 0 || r >= this.grid.rows || c >= this.grid.cols) {
      this._updateBrushOutline(-1, -1);
      return;
    }
    this._updateBrushOutline(r, c);
    if (isPainting) this._paintAt(r, c);
  };
  this.canvas.onmousedown = (ev) => {
    if (this._mode === 'dragger') return;  // shouldn't fire (pointer-events: none)
    isPainting = true;
    this.history.push(this.grid);
    onMove(ev);
  };
  this.canvas.onmousemove = (ev) => onMove(ev);
  document.addEventListener('mouseup', () => { isPainting = false; });
  this.canvas.onmouseleave = () => {
    isPainting = false;
    this._updateBrushOutline(-1, -1);
  };
}
```

Toolbar handler 注册新增 1 项：
```js
setMode: (m) => this._setMode(m),
```

### `editor.html`

新增 1 个 section（在 `## 画笔` section 之前）：
```html
<h2>工具</h2>
<div class="pen-row" id="modes">
  <button id="mode-dragger" title="拖动 = 平移地图">拖动</button>
  <button id="mode-painter" class="active" title="拖动 = 画 1 格">画格</button>
  <button id="mode-bigger" title="拖动 = 画 6×6 区域">画 6×6</button>
</div>
```

### 不动的文件

- `editor_lib.js`（纯逻辑）
- `editor_server.py`（Python）
- `BackgroundAligner` / `Renderer` / `TileLoader`

## UI 行为

- **默认模式**：`painter`（与现有行为一致）
- **拖动模式**：canvas 鼠标穿透到 Leaflet → pan 地图，**不**画格。`pointerEvents = 'none'`。
- **画格模式**：拖动 = 画 1 格（中心 cell）
- **画 6×6 模式**：拖动 = 画 6×6 区域（中心 cell 周围 ±3 行 ±3 列）；鼠标在 canvas 上时显示虚线轮廓跟随
- **按钮 active 态**：用现有 `.active` CSS class

## 数据流

### 切换模式

1. 用户点「画 6×6」按钮
2. Toolbar handler `setMode('bigger')` → `_setMode('bigger')`
3. `_mode = 'bigger'`
4. canvas pointerEvents 保持 `auto`
5. toolbar 3 个按钮的 active class 重置
6. 状态栏显示「模式: 画 6×6」

### 画 6×6 拖动

1. mousedown on canvas → push history → `_paintAt(r, c)` → 画 6×6
2. mousemove → 调 `_paintAt(r, c)` 更新 6×6 区域；调 `_updateBrushOutline(r, c)` 更新虚线位置
3. mouseleave canvas → `_updateBrushOutline(-1, -1)` 隐藏虚线

### 拖动模式平移

1. canvas `pointer-events: none`（已在 `_setMode('dragger')` 时设置）
2. mousedown 穿透到 Leaflet tilePane
3. Leaflet pan → 触发 `move` 事件 → `_onMapMove` 重定位 canvas（已有逻辑）

## 错误处理

| 场景 | 行为 |
|------|------|
| 6×6 越界 | 跳过越界 cell，不报错 |
| 拖动模式点 toolbar 按钮 | 正常响应（toolbar 在 #toolbar div，与 canvas pointer-events 无关） |
| 拖动模式拖到 canvas 外 | Leaflet pan 持续（原生行为） |
| 模式切换中途中断 paint | history 已经 push，下次 mousedown 会 push 新的；切换不影响 grid 内容 |
| 鼠标在 canvas 外时 6×6 轮廓 | 隐藏（`_updateBrushOutline(-1, -1)`） |

## 测试

### 自动化（pytest）

扩展 `tests/editor/test_editor_map_sync.py`，新增 3 个断言：
- `id="mode-dragger"` 存在
- `id="mode-painter"` 存在
- `id="mode-bigger"` 存在

### 手动 smoke

`docs/editor-usage.md` 操作 section 新增 1 条说明（位置在「画笔」之前或之后均可）：

> - **切换工具**：工具栏「工具」section 选「拖动 / 画格 / 画 6×6」。拖动模式鼠标拖动画布 = 平移地图；画格模式拖动 = 画 1 格；画 6×6 模式拖动 = 画以鼠标为中心的 6×6 区域，鼠标在画布上时显示虚线轮廓。

## 约束与非目标

- **不**保存模式到 localStorage（UI 状态，不需要持久化）
- **不**改 `BackgroundAligner` / `Renderer` / `editor_lib.js`
- **不**改 [应用] / [同步] / [城市预设] / [底图切换] 按钮
- **不**新增显式快捷键
- 6×6 大小**硬编码**（6 在两处出现：_updateBrushOutline 宽高，_paintAt 循环范围）
- 模式切换**不**重置 history / 不清空 grid

## 开放问题

（无——所有路径已和用户确认）
