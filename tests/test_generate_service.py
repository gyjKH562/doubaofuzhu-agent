"""
tests/test_generate_service.py —— 模型输出解析函数的单元测试

测试对象：generate_service.parse_generated（把大模型返回的原始文本
按分隔符拆成"公众号 + 小红书"两段）。

为什么单独测它：这是全项目"最容易坏"的代码——上游模型不保证按格式输出，
解析逻辑的正确性直接决定写进数据库的内容是否完整。用测试把
"各种畸形输入"都钉死，模型再抽风我们也能第一时间发现。
"""
import pytest  # 测试框架

from services.generate_service import SEP_GZH, SEP_XHS, parse_generated  # 被测函数 + 分隔符常量
from services.exceptions import ModelOutputError  # 解析失败抛的领域异常


def test_正常解析出两段内容():
    """正常路径：模型按约定输出 → 正确拆成两段。"""
    text = f"{SEP_GZH}\n公众号正文\n{SEP_XHS}\n小红书笔记"  # 模拟模型原始输出
    gzh, xhs = parse_generated(text)
    assert gzh == "公众号正文"    # 公众号段正确取出
    assert xhs == "小红书笔记"    # 小红书段正确取出


def test_缺少公众号分隔符时报错():
    """边界：模型完全没按格式输出 → 必须明确失败（不能静默接受）。"""
    with pytest.raises(ModelOutputError):  # 期望抛领域异常
        parse_generated("一段没有任何分隔符的废话")


def test_公众号内容为空时报错():
    """边界：分隔符在，但公众号段是空的 → 视为解析失败。"""
    text = f"{SEP_GZH}\n\n{SEP_XHS}\n小红书内容"  # 公众号段只有空白
    with pytest.raises(ModelOutputError):
        parse_generated(text)


def test_缺少小红书分隔符时小红书为空串():
    """容错路径：小红书段缺失 → 公众号保留，小红书兜底为空串。"""
    text = f"{SEP_GZH}\n只有公众号内容"  # 没有小红书分隔符
    gzh, xhs = parse_generated(text)
    assert gzh == "只有公众号内容"  # 公众号正常
    assert xhs == ""                # 小红书为空（现有设计的兜底行为）
