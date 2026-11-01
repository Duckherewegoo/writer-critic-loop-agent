"""工作流定义
使用LangGraph构建多智能体协作写作工作流
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .config import WorkflowConfig
from .nodes import build_workflow_nodes
from .state import WorkflowState


def create_initial_state(
    topic: str,
    *,
    max_iterations: int = 3,
) -> WorkflowState:
    """构造工作流初始状态。

    max_iterations 只是 TypedDict 字段兜底；循环是否继续以 WorkflowConfig.max_iterations 为准。

    需要注入中间状态做测试时，直接构造 dict 传给 workflow.invoke，或对调用方
    （如 MultiAgentWritingSystem.run_writing_task）monkeypatch，不走本函数参数。
    """
    return {
        "topic": topic,
        "research_notes": [],
        "draft_content": "",
        "review_feedback": "",
        "final_content": "",
        "current_step": "research",
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "metadata": {},
    }


def create_workflow(config: WorkflowConfig):
    """创建多智能体协作写作工作流。

    config 通过 build_workflow_nodes 闭包注入到每个节点，
    确保 WorkflowConfig.llm / max_iterations 真正流到执行层。
    """
    workflow = StateGraph(WorkflowState)
    nodes = build_workflow_nodes(config)

    workflow.add_node("research", nodes["research"])
    workflow.add_node("write", nodes["write"])
    workflow.add_node("review", nodes["review"])
    workflow.add_node("edit", nodes["edit"])

    workflow.set_entry_point("research")

    workflow.add_edge("research", "write")
    workflow.add_edge("write", "review")

    workflow.add_conditional_edges(
        "review",
        nodes["route"],
        {
            "write": "write",
            "edit": "edit",
        },
    )

    workflow.add_edge("edit", END)

    return workflow.compile()


__all__ = ["create_initial_state", "create_workflow"]
