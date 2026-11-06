import pytest
from agents.reviewer import ReviewerAgent
from unittest.mock import MagicMock

@pytest.fixture
def reviewer():
    # 单测解析逻辑，不需要真的 LLM
    return ReviewerAgent(llm=MagicMock())

def test_needs_revision_regex_parse(reviewer):
    """测试标准格式解析"""
    assert reviewer._needs_revision("写得不错。\nNEEDS_REVISION: NO") is False
    assert reviewer._needs_revision("太烂了。\nNEEDS_REVISION: YES") is True
    # 测试中英文冒号混用
    assert reviewer._needs_revision("还行\nNEEDS_REVISION：NO") is False

def test_needs_revision_fallback_on_malformed(reviewer):
    """灵魂测试：如果 LLM 抽风没输出标记，必须兜底返回 True（宁可重写，不能漏错）"""
    assert reviewer._needs_revision("我觉得这篇文章写得还可以，不用改了。") is True
    assert reviewer._needs_revision("") is True
