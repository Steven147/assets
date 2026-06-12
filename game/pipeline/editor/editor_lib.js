// Pure logic, no DOM. Loadable in node and browser.

const VALID_CHARS = new Set(['S', 'G', 'O', 'R', 'r', 'L']);

export class GridModel {
  constructor(rows, cols) {
    this.rows = rows;
    this.cols = cols;
    this._grid = Array.from({ length: rows }, () => 'S'.repeat(cols).split(''));
  }

  inBounds(r, c) {
    return r >= 0 && r < this.rows && c >= 0 && c < this.cols;
  }

  get(r, c) {
    if (!this.inBounds(r, c)) return 'S';
    return this._grid[r][c];
  }

  set(r, c, ch) {
    if (!this.inBounds(r, c)) return;
    if (!VALID_CHARS.has(ch)) return;
    this._grid[r][c] = ch;
  }

  clear() {
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        this._grid[r][c] = 'S';
      }
    }
  }

  fillRect(r0, c0, r1, c1, ch) {
    for (let r = r0; r <= r1; r++) {
      for (let c = c0; c <= c1; c++) {
        this.set(r, c, ch);
      }
    }
  }

  clone() {
    const out = new GridModel(this.rows, this.cols);
    for (let r = 0; r < this.rows; r++) {
      out._grid[r] = this._grid[r].slice();
    }
    return out;
  }

  toDeclMap() {
    return this._grid.map(row => row.join(''));
  }

  resize(newRows, newCols) {
    const old = this._grid;
    const out = Array.from({ length: newRows }, () => 'S'.repeat(newCols).split(''));
    const rmax = Math.min(this.rows, newRows);
    const cmax = Math.min(this.cols, newCols);
    for (let r = 0; r < rmax; r++) {
      for (let c = 0; c < cmax; c++) {
        out[r][c] = old[r][c];
      }
    }
    this.rows = newRows;
    this.cols = newCols;
    this._grid = out;
  }
}

const LAND_CHARS = new Set(['G', 'O', 'R', 'r', 'L']);
const ROAD_CHARS = new Set(['R', 'r']);

function getChar(grid, r, c) {
  return grid.get(r, c);
}

function isSea(ch) {
  return ch === 'S';
}

function beach(grid, r, c, prefix, full) {
  const nTop = isSea(getChar(grid, r - 1, c));
  const nBot = isSea(getChar(grid, r + 1, c));
  const nLft = isSea(getChar(grid, r, c - 1));
  const nRgt = isSea(getChar(grid, r, c + 1));
  const dTL = isSea(getChar(grid, r - 1, c - 1));
  const dTR = isSea(getChar(grid, r - 1, c + 1));
  const dBL = isSea(getChar(grid, r + 1, c - 1));
  const dBR = isSea(getChar(grid, r + 1, c + 1));

  const seas = [];
  if (nTop) seas.push('top');
  if (nBot) seas.push('bottom');
  if (nLft) seas.push('left');
  if (nRgt) seas.push('right');
  const n = seas.length;

  if (n === 0) {
    if (dTL) return `${prefix}-left-top-negative-beach`;
    if (dTR) return `${prefix}-right-top-negative-beach`;
    if (dBL) return `${prefix}-left-bottom-negative-beach`;
    if (dBR) return `${prefix}-right-bottom-negative-beach`;
    return full;
  }
  if (n === 1) return `${prefix}-${seas[0]}-beach`;
  if (n === 2) {
    const s = new Set(seas);
    if (s.has('top') && s.has('bottom')) return `${prefix}-top-beach`;
    if (s.has('left') && s.has('right')) return `${prefix}-left-beach`;
    const h = s.has('left') ? 'left' : 'right';
    const v = s.has('top') ? 'top' : 'bottom';
    return `${prefix}-${h}-${v}-beach`;
  }
  if (n === 3) return `${prefix}-island`;
  return `${prefix}-island-2`;
}

function road(grid, r, c, base, roadPrefix) {
  const conn = new Set();
  const dirs = [['top', -1, 0], ['bottom', 1, 0], ['left', 0, -1], ['right', 0, 1]];
  for (const [name, dr, dc] of dirs) {
    if (ROAD_CHARS.has(getChar(grid, r + dr, c + dc))) conn.add(name);
  }
  const n = conn.size;
  if (n === 4) return `${base}-${roadPrefix}-full-road`;
  if (n === 3) {
    const all = new Set(['top', 'bottom', 'left', 'right']);
    for (const v of conn) all.delete(v);
    const miss = [...all][0];
    const m = {
      top: 'left-right-bottom',
      bottom: 'left-right-top',
      left: 'right-top-bottom',
      right: 'left-top-bottom',
    };
    return `${base}-${roadPrefix}-${m[miss]}-road`;
  }
  if (n === 2) {
    const sorted = [...conn].sort().join(',');
    const m = {
      'left,right': 'left-right',
      'bottom,top': 'top-bottom',
      'left,top': 'left-top',
      'right,top': 'right-top',
      'bottom,left': 'left-bottom',
      'bottom,right': 'right-bottom',
    };
    return `${base}-${roadPrefix}-${m[sorted]}-road`;
  }
  if (n === 1) return `${base}-${roadPrefix}-${[...conn][0]}-road`;
  return `${base}-${roadPrefix}-full-road`;
}

export class TileResolver {
  resolve(grid, r, c) {
    const ch = grid.get(r, c);
    if (ch === 'S') return 'W-full-sea';
    if (ch === 'L') return 'location';
    if (ch === 'R') return road(grid, r, c, 'G', 'o');
    if (ch === 'r') return road(grid, r, c, 'o', 'w');
    if (ch === 'G') return beach(grid, r, c, 'W-y-g', 'G-full-land');
    if (ch === 'O') return beach(grid, r, c, 'W-y-o', 'O-full-land');
    return 'W-full-sea';
  }
}
