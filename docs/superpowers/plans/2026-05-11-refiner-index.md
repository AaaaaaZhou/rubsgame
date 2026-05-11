# Refiner 模块实现计划索引

本文档索引所有 refiner 子模块的开发计划。

---

## 计划列表

| 序号 | 子模块 | 文件路径 | 描述 |
|------|--------|----------|------|
| 1 | types | `docs/superpowers/plans/2026-05-11-refiner-types.md` | 数据类型定义 |
| 2 | text_analyzer | `docs/superpowers/plans/2026-05-11-refiner-text-analyzer.md` | Stage 1: 文本分析 |
| 3 | world_extractor | `docs/superpowers/plans/2026-05-11-refiner-world-extractor.md` | Stage 2a: 世界观提取 |
| 4 | persona_extractor | `docs/superpowers/plans/2026-05-11-refiner-persona-extractor.md` | Stage 2b: NPC 档案提取 |
| 5 | plot_builder | `docs/superpowers/plans/2026-05-11-refiner-plot-builder.md` | Stage 2c: 剧本构建 |
| 6 | asset_writer | `docs/superpowers/plans/2026-05-11-refiner-asset-writer.md` | Stage 3: 文件写出 |
| 7 | core | `docs/superpowers/plans/2026-05-11-refiner-core.md` | RefinerCore 主入口 |

---

## 依赖关系

```
types (Task 1)          ← 无依赖
    ↓
text_analyzer (Task 2)   ← types
    ↓
world_extractor (Task 3) ← types
persona_extractor (Task 4) ← types
plot_builder (Task 5)    ← types
    ↓
asset_writer (Task 6)    ← world_extractor, persona_extractor, plot_builder
    ↓
core (Task 7)            ← 所有 Stage
```

---

## 推荐实现顺序

1. **types** — 定义所有数据结构，是其他所有模块的基础
2. **text_analyzer** — Stage 1，提取原始文本的结构化信息
3. **world_extractor** — Stage 2a，生成 world.yaml
4. **persona_extractor** — Stage 2b，生成 npc/*.yaml
5. **plot_builder** — Stage 2c，生成 plot/*.yaml
6. **asset_writer** — Stage 3，将结果写入磁盘
7. **core** — 组装各模块，提供统一接口

---

## 文件结构

```
refiner/
├── types.py                    # Task 1
├── core.py                     # Task 7
├── extractors/
│   ├── __init__.py
│   ├── text_analyzer.py        # Task 2
│   ├── world_extractor.py      # Task 3
│   ├── persona_extractor.py   # Task 4
│   └── plot_builder.py         # Task 5
└── writers/
    ├── __init__.py
    └── asset_writer.py         # Task 6

unittest/refiner/
├── test_types.py
├── test_text_analyzer.py
├── test_world_extractor.py
├── test_persona_extractor.py
├── test_plot_builder.py
├── test_asset_writer.py
├── test_core.py
└── test_integration.py
```

---

## 设计文档

- 主设计文档: `refiner/docs/2026-05-11-refiner-design.md`
- 本索引: `docs/superpowers/plans/2026-05-11-refiner-index.md`