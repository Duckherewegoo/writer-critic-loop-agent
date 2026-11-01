from typing import Any, TypedDict


class WorkflowState(TypedDict):
    """工作流状态类型"""
    topic: str
    research_notes: list[str]
    draft_content: str
    review_feedback: str
    final_content: str
    current_step: str  # 预留：UI 进度展示；当前无消费方
    iteration_count: int
    max_iterations: int  # 初始值；循环是否继续以 WorkflowConfig.max_iterations 为准
    metadata: dict[str, Any]
