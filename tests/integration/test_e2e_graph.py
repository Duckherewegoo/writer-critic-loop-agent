import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from graph.workflow import create_workflow
from graph.state import WorkflowState

@pytest.fixture
def mock_agents():
    """Mock 掉底层的 4 个 Agent，直接返回我们想要的状态"""
    with patch("graph.nodes.ResearchAgent") as MockRes, \
         patch("graph.nodes.WriterAgent") as MockWri, \
         patch("graph.nodes.ReviewerAgent") as MockRev, \
         patch("graph.nodes.EditorAgent") as MockEdi:
        
        # 让 Mock 实例的 run 方法支持 await
        MockRes.return_value.run = AsyncMock()
        MockWri.return_value.run = AsyncMock()
        MockRev.return_value.run = AsyncMock()
        MockEdi.return_value.run = AsyncMock()
        
        yield {
            "res": MockRes.return_value,
            "wri": MockWri.return_value,
            "rev": MockRev.return_value,
            "edi": MockEdi.return_value,
        }

@pytest.mark.asyncio
async def test_graph_e2e_pass_on_first_try(mock_agents):
    """灵魂测试：一次通过评审，直接进总编，验证图的流转顺序"""
    # 1. 设定每个 Agent 的返回值 (直接修改传入的 AgentState)
    async def res_run(state):
        state.research_notes = ["笔记1", "笔记2"]
        return state
    async def wri_run(state):
        state.draft_content = "草稿"
        state.iteration_count += 1
        return state
    async def rev_run(state):
        state.review_feedback = "完美"
        state.metadata["needs_revision"] = False # 直接通过
        return state
    async def edi_run(state):
        state.final_content = "最终文章"
        return state

    mock_agents["res"].run.side_effect = res_run
    mock_agents["wri"].run.side_effect = wri_run
    mock_agents["rev"].run.side_effect = rev_run
    mock_agents["edi"].run.side_effect = edi_run

    # 2. 编译图
    config = MagicMock()
    config.max_iterations = 3
    graph = create_workflow(config)

    # 3. 初始状态
    initial_state = {
        "topic": "测试E2E",
        "research_notes": [],
        "draft_content": "",
        "review_feedback": "",
        "final_content": "",
        "iteration_count": 0,
        "max_iterations": 3,
        "metadata": {},
    }

    # 4. 运行整图
    final_state = await graph.ainvoke(initial_state)

    # 5. 验证：顺序流转，且编辑执行了
    assert final_state["final_content"] == "最终文章"
    assert mock_agents["edi"].run.called
    assert mock_agents["wri"].run.call_count == 1

@pytest.mark.asyncio
async def test_graph_e2e_hit_max_iterations(mock_agents):
    """灵魂测试：一直不通过，触发 max_iterations 熔断，直接踢给总编"""
    async def res_run(state):
        state.research_notes = ["笔记1"]
        return state
    async def wri_run(state):
        state.draft_content = "草稿"
        state.iteration_count += 1
        return state
    async def rev_run(state):
        state.review_feedback = "还要改"
        state.metadata["needs_revision"] = True # 永远不通过
        return state
    async def edi_run(state):
        state.final_content = "熔断后的最终文章"
        return state

    mock_agents["res"].run.side_effect = res_run
    mock_agents["wri"].run.side_effect = wri_run
    mock_agents["rev"].run.side_effect = rev_run
    mock_agents["edi"].run.side_effect = edi_run

    config = MagicMock()
    config.max_iterations = 3
    graph = create_workflow(config)

    initial_state = {"topic": "测试E2E", "research_notes": [], "draft_content": "", "review_feedback": "", "final_content": "", "iteration_count": 0, "max_iterations": 3, "metadata": {}}

    final_state = await graph.ainvoke(initial_state)

    # 验证：写了 3 次，最后被强制踢给编辑
    assert mock_agents["wri"].run.call_count == 3
    assert final_state["final_content"] == "熔断后的最终文章"
