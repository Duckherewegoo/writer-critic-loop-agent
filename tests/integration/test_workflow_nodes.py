import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from graph.nodes import build_workflow_nodes
from graph.config import WorkflowConfig
from graph.state import WorkflowState

@pytest.fixture
def mock_config(fake_llm_factory):
    # 直接使用 conftest.py 里的 fake_llm_factory
    return WorkflowConfig(
        llm=fake_llm_factory(),
        max_iterations=3,
    )

@pytest.fixture
def nodes_and_mocks(mock_config):
    with patch("graph.nodes.ResearchAgent"), \
         patch("graph.nodes.WriterAgent") as MockWri, \
         patch("graph.nodes.ReviewerAgent"), \
         patch("graph.nodes.EditorAgent"):
        
        mock_writer = MockWri.return_value
        mock_writer.run = AsyncMock()
        
        nodes = build_workflow_nodes(mock_config)
        yield nodes, mock_writer

@pytest.mark.asyncio
async def test_writer_receives_critique_feedback(nodes_and_mocks):
    """灵魂测试 1：验证 Writer 确实接收到了 Reviewer 的反馈"""
    nodes, mock_writer = nodes_and_mocks
    write_node = nodes["write"]
    
    state: WorkflowState = {
        "topic": "AI测试",
        "review_feedback": "第二段逻辑不通，请修改。",
        "iteration_count": 1,
        "max_iterations": 3,
        "metadata": {},
        "draft_content": "",
        "research_notes": [],
        "final_content": "",
        "current_step": "write"
    }
    
    mock_writer.run.return_value = MagicMock()
    
    await write_node(state)
    
    called_state = mock_writer.run.call_args[0][0]
    assert "第二段逻辑不通" in called_state.review_feedback

def test_should_continue_writing_router(nodes_and_mocks):
    """灵魂测试 2：死循环熔断（路由逻辑）"""
    nodes, _ = nodes_and_mocks
    route = nodes["route"]
    
    assert route({"metadata": {"needs_revision": True}, "iteration_count": 1}) == "write"
    assert route({"metadata": {"needs_revision": True}, "iteration_count": 3}) == "edit"
    assert route({"metadata": {"needs_revision": False}, "iteration_count": 1}) == "edit"
