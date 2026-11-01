"""工作流节点定义。

通过 build_workflow_nodes(config) 工厂创建节点，将 WorkflowConfig 闭包注入执行层，
避免模块级单例导致 main.py 的 UI 参数（model / temperature / api_key）失效，
也避免 import 时读 WorkflowConfig 类属性直接崩。
"""

from __future__ import annotations

import typing

from agents.editor import EditorAgent
from agents.researcher import ResearchAgent
from agents.reviewer import ReviewerAgent
from agents.writer import WriterAgent

from .config import WorkflowConfig
from .helper import agent_state_to_state as _agent_state_to_state
from .helper import state_to_agent_state as _state_to_agent_state
from .state import WorkflowState

if typing.TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    NodeFn = Callable[[WorkflowState], Awaitable[WorkflowState]]
    RouteFn = Callable[[WorkflowState], str]


def build_workflow_nodes(config: WorkflowConfig) -> dict[str, typing.Any]:
    """按配置构造节点函数。

    四个 agent 用 config.llm 与各自的 *_config 构造，UI 参数由此流到执行层；
    review 节点每次完成后 iteration_count +1，should_continue_writing 据此判断。
    """
    researcher = ResearchAgent(llm=config.llm, **(config.researcher_config or {}))
    writer = WriterAgent(llm=config.llm, **(config.writer_config or {}))
    reviewer = ReviewerAgent(llm=config.llm, **(config.reviewer_config or {}))
    editor = EditorAgent(llm=config.llm, **(config.editor_config or {}))

    async def research_node(state: WorkflowState) -> WorkflowState:
        agent_state = _state_to_agent_state(state)
        result = await researcher.run(agent_state)
        return _agent_state_to_state(result, state)

    async def write_node(state: WorkflowState) -> WorkflowState:
        agent_state = _state_to_agent_state(state)
        result = await writer.run(agent_state)
        return _agent_state_to_state(result, state)

    async def review_node(state: WorkflowState) -> WorkflowState:
        agent_state = _state_to_agent_state(state)
        result = await reviewer.run(agent_state)
        new_state = _agent_state_to_state(result, state)
        # 每完成一次 review 视为一轮迭代；显式 +1 防止 helper 未处理时死循环。
        new_state["iteration_count"] = state.get("iteration_count", 0) + 1
        return new_state

    async def edit_node(state: WorkflowState) -> WorkflowState:
        agent_state = _state_to_agent_state(state)
        result = await editor.run(agent_state)
        return _agent_state_to_state(result, state)

    def should_continue_writing(state: WorkflowState) -> str:
        """审核后决定继续写作还是进入编辑。

        终止条件以 config.max_iterations 为准（唯一权威源）；
        needs_revision 从 metadata 读，由 reviewer agent 写入。
        """
        needs_revision = state.get("metadata", {}).get("needs_revision", False)
        iteration_count = state.get("iteration_count", 0)
        if needs_revision and iteration_count < config.max_iterations:
            return "write"
        return "edit"

    return {
        "research": research_node,
        "write": write_node,
        "review": review_node,
        "edit": edit_node,
        "route": should_continue_writing,
    }


__all__ = ["build_workflow_nodes"]
