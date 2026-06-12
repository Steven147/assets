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
