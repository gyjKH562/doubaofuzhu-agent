"""
tests/test_markdown_service.py —— 文本规范化单元测试

测试对象：normalize_markdown（公众号用）/ normalize_plain（小红书用）。
纯函数测试的套路：准备输入 → 调用 → 断言输出（没有数据库、没有 mock）。

关键设计断言（第 12 步修正）：
    # 开头在小红书是【话题标签】不是标题——
    normalize_plain 绝不能给 # 开头补空行。
"""
from services.markdown_service import normalize_markdown, normalize_plain  # 被测函数


# ==================== normalize_markdown（公众号：完整规则） ====================

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


# ==================== normalize_plain（小红书：只清洗） ====================

def test_plain去掉行尾空白():
    """清洗规则 1 对小红书同样生效。"""
    text = "正文   \n下一行\t"
    assert normalize_plain(text) == "正文\n下一行"


def test_plain压缩连续空行():
    """清洗规则 2 对小红书同样生效（小红书靠空行分段，空行泛滥要压缩）。"""
    text = "第一段\n\n\n\n第二段"
    assert normalize_plain(text) == "第一段\n\n第二段"


def test_plain不把话题标签当标题():
    """关键断言：# 开头在小红书是话题标签，绝不能补空行。

    这是第 12 步的设计修正——把小红书也走 Markdown 规则，
    会把 #学习打卡 当成标题处理（语义错误）。
    """
    text = "今天的分享\n#学习打卡 #效率工具"     # 文末话题标签（紧跟正文）
    assert normalize_plain(text) == "今天的分享\n#学习打卡 #效率工具"  # 原样保留


def test_plain幂等():
    """清洗幂等：重复处理结果不变。"""
    text = "正文  \n\n\n#话题\n"
    once = normalize_plain(text)
    assert normalize_plain(once) == once
