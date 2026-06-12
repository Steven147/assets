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
}

class BackgroundAligner {
  constructor(mapElId) {
    this.map = L.map(mapElId, { zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
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
}

export { TileLoader, Renderer, BackgroundAligner, PENS };
