"""
项目冒烟测试。

分两组：

1. 纯函数测试（默认执行，毫秒级，不联网）
   - _parse_research_notes     研究笔记解析
   - _needs_revision           审核结论解析
   - should_continue_writing   循环终止条件
   - state ↔ agent_state 转换   字段不丢失
   - iteration_count 语义      research 不加、writer 加

2. 联机 smoke test（默认跳过）
   - RUN_ONLINE=1 且配置 OPENAI_API_KEY + OPENAI_BASE_URL 时执行
   - 只验证凭证与端点可达，不测业务

用法：
    python test.py                      # 纯函数组
    RUN_ONLINE=1 python test.py         # 纯函数组 + 联机组
    pytest test.py -v                   # pytest 方式

前置：本文件假设已应用以下修复
    - reviewer._needs_revision 改为解析 NEEDS_REVISION: YES/NO，签名去掉 state 参数
    - research.run 不再修改 iteration_count
    - writer.run 末尾 iteration_count += 1，反馈注入条件为 bool(review_feedback)
    - workflow 提供 create_initial_state，nodes 提供 build_workflow_nodes
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from agents.base_agent import AgentState
from agents.research import ResearchAgent
from agents.reviewer import ReviewerAgent
from agents.writer import WriterAgent
from graph.helper import agent_state_to_state, state_to_agent_state
from graph.state import WorkflowState


# ============ 测试夹具 ============

def _fake_llm(*contents: str) -> BaseChatModel:
    """构造按顺序返回固定内容的假 LLM，不联网。"""
    llm = MagicMock(spec=BaseChatModel)
    queue = list(contents)

    async def ainvoke(*args: Any, **kwargs: Any) -> AIMessage:
        return AIMessage(content=queue.pop(0) if queue else "")

    llm.ainvoke = ainvoke
    return llm


def _agent_state(**overrides: Any) -> AgentState:
    defaults: dict[str, Any] = {
        "topic": "测试主题",
        "research_notes": [],
        "draft_content": "",
        "review_feedback": "",
        "final_content": "",
        "current_step": "research",
        "iteration_count": 0,
        "max_iterations": 3,
        "metadata": {},
    }
    defaults.update(overrides)
    return AgentState(**defaults)


def _workflow_state(**overrides: Any) -> WorkflowState:
    state: WorkflowState = {
        "topic": "测试主题",
        "research_notes": [],
        "draft_content": "",
        "review_feedback": "",
        "final_content": "",
        "current_step": "research",
        "iteration_count": 0,
        "max_iterations": 3,
        "metadata": {},
    }
    state.update(overrides)
    return state


def _route(max_iterations: int = 3):
    """从 build_workflow_nodes 取出条件边函数，模拟 LangGraph 的路由调用。"""
    from graph.config import WorkflowConfig
    from graph.nodes import build_workflow_nodes

    config = WorkflowConfig(llm=_fake_llm(), max_iterations=max_iterations)
    return build_workflow_nodes(config)["route"]


# ============ 纯函数：研究笔记解析 ============

def test_parse_research_notes_mixed_formats():
    agent = ResearchAgent(llm=_fake_llm())
    notes = agent._parse_research_notes("1. 第一条\n2. 第二条\n- 符号项\n* 星号项\n• 圆点项")
    assert notes == ["第一条", "第二条", "符号项", "星号项", "圆点项"]


def test_parse_research_notes_multi_digit():
    agent = ResearchAgent(llm=_fake_llm())
    notes = agent._parse_research_notes("12. 两位编号\n100. 三位编号")
    assert notes == ["两位编号", "三位编号"]


def test_parse_research_notes_falls_back_to_whole_text():
    agent = ResearchAgent(llm=_fake_llm())
    raw = "这里是一段没有列表格式的长内容，长度足够触发长行兜底。"
    notes = agent._parse_research_notes(raw)
    assert notes == [raw]


# ============ 纯函数：审核结论解析 ============

def test_needs_revision_yes():
    agent = ReviewerAgent(llm=_fake_llm())
    assert agent._needs_revision("优点很多...\n改进建议...\nNEEDS_REVISION: YES") is True


def test_needs_revision_no():
    agent = ReviewerAgent(llm=_fake_llm())
    assert agent._needs_revision("文章很好...\nNEEDS_REVISION: NO") is False


def test_needs_revision_case_and_format():
    agent = ReviewerAgent(llm=_fake_llm())
    assert agent._needs_revision("needs_revision: yes") is True
    assert agent._needs_revision("Needs_Revision：No") is False  # 全角冒号


def test_needs_revision_fallback_is_true():
    """解析失败时保守返回 True，由 max_iterations 兜底。"""
    agent = ReviewerAgent(llm=_fake_llm())
    assert agent._needs_revision("完全没有任何标记") is True


# ============ 纯函数：循环终止条件 ============

def test_route_continue_when_needs_revision_and_below_max():
    route = _route(max_iterations=3)
    state = _workflow_state(iteration_count=1, metadata={"needs_revision": True})
    assert route(state) == "write"


def test_route_stop_when_reached_max():
    route = _route(max_iterations=3)
    state = _workflow_state(iteration_count=3, metadata={"needs_revision": True})
    assert route(state) == "edit"


def test_route_stop_when_no_revision_needed():
    route = _route(max_iterations=3)
    state = _workflow_state(iteration_count=1, metadata={"needs_revision": False})
    assert route(state) == "edit"


# ============ 迭代计数语义 ============

def test_research_does_not_increment_iteration():
    agent = ResearchAgent(llm=_fake_llm("1. a\n2. b"))
    out = asyncio.run(agent.run(_agent_state(iteration_count=0)))
    assert out.iteration_count == 0
    assert out.research_notes == ["a", "b"]


def test_writer_increments_iteration():
    agent = WriterAgent(llm=_fake_llm("draft content"))
    out = asyncio.run(agent.run(_agent_state(iteration_count=0)))
    assert out.iteration_count == 1
    assert out.draft_content == "draft content"


def test_writer_injects_feedback_regardless_of_iteration():
    """反馈注入不依赖 iteration_count，只要有反馈就必须传给 LLM。"""
    captured: dict[str, str] = {}

    def fake_ainvoke(messages, **kwargs):
        captured["system"] = messages[0].content
        return AIMessage(content="改稿")

    llm = MagicMock(spec=BaseChatModel)
    llm.ainvoke = fake_ainvoke

    agent = WriterAgent(llm=llm)
    asyncio.run(agent.run(_agent_state(iteration_count=0, review_feedback="请加强论证")))
    assert "请加强论证" in captured["system"]


# ============ 状态转换 ============

def test_state_roundtrip_preserves_all_fields():
    original = _workflow_state(
        research_notes=["a", "b"],
        draft_content="draft",
        review_feedback="fb",
        iteration_count=2,
        metadata={"needs_revision": True},
    )
    back = agent_state_to_state(state_to_agent_state(original), original)
    for key, value in original.items():
        assert back[key] == value, f"字段 {key} 在往返中丢失"


def test_agent_state_partial_update_does_not_drop_other_fields():
    """子类应使用 model_copy(update=...) 局部更新，不得裸建 AgentState。"""
    original = _workflow_state(research_notes=["a", "b"], iteration_count=1)
    agent_state = state_to_agent_state(original)
    agent_state = agent_state.model_copy(update={"draft_content": "x"})
    back = agent_state_to_state(agent_state, original)
    assert back["research_notes"] == ["a", "b"]
    assert back["draft_content"] == "x"


# ============ 联机 smoke test ============

@pytest.mark.skipif(
    os.getenv("RUN_ONLINE") != "1",
    reason="需要 RUN_ONLINE=1 且配置 OPENAI_API_KEY / OPENAI_BASE_URL 才执行",
)
def test_online_llm_roundtrip():
    """验证凭证和端点可达；不覆盖业务逻辑。"""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    assert api_key, "OPENAI_API_KEY / DASHSCOPE_API_KEY 未配置"
    assert base_url, "OPENAI_BASE_URL 未配置"

    llm = ChatOpenAI(
        model=os.getenv("SMOKE_MODEL", "qwen-plus"),
        api_key=api_key,
        base_url=base_url,
        timeout=30,
    )
    res = llm.invoke("请回复两个字：收到")
    assert res.content


if __name__ == "__main__":
    load_dotenv()
    # 显式指定文件：pytest 默认只收集 test_*.py / *_test.py，test.py 不会被自动收集
    sys.exit(pytest.main([__file__, "-v"]))
