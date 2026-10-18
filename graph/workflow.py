"""
工作流定义
使用LangGraph构建多智能体协作写作工作流
"""

from langgraph.graph import END, StateGraph

from .config import WorkflowConfig
from .nodes import (
    edit_node,
    research_node,
    review_node,
    should_continue_writing,
    write_node,
)
from .state import WorkflowState


def create_workflow(config: WorkflowConfig):
    """
    创建多智能体协作写作工作流

    Args:
        config: 工作流配置

    Returns:
        编译后的LangGraph工作流
    """
   
    # 创建状态图
    workflow = StateGraph(WorkflowState)

    # 添加节点
    workflow.add_node("research", research_node)
    workflow.add_node("write", write_node)
    workflow.add_node("review", review_node)
    workflow.add_node("edit", edit_node)

    # 设置入口点
    workflow.set_entry_point("research")

    # 添加边
    workflow.add_edge("research", "write")
    workflow.add_edge("write", "review")

    # 添加条件边（审核后决定是继续修改还是进入编辑）
    workflow.add_conditional_edges(
        "review",
        should_continue_writing,
        {
            "write": "write",
            "edit": "edit",
        },
    )

    workflow.add_edge("edit", END)

    # 编译工作流
    compiled_workflow = workflow.compile()

    return compiled_workflow

__all__ = ["create_workflow"]
