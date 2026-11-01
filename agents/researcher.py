"""
研究智能体
负责收集信息、进行研究，为写作提供素材和参考
"""

import re

from langchain_core.language_models import BaseChatModel

from .base_agent import AgentState, BaseAgent


class ResearchAgent(BaseAgent):
    """
    研究智能体
    负责对给定主题进行深入研究，收集相关信息和素材
    """

    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "研究专家",
        description: str = "专业的研究人员，擅长收集信息、整理资料、进行深度分析",
        system_prompt: str | None = None,
    ):
        """
        初始化研究智能体

        Args:
            llm: 语言模型实例
            name: 智能体名称
            description: 智能体描述
            system_prompt: 系统提示词
        """
        default_prompt = """你是一位资深的研究专家，拥有丰富的信息收集和分析能力。
你的任务是对给定的主题进行深入研究，收集相关的信息、数据和观点。

请遵循以下原则：
1. 全面性：尽可能收集多方面的信息，不要遗漏重要角度
2. 准确性：确保信息的准确性和可靠性
3. 结构化：将收集到的信息整理成清晰的结构
4. 深度：不仅停留在表面，要进行深入分析
5. 实用性：提供的信息要对后续写作有实际帮助

请以列表形式输出你的研究发现，每条笔记包含一个关键点。"""

        super().__init__(
            llm=llm,
            name=name,
            description=description,
            system_prompt=system_prompt or default_prompt,
        )

    async def run(self, state: AgentState) -> AgentState:
        """
        执行研究任务

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        research_prompt = f"""请对以下主题进行深入研究：

主题：{state.topic}

请提供至少10条有价值的研究笔记，涵盖以下方面：
1. 主题的背景和基本概念
2. 最新的发展和趋势
3. 关键数据和统计信息
4. 不同的观点和争议
5. 实际应用案例
6. 未来发展方向

请确保每条笔记都是具体、有价值的信息，不要泛泛而谈。"""

        context = {
            "当前迭代次数": state.iteration_count,
            "已有的研究笔记数量": len(state.research_notes),
        }

        messages = self._build_messages(research_prompt, context)
        response = await self._call_llm(messages)

        research_notes = self._parse_research_notes(response)

        state.research_notes.extend(research_notes)
        state.current_step = "write"
        state.metadata["research_agent_output"] = response

        return state

    def _parse_research_notes(self, response: str) -> list[str]:
        """
        解析研究笔记

        Args:
            response: LLM回复

        Returns:
            研究笔记列表
        """
        notes = []
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 数字列表：1. / 1、 / 1) 前缀，支持两位以上编号
            match = re.match(r"^\d+[.、)]\s*(.+)$", line)
            if match:
                notes.append(match.group(1).strip())
                continue

            # 符号列表：- / * / •
            if line.startswith(("-", "*", "•")):
                note = line[1:].strip()
                if note:
                    notes.append(note)
                continue

            # 兜底：长行视为一条笔记，避免丢失非列表格式的有效内容
            if len(line) > 20:
                notes.append(line)

        # 如果没有解析出笔记，就把整个回复作为一条笔记
        if not notes:
            notes.append(response.strip())

        return notes
