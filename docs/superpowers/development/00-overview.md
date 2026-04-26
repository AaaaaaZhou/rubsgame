# 视觉小说模式开发指南

## 概述

本文档指导如何将视觉小说模式的设计规范实现为代码。基于 `docs/superpowers/specs/` 下的设计文档编写。

## 目录

| 文档 | 内容 |
|------|------|
| `00-overview.md` | 本文档，开发总览 |
| `01-plot-manager.md` | StoryPlotManager 开发指南 |
| `02-narrator-generator.md` | NarratorGenerator 开发指南 |
| `03-option-generator.md` | OptionGenerator 开发指南 |
| `04-npc-interaction.md` | NPCInteractionManager 开发指南 |
| `05-game-loop.md` | GameLoopController 开发指南 |
| `06-session.md` | Session 扩展开发指南 |

## 开发环境准备

```bash
# 安装依赖（如果需要）
pip install pytest pytest-asyncio

# 确认目录结构
ls src/core/
# 应包含: engine.py, session.py, asset_manager.py, orchestrator.py 等
```

## 新模块目录结构

```
src/core/plot/
├── __init__.py           # 模块导出
├── types.py              # 共用数据类型（PlotState, PlotNode, Branch 等）
├── plot_loader.py        # 章节 YAML 加载器
├── plot_manager.py       # StoryPlotManager
├── narrator.py           # NarratorGenerator
├── option_generator.py  # OptionGenerator
├── npc_interaction.py    # NPCInteractionManager
└── game_loop.py         # GameLoopController

assets/plot/              # 章节配置目录
└── {chapter_id}/
    └── chapter.yaml
```

## 实现顺序

```
Step 1: types.py + plot_loader.py
        ↓
Step 2: plot_manager.py
        ↓
Step 3: narrator.py
        ↓
Step 4: option_generator.py
        ↓
Step 5: npc_interaction.py
        ↓
Step 6: game_loop.py（整合所有模块）
        ↓
Step 7: Session 扩展（PlotState 持久化）
        ↓
Step 8: PowerShellInterface 适配
        ↓
Step 9: 单元测试
```

## 现有系统集成点

| 现有模块 | 集成方式 |
|----------|----------|
| `EngineCore` | 扩展 `chat()` 返回结构，增加 `options` 和 `narrative` 字段 |
| `AssetManager` | 新增加载章节配置方法 |
| `SessionManager` | 持久化 `plot_state` |
| `PowerShellInterface` | 选项渲染、键盘输入处理 |

## 测试策略

每个模块开发完成后，编写对应的单元测试：

```
unittest/core/plot/
├── test_plot_manager.py
├── test_narrator.py
├── test_option_generator.py
└── test_npc_interaction.py
```

运行测试：
```bash
pytest unittest/core/plot/ -v
```
