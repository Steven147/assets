import { test } from 'node:test';
import assert from 'node:assert/strict';

const lib = await import('../../pipeline/editor/editor_lib.js');
const { TileResolver } = lib;

test('GridModel initializes all cells to S', () => {
  const g = new lib.GridModel(3, 4);
  assert.equal(g.rows, 3);
  assert.equal(g.cols, 4);
  assert.equal(g.get(0, 0), 'S');
  assert.equal(g.get(2, 3), 'S');
});

test('GridModel set/get roundtrip', () => {
  const g = new lib.GridModel(3, 3);
  g.set(1, 1, 'G');
  assert.equal(g.get(1, 1), 'G');
});

test('GridModel out of bounds returns S', () => {
  const g = new lib.GridModel(3, 3);
  assert.equal(g.get(-1, 0), 'S');
  assert.equal(g.get(0, 99), 'S');
});

test('GridModel fillRect sets rectangle', () => {
  const g = new lib.GridModel(5, 5);
  g.fillRect(1, 1, 3, 2, 'G');
  for (let r = 1; r < 4; r++) {
    for (let c = 1; c < 3; c++) {
      assert.equal(g.get(r, c), 'G');
    }
  }
  assert.equal(g.get(0, 0), 'S');
});

test('GridModel clear resets to S', () => {
  const g = new lib.GridModel(3, 3);
  g.set(1, 1, 'G');
  g.clear();
  assert.equal(g.get(1, 1), 'S');
});

test('GridModel clone is independent', () => {
  const g = new lib.GridModel(3, 3);
  g.set(1, 1, 'G');
  const c = g.clone();
  c.set(1, 1, 'O');
  assert.equal(g.get(1, 1), 'G');
  assert.equal(c.get(1, 1), 'O');
});

test('GridModel toDeclMap returns array of strings with correct length', () => {
  const g = new lib.GridModel(3, 5);
  g.set(1, 2, 'G');
  const out = g.toDeclMap();
  assert.equal(out.length, 3);
  for (const row of out) {
    assert.equal(row.length, 5);
    assert.equal(typeof row, 'string');
  }
  assert.equal(out[1][2], 'G');
});

test('GridModel resize keeps top-left, fills with S', () => {
  const g = new lib.GridModel(3, 3);
  g.set(0, 0, 'G');
  g.set(2, 2, 'O');
  g.resize(5, 5);
  assert.equal(g.get(0, 0), 'G');
  assert.equal(g.get(2, 2), 'O');
  assert.equal(g.get(4, 4), 'S');
});

test('GridModel resize smaller drops cells', () => {
  const g = new lib.GridModel(3, 3);
  g.set(2, 2, 'O');
  g.resize(2, 2);
  assert.equal(g.get(2, 2), 'S');
});

test('TileResolver S returns W-full-sea', () => {
  const g = new lib.GridModel(2, 2);
  const r = new TileResolver();
  assert.equal(r.resolve(g, 0, 0), 'W-full-sea');
});

test('TileResolver L returns location', () => {
  const g = new lib.GridModel(2, 2);
  g.set(0, 0, 'L');
  const r = new TileResolver();
  assert.equal(r.resolve(g, 0, 0), 'location');
});

test('TileResolver G with all-G neighbors returns G-full-land', () => {
  const g = new lib.GridModel(3, 3);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) g.set(r, c, 'G');
  const r = new TileResolver();
  assert.equal(r.resolve(g, 1, 1), 'G-full-land');
});

test('TileResolver G with sea on top returns top-beach', () => {
  const g = new lib.GridModel(3, 3);
  g.set(0, 0, 'S'); g.set(0, 1, 'S'); g.set(0, 2, 'S');
  for (let r = 1; r < 3; r++) for (let c = 0; c < 3; c++) g.set(r, c, 'G');
  const r = new TileResolver();
  assert.equal(r.resolve(g, 1, 1), 'W-y-g-top-beach');
});

test('TileResolver R with road neighbors returns road desc', () => {
  const g = new lib.GridModel(3, 3);
  g.set(0, 0, 'S'); g.set(0, 1, 'S'); g.set(0, 2, 'S');
  g.set(1, 0, 'S'); g.set(1, 1, 'R'); g.set(1, 2, 'R');
  g.set(2, 0, 'S'); g.set(2, 1, 'S'); g.set(2, 2, 'S');
  const r = new TileResolver();
  // R at (1,1) with R at (1,2) only -> "G-o-right-road"
  assert.equal(r.resolve(g, 1, 1), 'G-o-right-road');
});

test('TileResolver r (lowercase) uses o-w- prefix', () => {
  const g = new lib.GridModel(3, 3);
  g.set(0, 1, 'r');
  g.set(1, 1, 'r');
  g.set(2, 1, 'r');
  const r = new TileResolver();
  // r at (1,1) with r above and below -> "o-w-top-bottom-road"
  assert.equal(r.resolve(g, 1, 1), 'o-w-top-bottom-road');
});
