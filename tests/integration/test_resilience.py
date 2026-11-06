import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.writer import WriterAgent
from agents.base_agent import AgentState

@pytest.mark.asyncio
async def test_writer_handles_empty_research_notes():
    """灵魂测试：研究专家啥也没搜到，Writer 能不能不崩"""
    mock_llm = MagicMock()
    writer = WriterAgent(llm=mock_llm)
    # 拦截底层的真实 LLM 调用
    writer._call_llm = AsyncMock(return_value="我是兜底写出来的文章")

    state = AgentState(
        topic="测试空素材",
        research_notes=[],  # 空素材！
        draft_content="",
        review_feedback="",
        iteration_count=0,
        max_iterations=3,
        metadata={}
    )
    
    result_state = await writer.run(state)
    
    assert result_state.draft_content == "我是兜底写出来的文章"
    assert writer._call_llm.called
