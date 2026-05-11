# Refiner - RefinerCore 主入口实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 RefinerCore 主入口，组装各 Stage 并提供 `refine()` 接口

**Architecture:** 组合 TextAnalyzer、WorldExtractor、PersonaExtractor、PlotBuilder、AssetWriter

**Tech Stack:** ClientManager, Stage 1-3 模块

---

## File Structure

```
refiner/
├── core.py  (Create)
```

---

## Task 1: 实现 RefinerCore

**Files:**
- Create: `refiner/core.py`
- Test: `unittest/refiner/test_core.py`

- [ ] **Step 1: 编写测试文件**

```python
# unittest/refiner/test_core.py
import pytest
from unittest.mock import MagicMock, patch
from refiner.core import RefinerCore
from refiner.types import RefinerOutput, AnalysisResult, CharacterInfo, LocationInfo, EventInfo


def test_refiner_core_initialization():
    """测试 RefinerCore 初始化"""
    mock_client_mgr = MagicMock()
    core = RefinerCore(mock_client_mgr)

    assert core._client_mgr is mock_client_mgr
    assert core._output_dir == "assets"


def test_refiner_core_with_custom_output_dir():
    """测试自定义输出目录"""
    mock_client_mgr = MagicMock()
    core = RefinerCore(mock_client_mgr, output_dir="custom/path")

    assert core._output_dir == "custom/path"


def test_refine_returns_refiner_output():
    """测试 refine() 返回 RefinerOutput"""
    mock_client_mgr = MagicMock()

    # Mock 各 stage
    with patch('refiner.core.TextAnalyzer') as mock_ta, \
         patch('refiner.core.WorldExtractor') as mock_we, \
         patch('refiner.core.PersonaExtractor') as mock_pe, \
         patch('refiner.core.PlotBuilder') as mock_pb, \
         patch('refiner.core.AssetWriter') as mock_aw:

        # 配置 mock
        mock_analysis = MagicMock()
        mock_analysis.world_name = "测试世界"
        mock_analysis.characters = []
        mock_analysis.locations = []
        mock_analysis.events = []
        mock_analysis.relationships = []

        mock_ta_instance = MagicMock()
        mock_ta_instance.extract.return_value = mock_analysis
        mock_ta.return_value = mock_ta_instance

        mock_we_instance = MagicMock()
        mock_we.return_value = mock_we_instance

        mock_pe_instance = MagicMock()
        mock_pe.return_value = mock_pe_instance

        mock_pb_instance = MagicMock()
        mock_pb.return_value = mock_pb_instance

        mock_aw_instance = MagicMock()
        mock_aw.return_value = mock_aw_instance

        core = RefinerCore(mock_client_mgr)
        result = core.refine("测试文本")

        assert isinstance(result, RefinerOutput)
        assert result.analysis is mock_analysis
        assert isinstance(result.warnings, list)


def test_refine_with_empty_text():
    """测试空文本处理"""
    mock_client_mgr = MagicMock()

    with patch('refiner.core.TextAnalyzer') as mock_ta:
        mock_ta_instance = MagicMock()
        mock_ta_instance.extract.return_value = AnalysisResult(
            world_name="", characters=[], locations=[], events=[], relationships=[]
        )
        mock_ta.return_value = mock_ta_instance

        core = RefinerCore(mock_client_mgr)
        result = core.refine("")

        assert result.analysis.world_name == ""
        assert len(result.warnings) >= 0


def test_refine_stages_called_in_order():
    """测试各 Stage 按顺序调用"""
    mock_client_mgr = MagicMock()

    with patch('refiner.core.TextAnalyzer') as mock_ta, \
         patch('refiner.core.WorldExtractor') as mock_we, \
         patch('refiner.core.PersonaExtractor') as mock_pe, \
         patch('refiner.core.PlotBuilder') as mock_pb, \
         patch('refiner.core.AssetWriter') as mock_aw:

        mock_analysis = AnalysisResult(
            world_name="test",
            characters=[CharacterInfo(name="Alice")],
            locations=[LocationInfo(name="老街")],
            events=[EventInfo(scene_id="e1", description="test", participants=["Alice"], location="老街", event_type="dialogue")],
            relationships=[]
        )

        mock_ta_instance = MagicMock()
        mock_ta_instance.extract.return_value = mock_analysis
        mock_ta.return_value = mock_ta_instance

        mock_we_instance = MagicMock()
        mock_we.return_value = mock_we_instance

        mock_pe_instance = MagicMock()
        mock_pe.return_value = mock_pe_instance

        mock_pb_instance = MagicMock()
        mock_pb.return_value = mock_pb_instance

        mock_aw_instance = MagicMock()
        mock_aw.return_value = mock_aw_instance

        core = RefinerCore(mock_client_mgr)
        core.refine("测试文本")

        # 验证调用顺序
        mock_ta_instance.extract.assert_called_once()
        mock_we_instance.build.assert_called_once()
        mock_pe_instance.extract_all.assert_called_once()
        mock_pb_instance.build.assert_called_once()
        mock_aw_instance.write_all.assert_called_once()


def test_refiner_output_dataclass():
    """测试 RefinerOutput 数据类"""
    from refiner.types import RefinerOutput
    output = RefinerOutput(
        world=None,
        npcs=[],
        chapters=[],
        analysis=None,
        warnings=["warning1"]
    )
    assert len(output.warnings) == 1
    assert output.world is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest unittest/refiner/test_core.py -v`
Expected: FAIL (import error - module not found)

- [ ] **Step 3: 编写 RefinerCore 实现**

```python
"""
RefinerCore - 主入口模块
组装各 Stage，提供统一的 refine() 接口
"""
import logging
from typing import Optional

from ..clients.manager import ClientManager
from ..src.core.world_model import WorldKnowledge
from ..src.core.npc import NPCProfile
from ..src.core.plot.types import Chapter
from .types import AnalysisResult, RefinerOutput
from .extractors.text_analyzer import TextAnalyzer
from .extractors.world_extractor import WorldExtractor
from .extractors.persona_extractor import PersonaExtractor
from .extractors.plot_builder import PlotBuilder
from .writers.asset_writer import AssetWriter

_logger = logging.getLogger("refiner.core")


class RefinerCore:
    """Refiner 主入口"""

    def __init__(
        self,
        client_manager: ClientManager,
        output_dir: str = "assets",
        model_name: Optional[str] = None
    ):
        """初始化

        Args:
            client_manager: ClientManager 实例
            output_dir: 资源输出目录
            model_name: 可选，指定 LLM 模型
        """
        self._client_mgr = client_manager
        self._output_dir = output_dir
        self._model_name = model_name

        # 初始化各 Stage
        self._text_analyzer = TextAnalyzer(client_manager, model_name)
        self._world_extractor = WorldExtractor(client_manager, model_name)
        self._persona_extractor = PersonaExtractor(client_manager, model_name)
        self._plot_builder = PlotBuilder(client_manager, model_name)
        self._asset_writer = AssetWriter(output_dir)

        _logger.info(f"RefinerCore initialized with output_dir={output_dir}")

    def refine(
        self,
        input_text: str,
        world_name: Optional[str] = None,
        existing_world: Optional[WorldKnowledge] = None
    ) -> RefinerOutput:
        """执行完整精炼流程

        Args:
            input_text: 用户提供的原始文本
            world_name: 可选，指定世界名称（覆盖分析结果）
            existing_world: 可选，现有 WorldKnowledge（合并模式）

        Returns:
            RefinerOutput 对象
        """
        warnings = []

        # Stage 1: 文本分析
        _logger.info("Stage 1: TextAnalyzer")
        analysis = self._text_analyzer.extract(input_text)

        # 覆盖世界名称（如果指定）
        if world_name:
            analysis.world_name = world_name

        if not analysis.world_name:
            warnings.append("未能从文本中提取世界名称，使用默认值")

        # Stage 2a: 世界观提取
        _logger.info("Stage 2a: WorldExtractor")
        if existing_world:
            world = self._world_extractor.merge_existing(existing_world, analysis)
        else:
            world = self._world_extractor.build(analysis)

        # Stage 2b: NPC 档案提取
        _logger.info("Stage 2b: PersonaExtractor")
        npcs = self._persona_extractor.extract_all(analysis)

        if not npcs:
            warnings.append("未能从文本中提取任何角色")

        # Stage 2c: 剧本构建
        _logger.info("Stage 2c: PlotBuilder")
        chapters = self._plot_builder.build(analysis, npcs)

        if not chapters:
            warnings.append("未能从文本中构建任何章节")

        # Stage 3: 文件写出
        _logger.info("Stage 3: AssetWriter")
        try:
            self._asset_writer.write_all(world, npcs, chapters)
        except Exception as e:
            _logger.error(f"Failed to write assets: {e}")
            warnings.append(f"文件写出失败: {str(e)}")

        _logger.info(f"Refiner completed: {len(npcs)} NPCs, {len(chapters)} chapters")

        return RefinerOutput(
            world=world,
            npcs=npcs,
            chapters=chapters,
            analysis=analysis,
            warnings=warnings
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest unittest/refiner/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add refiner/core.py unittest/refiner/test_core.py
git commit -m "feat(refiner): add RefinerCore main entry"
```

---

## Task 2: 集成测试（可选）

**Files:**
- Create: `unittest/refiner/test_integration.py`

- [ ] **Step 1: 端到端测试**

```python
# unittest/refiner/test_integration.py
import pytest
import os
import tempfile
from unittest.mock import MagicMock
from refiner.core import RefinerCore


def test_end_to_end_refine():
    """端到端测试：文本 → 写出 → 重新加载验证"""
    mock_client_mgr = MagicMock()

    # Mock LLM 返回
    mock_client = MagicMock()
    mock_client.chat.return_value = MagicMock(content='{"world_name": "清溪镇", "characters": [{"name": "Alice", "gender": "女", "age": "17", "identity": "学生", "personality_traits": ["温和"], "speech_features": ["轻柔"], "background_summary": ""}], "locations": [{"name": "老街", "description": "历史悠久的街道"}], "events": [{"scene_id": "e1", "description": "Alice在老街散步", "participants": ["Alice"], "location": "老街", "event_type": "narration"}], "relationships": []}')
    mock_client_mgr.get_client.return_value = mock_client

    with tempfile.TemporaryDirectory() as tmpdir:
        core = RefinerCore(mock_client_mgr, output_dir=tmpdir)

        text = "Alice是一个17岁的女孩，她来到清溪镇的老街散步。"
        result = core.refine(text)

        assert result.analysis is not None
        assert result.analysis.world_name == "清溪镇"
        assert len(result.npcs) >= 1
        assert len(result.chapters) >= 1

        # 验证文件存在
        assert os.path.exists(os.path.join(tmpdir, "world", "清溪镇.yaml"))
        assert os.path.exists(os.path.join(tmpdir, "npc", "Alice", "persona.yaml"))
        assert os.path.exists(os.path.join(tmpdir, "plot", "chapter_1", "chapter.yaml"))
```

- [ ] **Step 2: Run integration test**

Run: `pytest unittest/refiner/test_integration.py -v`

- [ ] **Step 3: Commit**

```bash
git add unittest/refiner/test_integration.py
git commit -m "test(refiner): add integration test"
```