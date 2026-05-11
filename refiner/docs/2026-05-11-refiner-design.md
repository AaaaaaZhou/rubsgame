# Refiner 模块设计文档

## 1. 概述

### 1.1 目标

将用户提供的 `.txt` 原始文本（故事/小说/剧本）精炼为 rubsgame 可用的资源文件：

- **NPC 档案** → `assets/npc/{name}/persona.yaml` + `relationships.yaml` + `memories/*.yaml`
- **剧本章节** → `assets/plot/{chapter_id}/chapter.yaml`
- **世界观** → `assets/world/{name}.yaml`

### 1.2 四阶段分层提取架构

```
输入文本
    │
    ▼
┌─────────────────────────────────────┐
│  Stage 1: TextAnalyzer              │
│  提取：角色列表、地点列表、事件序列     │
└─────────────────────────────────────┘
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
┌───────────┐  ┌───────────────┐  ┌───────────────┐
│Stage 2a:  │  │ Stage 2b:     │  │ Stage 2c:     │
│WorldExtrac│  │ PersonaExtrac │  │ PlotBuilder   │
│ tor       │  │ tor           │  │               │
│ 世界观    │  │ NPC档案       │  │ 剧本章节      │
└───────────┘  └───────────────┘  └───────────────┘
    │                  │                  │
    └──────────────────┴──────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  AssetWriter    │
              │  写出到 assets/ │
              └─────────────────┘
```

**为什么分层？**
- 高内聚低耦合：每个 stage 输入输出明确，可独立测试
- 质量可控：阶段结果可人工审核后再进入下一阶段
- 可复用：WorldExtractor 产出的世界可以被多个 NPC 复用

---

## 2. 数据格式规范

### 2.1 NPC Persona (persona.yaml)

```yaml
name: "角色名"
gender: "男/女"
age: 17
identity: "学生/老师/..." 
basic_info:
  academic_performance: "..."
  residence: "..."
  family_background: "..."

personality:
  core_traits:
    - "性格特征1"
    - "性格特征2"
  preferences:
    likes:
      - "喜欢1"
    dislikes:
      - "不喜欢1"

behaviors:
  conflict_response:
    description: "冲突响应描述"
    好感度影响: -5
  social_interaction:
    description: "社交行为描述"
    friendliness_range: [1, 10]

mood_system:
  baseline: 65
  factors:
    positive:
      - "正面因素"
    negative:
      - "负面因素"

background:
  education: "教育背景"
  dreams:
    - "梦想1"
  limitations:
    - "局限1"

speech_style:
  tone: "语气"
  vocabulary: "用词"
  features:
    - "特征1"

topics_of_interest:
  - "话题1"
```

### 2.2 NPC Relationships (relationships.yaml)

```yaml
player:
  subject_id: "{npc_name}"
  object_id: "player"
  relation_type: "stranger/friend/rival/..."
  affinity: 0      # -100~100
  trust: 50        # 0~100
  key_events: []
```

### 2.3 Chapter (chapter.yaml)

```yaml
chapter:
  id: "{chapter_id}"
  name: "章节名"

nodes:
  - id: "n_start"
    node_type: "NARRATION_ONLY"
    narration_type: "SCENE_ENTER"
    content: "场景描述"
    next: "n_next"

npc_interactions:
  - trigger_type: "LOCATION_CHANGE"
    npc_name: "{npc}"
    location: "{location}"
    priority: 8
    content: "NPC说的话"
    cooldown_turns: 5
```

### 2.4 World (world.yaml)

```yaml
world_name: "{world_name}"

global_memories:
  - content: "全局记忆内容"
    priority: 9
    tags: ["tag1", "tag2"]

locations:
  - name: "地点名称"
    description: "地点描述"
    npcs: []
    properties:
      type: "natural_water/commercial_street/..."
      district: "old_town/new_town/..."
      activity: "walk,bike,chat"
      season: "all_year/summer_only/..."
```

---

## 3. 模块设计

### 3.1 Stage 1: TextAnalyzer

**职责**: 分析原始文本，提取结构化信息

**输入**: 原始 `.txt` 文本（用户提供的故事/小说）

**输出**: `AnalysisResult`（ dataclass，包含角色表、地点表、事件序列）

```python
@dataclass
class AnalysisResult:
    world_name: str                              # 世界名称
    characters: List[CharacterInfo]              # 角色列表
    locations: List[LocationInfo]                # 地点列表
    events: List[EventInfo]                      # 事件序列（按时间顺序）
    relationships: List[RelationshipInfo]        # 角色关系
```

**CharacterInfo**:
```python
@dataclass
class CharacterInfo:
    name: str
    gender: str = ""
    age: str = ""
    identity: str = ""
    personality_traits: List[str] = []
    speech_features: List[str] = []
    background_summary: str = ""
    appears_in_scenes: List[str] = []  # 出现的场景ID列表
```

**LocationInfo**:
```python
@dataclass
class LocationInfo:
    name: str
    description: str = ""
    properties: Dict[str, str] = {}
```

**EventInfo**:
```python
@dataclass
class EventInfo:
    scene_id: str
    description: str
    participants: List[str]  # 角色名列表
    location: str = ""
    event_type: str = ""  # dialogue/narration/action
```

**RelationshipInfo**:
```python
@dataclass
class RelationshipInfo:
    subject: str   # 角色A
    object: str     # 角色B
    relation_type: str  # stranger/friend/rival/...
    affinity: int = 0
    trust: int = 50
    description: str = ""
```

### 3.2 Stage 2a: WorldExtractor

**职责**: 将 `AnalysisResult` 中的地点和全局记忆转换为 world.yaml

**输入**: `AnalysisResult`

**输出**: `WorldKnowledge` 对象（与 `WorldLoader` 输出同规格）

### 3.3 Stage 2b: PersonaExtractor

**职责**: 将 `AnalysisResult` 中的角色信息转换为 NPCProfile

**输入**: `AnalysisResult`

**输出**: `List[NPCProfile]`

**注意**: 不生成 `relationships.yaml`，关系信息存入 NPCProfile 的 relationships 字段

### 3.4 Stage 2c: PlotBuilder

**职责**: 将事件序列转换为章节节点

**输入**: `AnalysisResult` + `List[NPCProfile]`

**输出**: `List[Chapter]`

**节点类型映射**:
- 对话事件 → `NodeType.DIALOGUE`
- 旁白描述 → `NodeType.NARRATION_ONLY`
- 分支选择 → `NodeType.BRANCH`
- NPC 主动交互 → `NodeType.NPC_INTERACT`

### 3.5 Stage 3: AssetWriter

**职责**: 将所有输出写入 `assets/` 目录

**输入**:
- `WorldKnowledge` 对象
- `List[NPCProfile]` 
- `List[Chapter]`
- `output_dir: str`（默认为 `assets/`）

**输出**: 写入磁盘的 YAML 文件

---

## 4. Prompt 设计策略

### 4.1 TextAnalyzer Prompt

分步骤调用 LLM：

**Step 1 - 提取世界名称和全局记忆**:
```
请分析以下文本，提取：
1. 世界/故事发生的地点名称
2. 描述该世界的整体氛围和特点（1-3句）
```

**Step 2 - 提取角色**:
```
请从文本中提取所有角色，包含：
- 姓名、性别、大致年龄
- 性格特征（2-4个关键词）
- 语言/行为特点
- 社会身份（学生/教师/...）
```

**Step 3 - 提取地点**:
```
请从文本中提取所有提到的地点，包含：
- 地点名称
- 简短描述（1-2句）
```

**Step 4 - 提取事件和关系**:
```
请按时间顺序列出主要事件（场景），每个事件包含：
- 场景ID
- 简述发生了什么
- 涉及哪些角色
- 在什么地点
- 事件类型（对话/动作/旁白）
```

### 4.2 世界观补全 Prompt

当 `AnalysisResult` 的地点描述不足时：
```
请根据已有的地点名称，补充：
- 地点类型（自然/商业/教育/...）
- 适合的活动（行走/骑行/聊天/...）
- 适宜季节（全年度/夏季/...）
```

---

## 5. 文件结构

```
refiner/
├── core.py                      # RefinerCore 主入口
├── types.py                     # 所有 dataclass 定义
├── extractors/
│   ├── __init__.py
│   ├── text_analyzer.py          # Stage 1
│   ├── world_extractor.py        # Stage 2a
│   ├── persona_extractor.py      # Stage 2b
│   └── plot_builder.py           # Stage 2c
├── writers/
│   ├── __init__.py
│   └── asset_writer.py           # Stage 3
├── docs/
│   └── 2026-05-11-refiner-design.md
└── unittest/
    └── test_refiner.py
```

---

## 6. 接口定义

```python
class RefinerCore:
    """主入口类"""

    def __init__(self, client_manager: ClientManager, output_dir: str = "assets"):
        self._client_mgr = client_manager
        self._output_dir = output_dir

    def refine(self, input_text: str, world_name: str = "") -> RefinerOutput:
        """执行完整精炼流程

        Args:
            input_text: 用户提供的原始文本
            world_name: 可选，指定世界名称

        Returns:
            RefinerOutput 对象
        """
        ...

@dataclass
class RefinerOutput:
    world: Optional[WorldKnowledge]
    npcs: List[NPCProfile]
    chapters: List[Chapter]
    analysis: AnalysisResult
    warnings: List[str]  # 任何非致命的问题
```

---

## 7. 验证方式

1. **加载验证**: 生成的文件通过现有 `NPCLoader`、`PlotLoader`、`WorldLoader` 加载无报错
2. **完整性检查**: 每个 NPC 有 `persona.yaml`；每个章节有 `chapter.yaml`
3. **单元测试**: 每个 extractor 有独立 UT
4. **集成测试**: 端到端测试（输入文本 → 写出文件 → 重新加载）

---

## 8. 错误处理

- **格式解析失败**: 将 raw LLM 输出存入 `refiner/output_raw/` 供调试，抛出 `RefinerParseError`
- **文件写出失败**: 捕获 IO 异常，汇总到 `RefinerOutput.warnings`
- **部分成功**: 如果某个角色解析失败，保留其他角色继续处理

---

## 9. 实现顺序

1. `types.py` — 定义所有数据结构
2. `text_analyzer.py` — Stage 1（最关键，决定上游质量）
3. `world_extractor.py` — Stage 2a
4. `persona_extractor.py` — Stage 2b
5. `plot_builder.py` — Stage 2c
6. `asset_writer.py` — Stage 3
7. `core.py` — 组装各模块
8. UT + 集成测试

---

## 10. 关键设计决策

### Q: NPC 关系文件是否单独写出？
**A**: 否。`relationships.yaml` 信息存入 `NPCProfile.relationships` 字段，由 `AssetWriter` 统一写出。这样保持与 `NPCLoader` 的接口一致。

### Q: 世界观是否可以补充而非全量生成？
**A**: 是。`WorldExtractor` 支持与现有世界合并（`merge_existing=True`），避免覆盖用户已有的世界设定。

### Q: 一个文本是否可能生成多个章节？
**A**: 是。根据事件序列自动切分，每个事件序列构成一个 chapter。