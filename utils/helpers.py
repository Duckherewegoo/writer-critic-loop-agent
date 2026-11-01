"""
辅助函数
提供各种实用的工具函数
"""

import json
import os
import re
from datetime import datetime, timezone


def format_research_notes(notes: list[str]) -> str:
    """
    格式化研究笔记为易读的字符串

    Args:
        notes: 研究笔记列表

    Returns:
        格式化后的字符串
    """
    if not notes:
        return "暂无研究笔记"

    formatted = []
    for i, note in enumerate(notes, 1):
        formatted.append(f"{i}. {note}")

    return "\n".join(formatted)


def count_words(text: str) -> int:
    """
    统计文本字数（中文按字符计算，英文按单词计算）

    Args:
        text: 输入文本

    Returns:
        字数
    """
    if not text:
        return 0

    # 简单的字数统计：中文字符 + 英文单词
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    english_words = len([word for word in text.split() if any(c.isalpha() for c in word)])

    return chinese_chars + english_words


def extract_title(content: str) -> str | None:
    """
    从文章内容中提取标题

    Args:
        content: 文章内容

    Returns:
        提取的标题，如果没有找到则返回None
    """
    if not content:
        return None

    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Markdown 标题：# ~ ######，统一剥掉井号前缀
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            return heading.group(1).strip()

        # 加粗标题：**xxx**
        if line.startswith('**') and line.endswith('**'):
            return line[2:-2].strip()

        # 无标记的长句兜底：文章首行可能是纯文本标题
        if len(line) < 100 and len(line) > 5:
            return line

    return None


def save_to_file(content: str, filepath: str, encoding: str = 'utf-8') -> None:
    """
    保存内容到文件

    Args:
        content: 要保存的内容
        filepath: 文件路径
        encoding: 文件编码
    """
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filepath, 'w', encoding=encoding) as f:
        f.write(content)


def load_from_file(filepath: str, encoding: str = 'utf-8') -> str:
    """
    从文件加载内容

    Args:
        filepath: 文件路径
        encoding: 文件编码

    Returns:
        文件内容
    """
    with open(filepath, encoding=encoding) as f:
        return f.read()


def save_state_to_json(state: dict, filepath: str) -> None:
    """
    保存状态到JSON文件

    Args:
        state: 状态字典
        filepath: 文件路径
    """
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    # 转换不可序列化的对象
    serializable_state = {}
    for key, value in state.items():
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            serializable_state[key] = value
        else:
            serializable_state[key] = str(value)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(serializable_state, f, ensure_ascii=False, indent=2)


def get_timestamp() -> str:
    """
    获取当前 UTC 时间戳字符串，格式 YYYYmmdd_HHMMSS。

    使用 UTC 避免服务器时区差异导致文件名不一致；
    展示层如需本地时间，请自行转换。

    Returns:
        UTC 时间戳字符串
    """
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def ensure_directory(dirpath: str) -> None:
    """
    确保目录存在

    Args:
        dirpath: 目录路径
    """
    os.makedirs(dirpath, exist_ok=True)
