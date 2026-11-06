"""
项目冒烟测试与核心语义验证。
包含纯函数测试（毫秒级、不联网）与可选的联机测试。
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
from langchain_core.outputs import ChatResult, ChatGeneration

from agents.base_agent import AgentState
from agents.researcher import ResearchAgent
from agents.reviewer import ReviewerAgent
from agents.writer import WriterAgent
from graph.config import WorkflowConfig
from graph.nodes import build_workflow_nodes
from graph.state import WorkflowState


# ============ 真实的假模型类 (替代 MagicMock) ============

class FakeChatModel(BaseChatModel):
    """真实的 BaseChatModel 子类，完美通过 Pydantic 校验与 LangChain 内部检查"""
    responses: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        content = self.responses.pop(0) if self.responses else ""
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def ainvoke(self, input, config=None, **kwargs):
        content = self.responses.pop(0) if self.responses else ""
        return AIMessage(content=content)


def _fake_llm(*contents: str) -> FakeChatModel:
    """构造按顺序返回固定内容的假 LLM"""
    return FakeChatModel(responses=list(contents))


# ============ 测试夹具 ============

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
    config = WorkflowConfig(llm=_fake_llm(), max_iterations=max_iterations)
    return build_workflow_nodes(config)["route"]


# ============ 纯函数：审核结论解析 ============

def test_needs_revision_yes():
    agent = ReviewerAgent(llm=_fake_llm())
    assert agent._needs_revision("优点很多...\n改进建议...\nNEEDS_REVISION: YES") is True


def test_needs_revision_no():
    agent = ReviewerAgent(llm=_fake_llm())
    assert agent._needs_revision("文章很好...\nNEEDS_REVISION: NO") is False


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

    class SpyChatModel(FakeChatModel):
        async def ainvoke(self, input, config=None, **kwargs):
            # 修复：input 是一个消息列表，审核反馈在 HumanMessage (索引 1) 里
            # 为了严谨，我们把所有的消息内容拼起来，确保不会漏掉
            captured["all_messages"] = " ".join([msg.content for msg in input])
            return AIMessage(content="改稿")

    llm = SpyChatModel()
    agent = WriterAgent(llm=llm)
    asyncio.run(agent.run(_agent_state(iteration_count=0, review_feedback="请加强论证")))
    
    # 断言反馈确实被拼到了发给大模型的文本里
    assert "请加强论证" in captured["all_messages"]


# ============ 联机 smoke test ============

@pytest.mark.skipif(
    os.getenv("RUN_ONLINE") != "1",
    reason="需要 RUN_ONLINE=1 且配置 OPENAI_API_KEY / OPENAI_BASE_URL 才执行",
)
def test_online_llm_roundtrip():
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
    sys.exit(pytest.main([__file__, "-v"]))
