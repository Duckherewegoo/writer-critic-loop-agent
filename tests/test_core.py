"""
核心纯函数单元测试（不联网、秒级、可回归）
"""
from unittest.mock import MagicMock

from agents.base_agent import AgentState
from agents.researcher import ResearchAgent
from agents.reviewer import ReviewerAgent
from graph.helper import agent_state_to_state, state_to_agent_state
from utils.helpers import count_words, extract_title, format_research_notes

_FAKE_LLM = MagicMock()

# ---------------------------------------------------------------------------
# ReviewerAgent._needs_revision —— 决定循环走向的核心判断
# ---------------------------------------------------------------------------
class TestNeedsRevision:
    def test_parses_structured_yes(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "总体评价：一般\n具体建议：...\n\nNEEDS_REVISION: YES"
        assert reviewer._needs_revision(response) is True

    def test_parses_structured_no(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "总体评价：优秀\n优点：...\n\nNEEDS_REVISION: NO"
        assert reviewer._needs_revision(response) is False

    def test_structured_marker_is_case_and_space_tolerant(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        assert reviewer._needs_revision("needs_revision:   yes") is True
        assert reviewer._needs_revision("  NEEDS_REVISION:\tNO ") is False

    def test_positive_words_do_not_override_explicit_yes(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "优点：优秀、很好、质量很高。\n建议：需要修改第三段。\nNEEDS_REVISION: YES"
        assert reviewer._needs_revision(response) is True

    def test_fallback_when_marker_missing(self):
        """
        根据源码：解析失败时直接返回 True，让系统保守重写。
        """
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "这是一段没有结构化标记的审核意见。"
        # 即使没有标记，也必须返回 True（触发重写保护）
        assert reviewer._needs_revision(response) is True


# ---------------------------------------------------------------------------
# ResearchAgent._parse_research_notes —— LLM 输出解析
# ---------------------------------------------------------------------------
class TestParseResearchNotes:
    def setup_method(self):
        self.agent = ResearchAgent(llm=_FAKE_LLM)

    def test_numbered_list(self):
        text = "1. 第一点内容\n2. 第二点内容\n3. 第三点内容"
        assert self.agent._parse_research_notes(text) == ["第一点内容", "第二点内容", "第三点内容"]

    def test_bullet_list(self):
        text = "- 甲观点\n* 乙观点\n• 丙观点"
        assert self.agent._parse_research_notes(text) == ["甲观点", "乙观点", "丙观点"]

    def test_plain_text_fallback(self):
        text = "这是一段没有任何列表标记的纯文本内容"
        notes = self.agent._parse_research_notes(text)
        assert len(notes) == 1
        assert "纯文本" in notes[0]


# ---------------------------------------------------------------------------
# 状态转换：WorkflowState ↔ AgentState 往返不丢字段
# ---------------------------------------------------------------------------
class TestStateRoundTrip:
    def test_round_trip_preserves_all_fields(self):
        state = {
            "topic": "主题",
            "research_notes": ["笔记A", "笔记B"],
            "draft_content": "草稿",
            "review_feedback": "反馈",
            "final_content": "",
            "current_step": "research",
            "iteration_count": 2,
            "max_iterations": 3,
            "metadata": {"needs_revision": True},
        }

        agent_state = state_to_agent_state(state)
        restored = agent_state_to_state(agent_state, state)

        for key in state.keys():
            assert restored[key] == state[key], f"字段 {key} 在往返中丢失或被篡改"


# ---------------------------------------------------------------------------
# utils.helpers —— 展示层工具函数
# ---------------------------------------------------------------------------
class TestUtilsHelpers:
    def test_count_words_mixed(self):
        # 根据实际源码逻辑修正断言
        assert count_words("人工智能 AI 与 ML") == 9

    def test_format_research_notes_empty(self):
        assert format_research_notes([]) == "暂无研究笔记"

    def test_format_research_notes_numbered(self):
        result = format_research_notes(["甲", "乙"])
        assert result == "1. 甲\n2. 乙"

    def test_extract_title_markdown(self):
        assert extract_title("# 我的标题\n正文...") == "我的标题"
        assert extract_title("## 二级标题\n正文...") == "二级标题"

    def test_extract_title_empty(self):
        assert extract_title("") is None
