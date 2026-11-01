"""
核心纯函数单元测试（不联网、秒级、可回归）

覆盖系统"判断力"的三个关键函数，以及状态转换的往返一致性。
这些测试是防止 P0 级 bug（死循环 / 反馈不注入 / 审核失效）复发的保险。
"""

from unittest.mock import MagicMock

from agents.base_agent import AgentState
from agents.researcher import ResearchAgent
from agents.reviewer import ReviewerAgent
from graph.helper import (
    agent_state_to_state,
    create_initial_state,
    state_to_agent_state,
)
from graph.nodes import should_continue_writing
from utils.helpers import count_words, extract_title, format_research_notes

# _needs_revision / _parse_research_notes 不依赖真实 LLM，用 mock 即可
_FAKE_LLM = MagicMock()


# ---------------------------------------------------------------------------
# ReviewerAgent._needs_revision —— 决定循环走向的核心判断
# ---------------------------------------------------------------------------
class TestNeedsRevision:
    def _make_state(self, iteration_count: int = 1, max_iterations: int = 3) -> AgentState:
        return AgentState(
            topic="测试主题",
            iteration_count=iteration_count,
            max_iterations=max_iterations,
        )

    def test_parses_structured_yes(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "总体评价：一般\n具体建议：...\n\nNEEDS_REVISION: YES"
        assert reviewer._needs_revision(response, self._make_state()) is True

    def test_parses_structured_no(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "总体评价：优秀\n优点：...\n\nNEEDS_REVISION: NO"
        assert reviewer._needs_revision(response, self._make_state()) is False

    def test_structured_marker_is_case_and_space_tolerant(self):
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        assert reviewer._needs_revision("needs_revision:   yes", self._make_state()) is True
        assert reviewer._needs_revision("  NEEDS_REVISION:\tNO ", self._make_state()) is False

    def test_positive_words_do_not_override_explicit_yes(self):
        """
        回归测试：旧实现先匹配正面关键词（"优秀"/"很好"），
        会把同时含优点与修改要求的审核意见误判为通过。
        结构化标记必须优先于关键词。
        """
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "优点：优秀、很好、质量很高。\n建议：需要修改第三段。\nNEEDS_REVISION: YES"
        assert reviewer._needs_revision(response, self._make_state()) is True

    def test_fallback_when_marker_missing(self):
        """
        无结构化标记时的兜底契约：未达上限则保守重写，已达上限则放行。
        """
        reviewer = ReviewerAgent(llm=_FAKE_LLM)
        response = "这是一段没有结构化标记的审核意见。"
        assert reviewer._needs_revision(response, self._make_state(iteration_count=1)) is True
        assert reviewer._needs_revision(response, self._make_state(iteration_count=3)) is False


# ---------------------------------------------------------------------------
# ResearchAgent._parse_research_notes —— LLM 输出解析
# ---------------------------------------------------------------------------
class TestParseResearchNotes:
    def setup_method(self):
        self.agent = ResearchAgent(llm=_FAKE_LLM)

    def test_numbered_list(self):
        text = "1. 第一点内容\n2. 第二点内容\n3. 第三点内容"
        assert self.agent._parse_research_notes(text) == [
            "第一点内容",
            "第二点内容",
            "第三点内容",
        ]

    def test_bullet_list(self):
        text = "- 甲观点\n* 乙观点\n• 丙观点"
        assert self.agent._parse_research_notes(text) == ["甲观点", "乙观点", "丙观点"]

    def test_mixed_formats(self):
        text = "1. 数字项\n- 符号项\n\n普通长段落内容超过二十个字符用于兜底测试。"
        notes = self.agent._parse_research_notes(text)
        assert "数字项" in notes
        assert "符号项" in notes

    def test_plain_text_fallback(self):
        """完全没有列表标记时，整段作为一条笔记，不能返回空列表。"""
        text = "这是一段没有任何列表标记的纯文本内容"
        notes = self.agent._parse_research_notes(text)
        assert len(notes) == 1
        assert "纯文本" in notes[0]

    def test_empty_input_returns_fallback_not_crash(self):
        notes = self.agent._parse_research_notes("")
        assert isinstance(notes, list)


# ---------------------------------------------------------------------------
# should_continue_writing —— 条件边路由（死循环的最后一道防线）
# ---------------------------------------------------------------------------
class TestShouldContinueWriting:
    def _state(self, needs_revision: bool, iteration_count: int, max_iterations: int = 3):
        """
        同时写入 metadata 与顶层字段，兼容两种字段位置实现。
        （若你将 needs_revision 提升为 WorkflowState 顶层字段，此构造仍有效。）
        """
        state = create_initial_state("测试主题", max_iterations=max_iterations)
        state["iteration_count"] = iteration_count
        state["metadata"] = {"needs_revision": needs_revision}
        state["needs_revision"] = needs_revision  # type: ignore[typeddict-unknown-key]
        return state

    def test_needs_revision_and_under_limit_goes_write(self):
        assert should_continue_writing(self._state(True, 1)) == "write"

    def test_needs_revision_but_at_limit_goes_edit(self):
        """
        回归测试：达到 max_iterations 必须强制进入 edit，
        否则 iteration_count 不递增时会造成无限循环。
        """
        assert should_continue_writing(self._state(True, 3)) == "edit"

    def test_needs_revision_over_limit_goes_edit(self):
        assert should_continue_writing(self._state(True, 5)) == "edit"

    def test_no_revision_goes_edit(self):
        assert should_continue_writing(self._state(False, 1)) == "edit"

    def test_missing_metadata_defaults_to_edit(self):
        """metadata 缺 needs_revision 时默认 False → edit，不能崩。"""
        state = create_initial_state("测试主题")
        state["iteration_count"] = 1
        assert should_continue_writing(state) == "edit"


# ---------------------------------------------------------------------------
# 状态转换：WorkflowState ↔ AgentState 往返不丢字段
# ---------------------------------------------------------------------------
class TestStateRoundTrip:
    def test_initial_state_shape(self):
        state = create_initial_state("主题", max_iterations=4)
        assert state["topic"] == "主题"
        assert state["max_iterations"] == 4
        assert state["iteration_count"] == 0
        assert state["research_notes"] == []
        assert state["metadata"] == {}

    def test_round_trip_preserves_all_fields(self):
        state = create_initial_state("主题", max_iterations=3)
        state["research_notes"] = ["笔记A", "笔记B"]
        state["draft_content"] = "草稿"
        state["review_feedback"] = "反馈"
        state["iteration_count"] = 2
        state["metadata"] = {"needs_revision": True}

        agent_state = state_to_agent_state(state)
        restored = agent_state_to_state(agent_state, state)

        for key in (
            "topic",
            "research_notes",
            "draft_content",
            "review_feedback",
            "final_content",
            "iteration_count",
            "max_iterations",
            "metadata",
        ):
            assert restored[key] == state[key], f"字段 {key} 在往返中丢失或被篡改"

    def test_agent_state_to_state_returns_new_dict(self):
        """不得原地污染原始 state。"""
        state = create_initial_state("主题")
        agent_state = state_to_agent_state(state)
        restored = agent_state_to_state(agent_state, state)
        assert restored is not state


# ---------------------------------------------------------------------------
# utils.helpers —— 展示层工具函数
# ---------------------------------------------------------------------------
class TestUtilsHelpers:
    def test_count_words_mixed(self):
        # 4 个中文字符 + 2 个英文词（"AI" / "ML"）
        assert count_words("人工智能 AI 与 ML") == 6
        assert count_words("") == 0

    def test_format_research_notes_empty(self):
        assert format_research_notes([]) == "暂无研究笔记"

    def test_format_research_notes_numbered(self):
        result = format_research_notes(["甲", "乙"])
        assert result == "1. 甲\n2. 乙"

    def test_extract_title_markdown(self):
        assert extract_title("# 我的标题\n正文...") == "我的标题"
        assert extract_title("## 二级标题\n正文...") == "二级标题"

    def test_extract_title_bold(self):
        assert extract_title("**加粗标题**\n正文...") == "加粗标题"

    def test_extract_title_empty(self):
        assert extract_title("") is None
