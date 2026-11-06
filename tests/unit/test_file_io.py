import json
import os
import re
from datetime import datetime

import pytest

from utils.helpers import (
    count_words,
    ensure_directory,
    extract_title,
    format_research_notes,
    get_timestamp,
    load_from_file,
    save_state_to_json,
    save_to_file,
)

# ============ 文本统计与解析 (补充现有 test_core 的边界) ============

def test_count_words_only_punctuation():
    """边界测试：全是标点符号，字数应该是 0"""
    assert count_words("，。！？、；：") == 0

def test_extract_title_fallback_to_long_sentence():
    """边界测试：没有 Markdown 标记，回退取第一行纯文本（长度 5~100）"""
    content = "这是文章的第一句话\n接下来的正文内容..."
    assert extract_title(content) == "这是文章的第一句话"

def test_extract_title_ignores_too_short_or_too_long():
    """边界测试：第一行太短 (<5) 或太长 (>100) 都不能被当成标题"""
    # 太短
    assert extract_title("短句\n正文") != "短句"
    # 太长 (101 个字符)
    assert extract_title("A" * 101 + "\n正文") is None


# ============ 文件基础读写 ============

def test_save_and_load_file(tmp_path):
    """功能测试：保存与读取文件，验证内容一致性"""
    filepath = str(tmp_path / "test.txt")
    content = "这是一段中文测试内容。\n换行也要保留。"
    
    save_to_file(content, filepath)
    loaded = load_from_file(filepath)
    
    assert loaded == content

def test_save_to_file_creates_parent_dirs(tmp_path):
    """边界测试：保存到多级不存在的目录时，应自动创建目录"""
    filepath = str(tmp_path / "level1" / "level2" / "test.txt")
    # 目录 currently 不存在
    assert not os.path.exists(os.path.dirname(filepath))
    
    save_to_file("content", filepath)
    
    # 目录被创建了，且文件写入了
    assert os.path.exists(filepath)


# ============ 状态 JSON 序列化 ============

def test_save_state_to_json_normal(tmp_path):
    """功能测试：正常字典能正确序列化落盘"""
    filepath = str(tmp_path / "state.json")
    state = {"topic": "测试", "iteration": 1, "is_done": False}
    
    save_state_to_json(state, filepath)
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["topic"] == "测试"
    assert data["iteration"] == 1
    assert data["is_done"] is False

def test_save_state_to_json_fallback_for_unserializable(tmp_path):
    """灵魂测试：遇到不可序列化的对象（如 lambda, 自定义类），必须降级为字符串，不能崩"""
    filepath = str(tmp_path / "state.json")
    
    class UnserializableObj:
        def __str__(self):
            return "我是不可序列化的对象"

    state = {
        "normal_key": "ok",
        "bad_obj": UnserializableObj(),
        "another_bad": lambda x: x,
    }
    
    save_state_to_json(state, filepath)
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["normal_key"] == "ok"
    # 断言不可序列化对象被 str() 兜底转成了字符串
    assert data["bad_obj"] == "我是不可序列化的对象"
    assert "lambda" in data["another_bad"]


# ============ 目录与时间戳 ============

def test_ensure_directory(tmp_path):
    """功能测试：确保目录创建（即使已存在也不报错）"""
    target_dir = str(tmp_path / "new_dir" / "sub_dir")
    
    # 首次创建
    ensure_directory(target_dir)
    assert os.path.isdir(target_dir)
    
    # 二次调用不抛异常
    ensure_directory(target_dir)

def test_get_timestamp_format():
    """功能测试：时间戳格式必须是 YYYYmmdd_HHMMSS"""
    ts = get_timestamp()
    # 用正则校验格式：8位数字_6位数字
    assert re.match(r"^\d{8}_\d{6}$", ts)
    
    # 验证年份大致靠谱（比如今年）
    current_year = str(datetime.now().year)
    assert ts.startswith(current_year)
