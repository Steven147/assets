import { test } from 'node:test';
import assert from 'node:assert/strict';

const lib = await import('../../pipeline/editor/editor_lib.js');

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
