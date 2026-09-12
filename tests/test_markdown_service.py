"""
tests/test_markdown_service.py —— Markdown 排版规范化单元测试

测试对象：markdown_service.normalize_markdown（纯函数，无副作用）。
纯函数测试的套路：准备输入 → 调用 → 断言输出（没有数据库、没有 mock）。
"""
from services.markdown_service import normalize_markdown  # 被测函数


def test_去掉行尾空白():
    """规则 1：每行行尾的空格/制表符应被删除。"""
    text = "第一行   \n第二行\t\n第三行"      # 行尾有空格和制表符
    result = normalize_markdown(text)
    assert result == "第一行\n第二行\n第三行"  # 行尾空白全部消失


def test_压缩连续空行():
    """规则 2：连续多个空行应压缩成一个。"""
    text = "标题\n\n\n\n正文"                  # 标题后 3 个空行
    result = normalize_markdown(text)
    assert result == "标题\n\n正文"            # 只剩 1 个空行


def test_标题前自动补空行():
    """规则 3：标题（# 开头）前无空行时，应自动插入空行。"""
    text = "段落一\n# 一级标题\n段落二"          # 标题前没有空行
    result = normalize_markdown(text)
    assert result == "段落一\n\n# 一级标题\n段落二"  # 标题前多了空行


def test_标题前已有空行则不重复插入():
    """规则 3 的幂等性：标题前已有空行，不应再插入（重复调用结果不变）。"""
    text = "段落一\n\n# 一级标题\n段落二"       # 已经规范
    once = normalize_markdown(text)
    twice = normalize_markdown(once)            # 再处理一遍
    assert twice == once                        # 幂等：结果不变


def test_空串输入返回空串():
    """边界：空串输入不应崩溃，返回空串。"""
    assert normalize_markdown("") == ""
