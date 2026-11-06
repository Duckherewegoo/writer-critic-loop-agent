# tests/conftest.py
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

class FakeChatModel(BaseChatModel):
    """真实的 BaseChatModel 子类，完美通过 Pydantic 校验与 LangChain 内部检查"""
    responses: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        content = self.responses.pop(0) if self.responses else ""
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def ainvoke(self, input, config=None, **kwargs):
        content = self.responses.pop(0) if self.responses else ""
        return AIMessage(content=content)

@pytest.fixture
def fake_llm_factory():
    """给测试提供构造 FakeChatModel 的工厂"""
    def _make(*contents: str) -> FakeChatModel:
        return FakeChatModel(responses=list(contents))
    return _make
