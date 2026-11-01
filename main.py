"""
多智能体协作写作系统 - 主程序
提供Gradio Web界面，用户可以输入主题，系统自动完成研究、写作、审核、编辑全流程
"""

import asyncio
import json
import logging
import os
import time
from typing import Any

import gradio as gr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from graph.workflow import WorkflowConfig, create_initial_state, create_workflow
from utils.helpers import (
    count_words,
    ensure_directory,
    extract_title,
    format_research_notes,
    get_timestamp,
    save_to_file,
)

# 启动时加载 .env，仅作为默认配置来源；运行时不再写进程级环境变量。
load_dotenv()

logger = logging.getLogger(__name__)


class MultiAgentWritingSystem:
    """
    多智能体协作写作系统
    整合研究、写作、审核、编辑四个智能体，完成完整的写作流程
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.llm = self._init_llm()
        self.workflow = self._init_workflow()
        self.output_dir = self.config.get("output_dir", "outputs")
        ensure_directory(self.output_dir)

    def _init_llm(self) -> ChatOpenAI:
        llm_config = self.config.get("llm", {})
        model = llm_config.get("model", "qwen-plus")
        temperature = llm_config.get("temperature", 0.7)
        api_key = llm_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = llm_config.get("base_url") or os.getenv("OPENAI_BASE_URL")

        kwargs = {
            "model": model,
            "temperature": temperature,
        }

        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url

        return ChatOpenAI(**kwargs)

    def _init_workflow(self):
        # 图在构造时编译一次；低并发场景无需缓存，高并发可按配置加缓存。
        workflow_config = WorkflowConfig(
            llm=self.llm,
            max_iterations=self.config.get("max_iterations", 3),
            researcher_config=self.config.get("researcher"),
            writer_config=self.config.get("writer"),
            reviewer_config=self.config.get("reviewer"),
            editor_config=self.config.get("editor"),
        )
        return create_workflow(workflow_config)

    async def run_writing_task(self, topic: str) -> dict[str, Any]:
        """运行写作任务；max_iterations 由构造配置决定，避免双来源。"""
        initial_state = create_initial_state(
            topic=topic,
            max_iterations=self.config.get("max_iterations", 3),
        )

        final_state = await self.workflow.ainvoke(initial_state)

        # 文件 IO 是同步操作，丢线程池避免阻塞事件循环。
        await asyncio.to_thread(self._save_result, final_state)

        return {
            "topic": topic,
            "final_content": final_state.get("final_content", ""),
            "draft_content": final_state.get("draft_content", ""),
            "research_notes": final_state.get("research_notes", []),
            "review_feedback": final_state.get("review_feedback", ""),
            "iteration_count": final_state.get("iteration_count", 0),
            "metadata": final_state.get("metadata", {}),
        }

    def _save_result(self, state: dict[str, Any]) -> None:
        """保存最终文章与完整状态到 output_dir。"""
        topic = state.get("topic", "untitled")
        timestamp = get_timestamp()

        # 文件名带上 topic 便于人工检索；截断并过滤非法字符。
        final_content = state.get("final_content", "")
        if final_content:
            safe_topic = "".join(c for c in topic if c.isalnum() or c in " -_")[:20].strip()
            filename = f"final_{safe_topic}_{timestamp}.md"
            filepath = os.path.join(self.output_dir, filename)
            save_to_file(final_content, filepath)

        # 保存完整状态；非 JSON 原生类型转 str 兜底，防止序列化失败。
        state_filename = f"state_{timestamp}.json"
        state_filepath = os.path.join(self.output_dir, state_filename)

        serializable_state = {}
        for key, value in state.items():
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                serializable_state[key] = value
            else:
                serializable_state[key] = str(value)

        with open(state_filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_state, f, ensure_ascii=False, indent=2)


def create_gradio_interface(system: MultiAgentWritingSystem):
    """创建Gradio界面"""

    async def generate_article(
        topic: str,
        model: str,
        temperature: float,
        max_iterations: int,
        api_key: str,
        base_url: str,
    ):
        if not topic.strip():
            raise gr.Error("请输入写作主题")

        start_time = time.perf_counter()

        # 每次请求用独立实例，凭证只进本次配置，不写进程级 os.environ。
        # 未填写时回退到 .env 中的默认值，由 _init_llm 负责。
        temp_config = {
            "llm": {
                "model": model,
                "temperature": temperature,
                "api_key": api_key or None,
                "base_url": base_url or None,
            },
            "max_iterations": max_iterations,
            "output_dir": system.output_dir
        }

        try:
            local_system = MultiAgentWritingSystem(temp_config)
            result = await local_system.run_writing_task(topic=topic)

            # 格式化输出
            research_notes_str = format_research_notes(result["research_notes"])
            word_count = count_words(result["final_content"])
            title = extract_title(result["final_content"]) or topic

            elapsed_time = time.perf_counter() - start_time
            info_str = (
                f"**标题**：{title}  \n"
                f"**字数**：{word_count} 字  \n"
                f"**迭代次数**：{result['iteration_count']} 次  \n"
                f"**耗时**：{elapsed_time:.2f} 秒"
            )

            return (
                result["final_content"],
                research_notes_str,
                result["review_feedback"],
                info_str,
            )

        except Exception:
            logger.exception("写作任务失败")
            elapsed_time = time.perf_counter() - start_time
            # 耗时信息帮助用户区分“超时”还是“逻辑错误”。
            raise gr.Error(f"生成失败 (耗时 {elapsed_time:.2f}s)")

    # 创建界面
    with gr.Blocks(title="多智能体协作写作系统") as demo:
        gr.Markdown(
            """
            # 🤖 多智能体协作写作系统

            基于 LangGraph + LangChain + Gradio 构建的多智能体协作写作平台。
            系统包含**研究专家**、**写作专家**、**审核专家**、**总编辑**四个智能体，
            自动完成从资料收集到最终润色的完整写作流程。
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ 配置")

                topic_input = gr.Textbox(
                    label="写作主题",
                    placeholder="请输入你想写的主题，例如：人工智能的未来发展",
                    lines=3,
                )

                with gr.Accordion("高级设置", open=False):
                    model_select = gr.Dropdown(
                        label="模型",
                        choices=[
                            "qwen-turbo",
                            "qwen-plus",
                            "qwen-max",
                            "qwen-long",
                        ],
                        value="qwen-turbo",
                        allow_custom_value=True,
                    )

                    temperature_slider = gr.Slider(
                        label="创造性 (Temperature)",
                        minimum=0.0,
                        maximum=1.0,
                        value=0.7,
                        step=0.1,
                    )

                    max_iterations_slider = gr.Slider(
                        label="最大迭代次数",
                        minimum=1,
                        maximum=5,
                        value=3,
                        step=1,
                    )

                    api_key_input = gr.Textbox(
                        label="API Key",
                        type="password",
                        placeholder="sk-...",
                    )

                    base_url_input = gr.Textbox(
                        label="API Base URL",
                        placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    )

                generate_btn = gr.Button(
                    "🚀 开始写作",
                    variant="primary",
                    size="lg",
                )

            with gr.Column(scale=2):
                gr.Markdown("### 📝 输出结果")

                with gr.Tabs():
                    with gr.Tab("最终文章"):
                        final_output = gr.Markdown(
                            label="最终文章",
                            value="*点击「开始写作」按钮生成文章*",
                        )

                    with gr.Tab("研究笔记"):
                        research_output = gr.Markdown(
                            label="研究笔记",
                            value="*研究笔记将显示在这里*",
                        )

                    with gr.Tab("审核反馈"):
                        review_output = gr.Markdown(
                            label="审核反馈",
                            value="*审核反馈将显示在这里*",
                        )

                info_output = gr.Markdown(
                    label="统计信息",
                    value="",
                )

        # 示例
        gr.Examples(
            examples=[
                ["人工智能对未来教育的影响", "qwen-turbo", 0.7, 3, "", ""],
                ["远程工作的优缺点分析", "qwen-turbo", 0.6, 2, "", ""],
                ["如何培养良好的阅读习惯", "qwen-turbo", 0.8, 3, "", ""],
            ],
            inputs=[
                topic_input,
                model_select,
                temperature_slider,
                max_iterations_slider,
                api_key_input,
                base_url_input,
            ],
        )

        # 绑定事件
        generate_btn.click(
            fn=generate_article,
            inputs=[
                topic_input,
                model_select,
                temperature_slider,
                max_iterations_slider,
                api_key_input,
                base_url_input,
            ],
            outputs=[
                final_output,
                research_output,
                review_output,
                info_output,
            ],
        )

    return demo


def main():
    system = MultiAgentWritingSystem()
    demo = create_gradio_interface(system)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        debug=False,
        show_error=True
    )


if __name__ == "__main__":
    main()
