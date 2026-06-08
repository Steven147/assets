# 地图生成管线简化设计

**日期**：2026-06-08
**作者**：brainstorming with claude
**状态**：待 review

## 1. 背景与目标

`game/` 目录当前有 3 个 Python 脚本承担"地图生成"职责：

| 脚本 | 行数 | 职责 |
|------|------|------|
| `map_builder.py` | 1199 | 单场景 + 多场景 + 两份内嵌 HTML 模板 + tile 解析 + 几何校验 |
| `osm_to_map.py` | 566 | Overpass API + 栅格化 + folium/matplotlib 渲染 |
| `osm_build.py` | 88 | 复用 `map_builder.py` 内部函数 + 字符串 hack 修 HTML 路径 |

痛点：

1. 三个脚本分散，新人看 `justfile` 才能拼出完整流程
2. `map_builder.py` 1199 行混了 4 件事（parse / validate / resolve / render HTML）
3. `osm_build.py` 里的 `text.replace('ABS_PREFIX', 'REL_PREFIX')` 路径修复 hack 散在外面
4. `map_builder.process_single()` 每次跑都会用硬编码的测试图覆盖 `input/map_decl.json`
5. 单场景 HTML 和多场景 HTML 是两份独立文件，重复样式/逻辑

**目标**：把现有管线重构成 4-stage 清晰管线（**完全替换**旧脚本），新增 input 来源接入只需加一个 source 模块。

## 2. 设计约束（来自 brainstorm 答案）

1. **完全替换** —— `map_builder.py` / `osm_to_map.py` / `osm_build.py` 一并删除
2. **API 仅 OSM** —— 不需要可插拔 source 接口
3. **Stage 划分固定为 source → grid → resolved → html**
4. **保留两份独立 HTML**（单场景 + 多场景），不强行合并
5. **4 个独立脚本**作为 CLI 入口
6. **产物统一到 `output/<name>/`**（与 source 类型无关）

## 3. 架构

### 3.1 数据流

```
input/<name>_decl.json ─┐
                        ├─ stage1 source ─→ output/<name>/<name>_decl.json
OSM API ────────────────┘                                          │
                                                                   ↓
                                                          stage2 grid
                                                                   │
                                                                   ↓
                                                output/<name>/<name>_grid.json
                                                                   │
                                                                   ↓
                                                         stage3 resolved
                                                                   │
                                                                   ↓
                                              output/<name>/<name>_resolved.json
                                                                   │
                                                                   ↓
                                                             stage4 html
                                                                   │
                                                                   ↓
                                       output/<name>/<name>_viewer.html (单场景)
                                       output/<name>/world_viewer.html (多场景)
```

每一步都是幂等的纯函数：`输入路径 + 资源 → 输出路径`。可独立运行调试。

### 3.2 关键约定

- 所有 stage 产物一律落 `output/<name>/`，与 source 类型无关
- `<name>` 既是产物目录名，也是单场景 viewer 的前缀（如 `my_map_viewer.html`）；多场景 viewer 固定名为 `world_viewer.html`
- HTML 不内嵌绝对路径；改用 `<base href="/">` + `fetch('map_resolved.json')`，仅当通过 `just serve` 起服务时才能加载图片
- 中间文件保留为可读 JSON，便于人工 diff 与 CI 校验

## 4. 组件

### 4.1 `pipeline/` 子包

| 模块 | 职责 | 行数估计 |
|------|------|---------|
| `pipeline/registry.py` | `parse_tile_registry()` 函数 + `TileRegistry` 类（从 `assets_map_check.json` 读，小写 key 索引） | ~50 |
| `pipeline/decl.py` | `read_decl()` / `write_decl()`，统一 decl schema | ~80 |
| `pipeline/grid.py` | `parse_map()` 字符网格、`get_char()` 安全取字符、`grid_to_json()` / `json_to_grid()` | ~60 |
| `pipeline/validate.py` | `validate_map()` R1-R4 几何规则 | ~80 |
| `pipeline/resolve.py` | `_beach()` / `_road()` / `resolve_tile()` / `generate_desc_json()` | ~120 |
| `pipeline/world.py` | `iter_scenes()` / `resolve_world_scenes()` 共享 world scene 操作 | ~60 |
| `pipeline/render.py` | `generate_map_html()` / `generate_world_html()`（读模板 → 填数据） | ~80 |
| `pipeline/sources/local.py` | `LocalSource.run(name)` → 拷贝 `input/<name>_decl.json` 到 `output/<name>/`（自动判 single / world） | ~40 |
| `pipeline/sources/osm.py` | `OsmSource.run(city, size_km, name)` → Overpass + 栅格化 + decl 构建 | ~500（基本搬 osm_to_map.py 的核心） |
| `pipeline/html/` | jinja2 模板：map_viewer.html.j2 / world_viewer.html.j2 | 0（纯模板） |
| `pipeline/sources/__init__.py` | `get_source(name: str)` 工厂 + `PRESET_CITY_KEYS` 常量 | ~20 |

### 4.2 4 个 stage 脚本

每个 stage 是 30-60 行的薄壳，统一模式：`python3 stage<N>_<role>.py <name>`。

#### `stage1_source.py`

```python
import argparse
from pipeline.sources import get_source

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="source", required=True)

    local = sub.add_parser("local")
    local.add_argument("name")

    osm = sub.add_parser("osm")
    osm.add_argument("--city", required=True, choices=PRESET_CITY_KEYS)
    osm.add_argument("--size-km", type=float, default=10.0)
    osm.add_argument("--name", default=None,
                     help="产物目录名 (默认 <city>_<size_km>km)")

    args = ap.parse_args()
    src = get_source(args.source)
    out = src.run(args)
    print(f"✅ stage1 → {out}")

if __name__ == "__main__":
    main()
```

#### `stage2_grid.py`

```python
import argparse
from pathlib import Path
from pipeline.decl import read_decl
from pipeline.grid import parse_map
from pipeline.validate import validate_map
from pipeline.world import iter_scenes
import json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    args = ap.parse_args()

    out_dir = Path("output") / args.name
    decl = read_decl(out_dir / f"{args.name}_decl.json")

    if decl["kind"] == "single":
        grid = parse_map(decl["map"])
        errors = validate_map(grid)
        result = {
            "name": decl["name"],
            "kind": "single",
            "rows": len(grid),
            "cols": max(len(r) for r in grid) if grid else 0,
            "grid": [[{"char": ch} for ch in row] for row in grid],
            "validation": {"ok": not errors, "rule_violations": errors},
        }
    else:  # world
        scenes = []
        all_ok = True
        for sc in decl["scenes"]:
            grid = parse_map(sc["map"])
            errors = validate_map(grid)
            scenes.append({
                "id": sc["id"],
                "grid": [[{"char": ch} for ch in row] for row in grid],
                "validation": {"ok": not errors, "rule_violations": errors},
            })
            all_ok = all_ok and not errors
        result = {
            "name": decl["name"],
            "kind": "world",
            "scenes": scenes,
            "validation": {"ok": all_ok},
        }

    out_path = out_dir / f"{args.name}_grid.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["validation"]["ok"]:
        n = sum(len(s.get("validation", {}).get("rule_violations", []))
                for s in result.get("scenes", [result]))
        print(f"⚠️  {n} 条 R1-R4 违规 (已写入 grid.json, 不阻塞)")
    print(f"✅ stage2 → {out_path}")

if __name__ == "__main__":
    main()
```

#### `stage3_resolved.py`

```python
import argparse, json
from pathlib import Path
from pipeline.registry import parse_tile_registry
from pipeline.resolve import generate_desc_json
from pipeline.world import resolve_world_scenes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    args = ap.parse_args()

    base = Path(__file__).parent
    registry = parse_tile_registry(str(base / "assets_map_check.json"))
    out_dir = Path("output") / args.name
    grid_doc = json.loads((out_dir / f"{args.name}_grid.json").read_text())

    if grid_doc["kind"] == "single":
        grid = [[c["char"] for c in row] for row in grid_doc["grid"]]
        resolved = {
            "name": grid_doc["name"],
            "kind": "single",
            "rows": grid_doc["rows"],
            "cols": grid_doc["cols"],
            "grid": generate_desc_json(grid, registry),
        }
    else:
        resolved = resolve_world_scenes(grid_doc, registry)

    out_path = out_dir / f"{args.name}_resolved.json"
    out_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2))
    print(f"✅ stage3 → {out_path}")

if __name__ == "__main__":
    main()
```

#### `stage4_html.py`

```python
import argparse
from pathlib import Path
from pipeline.render import generate_map_html, generate_world_html
import json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--serve", action="store_true",
                    help="渲染后启动 http server (后台)")
    args = ap.parse_args()

    out_dir = Path("output") / args.name
    resolved = json.loads((out_dir / f"{args.name}_resolved.json").read_text())

    if resolved["kind"] == "single":
        out_path = out_dir / f"{args.name}_viewer.html"
        generate_map_html(resolved, str(out_path))
    else:
        out_path = out_dir / "world_viewer.html"
        generate_world_html(resolved, str(out_path))

    print(f"✅ stage4 → {out_path}")
    if args.serve:
        import subprocess, time, urllib.request
        try:
            urllib.request.urlopen("http://127.0.0.1:8765/", timeout=0.3)
        except Exception:
            subprocess.Popen(
                ["python3", "-m", "http.server", "8765", "--bind", "127.0.0.1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:8765/{out_path}")

if __name__ == "__main__":
    main()
```

## 5. 数据 schema

### 5.1 Decl JSON（stage 1 输出 / stage 2 输入）

```json
{
  "name": "shanghai_map",
  "kind": "single",                  // "single" | "world"
  "source": "osm",                   // "local" | "osm"
  "rows": 1000,
  "cols": 1000,
  "map": ["SSSSSSSS...", ...],       // 字符网格
  "meta": {
    "city": "Shanghai",              // OSM 字段；local 可空
    "bbox": {"min_lat": ..., ...},   // 同上
    "scale_m_per_pixel": 10.0,
    "size_km": {"width": 10.0, ...}
  },
  "pois": [...]                      // OSM 字段；local 可空
}
```

`world` kind 时顶层多一个 `scenes: [{id, title, back, map, regions?}, ...]`，`kind=single` 字段不存在。

### 5.2 Grid JSON（stage 2 输出 / stage 3 输入）

```json
{
  "name": "shanghai_map",
  "kind": "single",
  "rows": 1000,
  "cols": 1000,
  "grid": [
    [{"char": "S"}, {"char": "S"}, ...],
    ...
  ],
  "validation": {
    "ok": true,
    "rule_violations": []            // R1-R4 违规
  }
}
```

> 注：stage 2 不在此步计算 desc —— desc 由 stage 3 算。这样 stage 2 校验失败可快速反馈，stage 3 单测不依赖 registry mock。

`world` kind 时多一层 `scenes: [{id, grid, validation}, ...]`。

### 5.3 Resolved JSON（stage 3 输出 / stage 4 输入）

```json
{
  "name": "shanghai_map",
  "kind": "single",
  "rows": 1000,
  "cols": 1000,
  "grid": [
    [{"char": "S", "desc": "W-full-sea", "file": "/abs/path/to/tile.png"}, ...],
    ...
  ]
}
```

> 与现状的 `output/map_resolved.json` 字段结构 1:1 兼容（旧 viewer 可直接消费新 resolved）。

## 6. 错误处理

| 阶段 | 失败情形 | 行为 | 退出码 |
|------|---------|------|-------|
| stage 1 | OSM 3 个端点全失败 | 打印端点日志 + 异常链 | 1 |
| stage 1 | local 输入文件不存在 | 抛出 FileNotFoundError | 1 |
| stage 2 | R1-R4 违规 | 写 grid.json 含 `validation.ok=false` + 违规列表，**不**退出 | 0 |
| stage 2 | decl 解析失败（缺 name/map 等） | 抛出 KeyError | 1 |
| stage 3 | TileRegistry 缺 desc | 在 grid[i][j] 写 `file=""`，HTML 标红 | 0 |
| stage 3 | assets_map_check.json 缺失 | 抛出 FileNotFoundError | 1 |
| stage 4 | 模板渲染失败 / 写盘失败 | 抛出原始异常 | 1 |

> 与现状对比：原 `osm_build.py` "警告不阻塞"，原 `map_builder.py` 单场景"硬失败"。**新策略统一为"不阻塞 + 产物中标红"** —— OSM 数据违反 R1-R4 是常态，不应阻止出图。

## 7. 测试

| 测试文件 | 覆盖 | 用例数 |
|---------|------|-------|
| `tests/test_validate.py` | R1-R4 各分支 | 7-8 |
| `tests/test_resolve.py` | 1×1 孤岛 / L 角 / 直角路 / T 字路 / 十字路 / 孤立路 | 6 |
| `tests/test_decl.py` | local 入口读 `input/<name>_decl.json` → 输出字段一致 | 3 |
| `tests/fixtures/` | 4-5 个小网格（不超 6×6） | - |

> 不测 stage 4 HTML 渲染（jinja2 模板 smoke test 即可），靠 `just view` 手动验证。

**手动 smoke 命令**：

- `just smoke` —— 跑 local boundary test map 全 4 stage + 起服务 + curl 检查 viewer 200
- `just smoke-osm shanghai 5` —— OSM 端到端（先离线 cache fixture 加速 CI）

## 8. CLI 与 justfile

### 8.1 新 justfile

```just
default:
    @just --list

PORT := "8765"

# === Stage 1: source ===
s1-local name:
    python3 stage1_source.py local {{name}}

s1-osm city size_km:
    python3 stage1_source.py osm --city {{city}} --size-km {{size_km}} \
        --name {{city}}_{{size_km}}km

# === Stage 2-4 ===
s2 name:
    python3 stage2_grid.py {{name}}

s3 name:
    python3 stage3_resolved.py {{name}}

s4 name:
    python3 stage4_html.py {{name}}

# === 一键全跑 ===
build name: (s1-local name) (s2 name) (s3 name) (s4 name)
build-osm city size_km: (s1-osm city size_km) (s2 (city + '_' + size_km + 'km')) \
                                       (s3 (city + '_' + size_km + 'km')) \
                                       (s4 (city + '_' + size_km + 'km'))

# === 查看 ===
serve:
    @python3 -m http.server {{PORT}} --bind 127.0.0.1

# 智能打开: kind=world 找 world_viewer.html, 否则找 <name>_viewer.html
view name: (view-auto name)
view-auto name:
    @# 检测 kind: grid.json 含 scenes 字段则是 world
    @if [ -f output/{{name}}/{{name}}_grid.json ] && \
         python3 -c "import json,sys; d=json.load(open('output/{{name}}/{{name}}_grid.json')); sys.exit(0 if d.get('kind')=='world' else 1)"; then \
        HTML="output/{{name}}/world_viewer.html"; \
    else \
        HTML="output/{{name}}/{{name}}_viewer.html"; \
    fi
    @curl -sf -o /dev/null http://127.0.0.1:{{PORT}}/ 2>/dev/null || \
        (python3 -m http.server {{PORT}} --bind 127.0.0.1 >/dev/null 2>&1 &)
    @open "http://127.0.0.1:{{PORT}}/$HTML"

# === 清理 ===
clean:
    @trash output 2>/dev/null || true

# === 测试 ===
test:
    python3 -m pytest tests/ -v

smoke: (build smoke_test) (view-bg smoke_test)
```

### 8.2 常用工作流

```bash
# 本地字符地图
just s1-local my_map
just build my_map
just view my_map

# OSM 真实数据
just s1-osm shanghai 10
just build-osm shanghai 10
just view shanghai_10km

# 单 stage 重跑
just s3 my_map      # 只重跑 stage 3
```

## 9. 迁移清单

新 spec 落地时一次性完成：

- [ ] 删除 `map_builder.py` / `osm_to_map.py` / `osm_build.py`
- [ ] 删除 `map_builder.process_single()` 写死测试图的副作用
- [ ] 把 `input/world_decl.json` 改名为 `input/world_map.json`（可选，保持兼容也行）
- [ ] 新增 `input/smoke_test_decl.json`（6×6 极小 fixture，给 `just smoke` 用）
- [ ] `output/` 旧产物（`map_resolved.json` / `map_viewer.html`）一次性 trash —— schema 不变，无需迁移脚本
- [ ] `__pycache__/` 目录 trash 一次
- [ ] `.venv/` 重新创建并重装（如果需要）
- [ ] README 替换：旧 4 命令 → 新 stage 命令

## 10. 范围外（YAGNI）

- 不引入可插拔 source 接口（OSM 唯一）
- 不引入配置层（`pipeline.toml` / yaml）
- 不测 stage 4 HTML 渲染（jinja2 模板）
- 不做 stage 间依赖图（按编号顺序手工串起）
- 不引入 CI / Docker（保留人工 `just` 调用）

## 11. 验收标准

1. `just build smoke_test` 在 5 秒内出 `output/smoke_test/smoke_test_viewer.html`
2. `just view smoke_test` 在浏览器里能看到 24×30 测试图，无缺图（all tile desc 在 registry 里命中）
3. `just build-osm shanghai 5` 跑通，浏览器能看到上海中心区 1000×1000 网格
4. `just test` 全部通过
5. 旧脚本删除后 `justfile` 里再无 `map_builder.py` / `osm_to_map.py` / `osm_build.py` 字样
