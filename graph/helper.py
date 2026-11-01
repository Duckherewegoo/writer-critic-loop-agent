from agents.base_agent import AgentState

from .state import WorkflowState


def state_to_agent_state(state: WorkflowState) -> AgentState:
    """将 WorkflowState 复制为 AgentState。

    字段一一对应；缺失字段用 AgentState 的默认值兜底。
    """
    return AgentState(
        topic=state.get("topic", ""),
        research_notes=state.get("research_notes", []),
        draft_content=state.get("draft_content", ""),
        review_feedback=state.get("review_feedback", ""),
        final_content=state.get("final_content", ""),
        current_step=state.get("current_step", "research"),
        iteration_count=state.get("iteration_count", 0),
        max_iterations=state.get("max_iterations", 3),
        metadata=state.get("metadata", {}),
    )


def agent_state_to_state(agent_state: AgentState, state: WorkflowState) -> WorkflowState:
    """将 AgentState 回写为 WorkflowState（全量覆盖）。

    全量覆盖意味着：agent 未显式保留的字段会退化为 AgentState 的默认值。
    子类必须用 `state.model_copy(update={...})` 构造返回，不能裸建
    `AgentState(draft_content=...)`——后者会把 research_notes 等字段冲成默认值。
    """
    return {
        **state,
        "topic": agent_state.topic,
        "research_notes": agent_state.research_notes,
        "draft_content": agent_state.draft_content,
        "review_feedback": agent_state.review_feedback,
        "final_content": agent_state.final_content,
        "current_step": agent_state.current_step,
        "iteration_count": agent_state.iteration_count,
        "max_iterations": agent_state.max_iterations,
        "metadata": agent_state.metadata,
    }


__all__ = ["agent_state_to_state", "state_to_agent_state"]
