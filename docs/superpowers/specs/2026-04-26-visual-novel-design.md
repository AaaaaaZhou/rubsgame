# 视觉小说模式设计总览

## 1. 概述

为 rubsgame 增加视觉小说风格的选项驱动机制，同时保留自由对话能力。系统以选项驱动为主，关键节点提供空白选项供玩家自由输入；NPC 可主动发起交互；旁白根据剧情状态自动生成。

## 2. 目标场景

- 角色扮演 + 交互式小说混合体验
- 主线有分支但最终收敛，章节制追踪进度
- 玩家行动以对话为主，可前往/探索已有地点，不改变世界状态
- NPC 主动交互采用混合触发（剧情节点 + 环境感知 + 关系驱动）

## 3. 模块架构

```
┌─────────────────────────────────────────────────────────┐
│                    PowerShellInterface                    │
│                    （展示层 / 用户交互）                    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     Game Loop Controller                  │
│              （对话循环协调 / 模式切换判断）                 │
└─────────────────────────────────────────────────────────┘
        │                │                │                │
        ▼                ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│StoryPlot    │  │  Narrator   │  │   Option    │  │    NPC      │
│Manager      │  │ Generator   │  │ Generator   │  │Interaction  │
│             │  │             │  │             │  │ Manager     │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
        │                │                │                │
        └────────────────┴────────────────┴────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │     EngineCore.chat()    │
              │     （现有对话引擎）        │
              └─────────────────────────┘
```

## 4. 四个子模块

| 模块 | 职责 | 独立文档 |
|------|------|----------|
| StoryPlotManager | 主线进度/章节状态/触发器队列 | `2026-04-26-plot-manager.md` |
| NarratorGenerator | 生成场景/氛围/过渡/行动描述 | `2026-04-26-narrator-generator.md` |
| OptionGenerator | 对话中穿插选项、NPC提议后选项 | `2026-04-26-option-generator.md` |
| NPCInteractionManager | NPC主动交互的混合触发和队列 | `2026-04-26-npc-interaction.md` |

## 5. 核心交互流程

### 5.1 对话循环

```
用户输入
    │
    ▼
GameLoopController 判断输入类型
    │
    ├─→ [选项选择] → 执行对应分支
    │                        │
    │                        ▼
    │                  NarratorGenerator（行动结果旁白）
    │
    └─→ [自由输入] → EngineCore.chat()
                           │
                           ▼
                  NarratorGenerator（判断是否需要旁白）
                           │
                           ▼
                  StoryPlotManager（检查触发器）
                           │
                           ▼
                  NPCInteractionManager（判断NPC是否主动交互）
                           │
                           ▼
                  OptionGenerator（判断是否生成选项）
                           │
                           ▼
                    展示给用户
```

### 5.2 章节切换流程

```
章节结束节点
    │
    ▼
NarratorGenerator 生成过渡旁白
    │
    ▼
展示旁白 + "继续" 选项
    │
    ▼
StoryPlotManager 加载下一章节
    │
    ▼
NarratorGenerator 生成新章节开场旁白
    │
    ▼
进入新章节第一个节点
```

## 6. 模块依赖关系

```
StoryPlotManager
    ├─→ 输出: plot_state, available_choices
    └─→ 依赖: AssetManager（加载章节配置）

NarratorGenerator
    ├─→ 输入: plot_state, location, emotion, chapter_info
    ├─→ 输出: narrative_text
    └─→ 依赖: ClientManager（LLM生成旁白）

OptionGenerator
    ├─→ 输入: chat_history, plot_state, npc_suggestion
    ├─→ 输出: List[DialogOption]
    └─→ 依赖: ClientManager（LLM生成选项）

NPCInteractionManager
    ├─→ 输入: session_context, plot_state, relationship_state
    ├─→ 输出: NPCInteraction 队列
    └─→ 依赖: StoryPlotManager, AssetManager
```

## 7. 文件结构

```
docs/superpowers/specs/
├── 2026-04-26-visual-novel-design.md      # 本文档（总览）
├── 2026-04-26-plot-manager.md              # StoryPlotManager
├── 2026-04-26-narrator-generator.md        # NarratorGenerator
├── 2026-04-26-option-generator.md          # OptionGenerator
└── 2026-04-26-npc-interaction.md           # NPCInteractionManager
```

## 8. 实现顺序

1. StoryPlotManager — 章节和节点数据结构
2. NarratorGenerator — Prompt 模板和旁白生成
3. OptionGenerator — 选项生成逻辑
4. NPCInteractionManager — 触发检测和事件队列
5. GameLoopController — 协调各模块
6. PowerShellInterface 适配 — 渲染和输入处理
