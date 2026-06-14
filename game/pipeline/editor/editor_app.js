// DOM-coupled: Leaflet, Canvas, toolbar events.

import { GridModel, TileResolver, History, DeclExporter } from './editor_lib.js';

const PENS = ['G', 'O', 'R', 'r', 'L', 'S'];

class TileLoader {
  constructor() {
    this._cache = new Map();
  }
  load(path) {
    if (this._cache.has(path)) {
      return Promise.resolve(this._cache.get(path));
    }
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        this._cache.set(path, img);
        resolve(img);
      };
      img.onerror = () => reject(new Error(`failed to load: ${path}`));
      img.src = path;
    });
  }
}

class Renderer {
  constructor(canvas, tileLoader, grid, resolver) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.tileLoader = tileLoader;
    this.grid = grid;
    this.resolver = resolver;
    this._cellSize = 16;
  }

  setCellSize(px) {
    this._cellSize = Math.max(4, Math.min(64, px));
    this.drawAll();
  }

  resizeToContainer() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.drawAll();
  }

  cellSize() { return this._cellSize; }

  pixelToCell(px, py) {
    return {
      r: Math.floor(py / this._cellSize),
      c: Math.floor(px / this._cellSize),
    };
  }

  cellToPixel(r, c) {
    return { x: c * this._cellSize, y: r * this._cellSize };
  }

  drawAll() {
    this.ctx.fillStyle = 'rgba(0,0,0,0)';
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    // Draw grid lines
    this.ctx.strokeStyle = 'rgba(255,255,255,0.3)';
    this.ctx.lineWidth = 1;
    for (let c = 0; c <= this.grid.cols; c++) {
      this.ctx.beginPath();
      this.ctx.moveTo(c * this._cellSize, 0);
      this.ctx.lineTo(c * this._cellSize, this.grid.rows * this._cellSize);
      this.ctx.stroke();
    }
    for (let r = 0; r <= this.grid.rows; r++) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, r * this._cellSize);
      this.ctx.lineTo(this.grid.cols * this._cellSize, r * this._cellSize);
      this.ctx.stroke();
    }
    // Draw tiles
    for (let r = 0; r < this.grid.rows; r++) {
      for (let c = 0; c < this.grid.cols; c++) {
        this._drawCellAsync(r, c);
      }
    }
  }

  _drawCellAsync(r, c) {
    const desc = this.resolver.resolve(this.grid, r, c);
    const path = (window.TILE_PATHS || {})[desc];
    if (!path) {
      this.ctx.fillStyle = 'red';
      this.ctx.fillRect(c * this._cellSize, r * this._cellSize, this._cellSize, this._cellSize);
      return;
    }
    this.tileLoader.load(path).then(img => {
      this.ctx.drawImage(img, c * this._cellSize, r * this._cellSize, this._cellSize, this._cellSize);
    }).catch(() => {
      this.ctx.fillStyle = 'red';
      this.ctx.fillRect(c * this._cellSize, r * this._cellSize, this._cellSize, this._cellSize);
    });
  }

  drawCell(r, c) {
    this._drawCellAsync(r, c);
  }

  /** Redraw the 3x3 region around (r, c). Used after painting one cell so the
   *  neighbor tiles re-resolve with the new context. The center is included
   *  too (covers the case where the cell was unchanged but a redraw is wanted).
   *  Out-of-bounds neighbors are silently skipped. */
  redrawAround(r, c) {
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        const nr = r + dr;
        const nc = c + dc;
        if (nr < 0 || nr >= this.grid.rows || nc < 0 || nc >= this.grid.cols) continue;
        this._drawCellAsync(nr, nc);
      }
    }
  }
}

class BackgroundAligner {
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true });
    this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.map);
  }

  /** Compute Leaflet zoom level that fits `spanKm` vertically. */
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

class Toolbar {
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

  _buildPens() {
    const row = document.getElementById('pens');
    PENS.forEach(p => {
      const btn = document.createElement('button');
      btn.textContent = p;
      btn.onclick = () => this.handlers.setPen(p);
      if (p === 'G') btn.classList.add('active');
      row.appendChild(btn);
    });
  }

  setActivePen(p) {
    document.querySelectorAll('#pens button').forEach(b => {
      b.classList.toggle('active', b.textContent === p);
    });
  }

  loadCityPresets(presets) {
    const sel = document.getElementById('city');
    sel.innerHTML = '<option value="">(blank)</option>' +
      presets.map(p => `<option value="${p}">${p}</option>`).join('');
    sel.onchange = () => {
      if (sel.value) this.handlers.applyCity(sel.value);
    };
  }

  setMeta(meta) {
    document.getElementById('lat').value = meta.center_lat.toFixed(4);
    document.getElementById('lng').value = meta.center_lng.toFixed(4);
    document.getElementById('span').value = meta.span_km;
    document.getElementById('rows').value = meta.rows;
    document.getElementById('cols').value = meta.cols;
  }

  getMeta() {
    return {
      name: 'untitled',
      center_lat: parseFloat(document.getElementById('lat').value),
      center_lng: parseFloat(document.getElementById('lng').value),
      span_km: parseFloat(document.getElementById('span').value),
      rows: parseInt(document.getElementById('rows').value, 10),
      cols: parseInt(document.getElementById('cols').value, 10),
    };
  }

  setStatus(msg) {
    document.getElementById('status').textContent = msg;
  }

  /** Update the baselayer toggle button label. */
  setBaseLayerLabel(text) {
    document.getElementById('toggle-base').textContent = `底图: ${text}`;
  }
}

class MapEditor {
  constructor(meta, cityPresets) {
    this.grid = new GridModel(meta.rows, meta.cols);
    this.resolver = new TileResolver();
    this.history = new History(this.grid);
    this.tileLoader = new TileLoader();
    this.canvas = document.getElementById('grid');
    this.renderer = new Renderer(this.canvas, this.tileLoader, this.grid, this.resolver);
    this.aligner = new BackgroundAligner('map');
    this.aligner.setView(meta);
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

  _setupMouse() {
    let isPainting = false;
    const onMove = (ev) => {
      const rect = this.canvas.getBoundingClientRect();
      const { r, c } = this.renderer.pixelToCell(ev.clientX - rect.left, ev.clientY - rect.top);
      if (r < 0 || c < 0 || r >= this.grid.rows || c >= this.grid.cols) return;
      if (this.grid.get(r, c) !== this.pen) {
        this.grid.set(r, c, this.pen);
        // Re-resolve the 3x3 neighborhood: the painted cell changed, and any
        // neighbor's resolved tile (beach/road/...) depends on its own
        // neighbors, so a change in one cell can flip a neighbor's variant.
        this.renderer.redrawAround(r, c);
      }
    };
    this.canvas.onmousedown = (ev) => {
      isPainting = true;
      this.history.push(this.grid);
      onMove(ev);
    };
    this.canvas.onmousemove = (ev) => { if (isPainting) onMove(ev); };
    document.addEventListener('mouseup', () => { isPainting = false; });
    this.canvas.onmouseleave = () => { isPainting = false; };
  }

  _setupResize() {
    this.renderer.resizeToContainer();
    window.addEventListener('resize', () => this.renderer.resizeToContainer());
  }

  _fitGridToView() {
    const rect = this.canvas.getBoundingClientRect();
    const cellSize = Math.max(8, Math.min(48, Math.floor(Math.min(rect.width / this.grid.cols, rect.height / this.grid.rows))));
    this.renderer.setCellSize(cellSize);
  }

  _undo() {
    if (this.history.undo(this.grid)) {
      this.renderer.drawAll();
      this._saveDraft();
    }
  }
  _redo() {
    if (this.history.redo(this.grid)) {
      this.renderer.drawAll();
      this._saveDraft();
    }
  }
  _clear() {
    if (!confirm('清空所有格子？')) return;
    this.history.push(this.grid);
    this.grid.clear();
    this.renderer.drawAll();
    this._saveDraft();
  }
  _export() {
    const meta = this.toolbar.getMeta();
    const json = DeclExporter.toJSON(this.grid, meta);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${meta.name || 'untitled'}_decl.json`;
    a.click();
    URL.revokeObjectURL(url);
    fetch('/save', { method: 'POST', body: json, headers: { 'Content-Type': 'application/json' } })
      .then(r => r.json().then(j => ({ status: r.status, body: j })))
      .then(({ status, body }) => this.toolbar.setStatus(status === 200 && body.ok ? `已保存: ${body.path}` : `错误: ${body.error || status}`))
      .catch(e => this.toolbar.setStatus(`下载成功,但保存到 input/ 失败: ${e.message}`));
  }
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

  _loadDraft() {
    const key = `mapeditor:${this.grid.rows}x${this.grid.cols}`;
    const raw = localStorage.getItem(key);
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      for (let r = 0; r < Math.min(this.grid.rows, data.length); r++) {
        for (let c = 0; c < Math.min(this.grid.cols, data[r].length); c++) {
          this.grid.set(r, c, data[r][c]);
        }
      }
    } catch {}
  }

  _saveDraft() {
    const key = `mapeditor:${this.grid.rows}x${this.grid.cols}`;
    try {
      localStorage.setItem(key, JSON.stringify(this.grid.toDeclMap()));
    } catch (e) {
      this.toolbar.setStatus(`localStorage 写入失败: ${e.message}`);
    }
  }
}

async function boot() {
  const metaUrl = new URL('meta.json', document.baseURI).href;
  const meta = await fetch(metaUrl).then(r => r.json());
  const cityPresets = ['shanghai', 'beijing', 'hangzhou', 'syracuse', 'tokyo'];
  new MapEditor(meta, cityPresets);
}

boot().catch(e => {
  document.getElementById('status').textContent = 'Boot error: ' + e.message;
  console.error(e);
});

export { TileLoader, Renderer, BackgroundAligner, Toolbar, MapEditor, PENS };
