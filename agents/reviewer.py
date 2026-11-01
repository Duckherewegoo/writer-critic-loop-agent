"""
审核智能体
负责审核文章草稿，提供修改意见和建议
"""

import re

from langchain_core.language_models import BaseChatModel

from .base_agent import AgentState, BaseAgent


class ReviewerAgent(BaseAgent):
    """
    审核智能体
    负责审核文章草稿，从多个维度进行评估并提供修改建议
    """

    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "审核专家",
        description: str = "专业的编辑和审稿人，擅长发现文章中的问题并提供改进建议",
        system_prompt: str | None = None,
    ):
        """
        初始化审核智能体

        Args:
            llm: 语言模型实例
            name: 智能体名称
            description: 智能体描述
            system_prompt: 系统提示词
        """
        default_prompt = """你是一位资深的编辑和审稿专家，拥有敏锐的洞察力和专业的评判标准。
你的任务是对文章进行全面的审核，发现其中的问题并提供具体的改进建议。

请从以下维度进行审核：
1. 内容质量：信息是否准确、观点是否清晰、论证是否充分
2. 结构逻辑：结构是否合理、逻辑是否严密、过渡是否自然
3. 语言表达：用词是否准确、句子是否通顺、是否有语法错误
4. 风格一致性：整体风格是否统一、是否符合目标读者
5. 创新性：是否有独特的见解和分析
6. 可读性：是否易于理解、阅读体验如何

请提供具体、可操作的修改建议，不要泛泛而谈。
如果文章质量很好，也请指出优点并说明可以直接通过。"""

        super().__init__(
            llm=llm,
            name=name,
            description=description,
            system_prompt=system_prompt or default_prompt,
        )

    async def run(self, state: AgentState) -> AgentState:
        """
        执行审核任务

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        review_prompt = f"""请审核以下关于"{state.topic}"的文章：

文章内容：
{state.draft_content}

请从以下维度进行全面审核：
1. 内容质量（准确性、深度、完整性）
2. 结构逻辑（结构、逻辑、过渡）
3. 语言表达（用词、语法、流畅度）
4. 风格一致性
5. 创新性
6. 可读性

请给出：
- 总体评价（优秀/良好/一般/需要修改）
- 具体的优点（至少3点）
- 具体的改进建议（至少3点，要具体可操作）

最后一行必须单独输出以下格式之一，不要加其他内容：
NEEDS_REVISION: YES
NEEDS_REVISION: NO"""

        context = {
            "当前迭代次数": state.iteration_count,
            "最大迭代次数": state.max_iterations,
            "文章字数": len(state.draft_content),
        }

        messages = self._build_messages(review_prompt, context)
        response = await self._call_llm(messages)

        needs_revision = self._needs_revision(response)

        state.review_feedback = response
        state.metadata["reviewer_agent_output"] = response
        state.metadata["needs_revision"] = needs_revision

        if needs_revision and state.iteration_count < state.max_iterations:
            state.current_step = "write"
        else:
            state.current_step = "edit"

        return state

    def _needs_revision(self, review_response: str) -> bool:
        """解析审核回复中的 NEEDS_REVISION 标记。

        标记解析失败时返回 True：宁可多重写一次，也不放过有问题的文章；
        外层有 max_iterations 上限兜底，不会无限循环。
        """
        match = re.search(
            r"NEEDS_REVISION\s*[:：]\s*(YES|NO)",
            review_response,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).upper() == "YES"
        return True
