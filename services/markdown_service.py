"""
markdown_service.py —— 文本规范化（纯后端文本处理）

职责：把大模型输出的"毛坯文本"整理成规范格式。

为什么拆成两个函数（第 12 步的设计修正，感谢评审）：
    - 公众号文章（gzh_article）支持 Markdown 渲染
      → normalize_markdown：完整规则（清洗 + 标题前补空行）
    - 小红书笔记（xhs_note）是纯文本展示，# 开头是【话题标签】不是标题
      → normalize_plain：只做通用清洗（去行尾空白 + 压缩空行）
    ⚠ 不能一刀切：把话题标签当标题处理是语义错误。

为什么是纯函数：
    1. 无副作用（不碰数据库/网络/文件）——同输入永远同输出
    2. 确定性 → 最好测（对比测试直接翻译成断言）
    3. 可复用 → 任何项目的文本清洗都能直接拿去用

公共清洗规则（两条，两个函数共用）：
    1. 每行去掉行尾空白（模型输出常见残留空格）
    2. 连续多个空行压缩成一个空行（模型输出常见空行泛滥）
Markdown 专属规则（仅 normalize_markdown）：
    3. 标题（# 开头）前必须有空行（渲染规范；话题标签不受此规则影响）
"""
from __future__ import annotations  # 类型注解兼容（字符串形式注解）

def _clean_lines(text: str) -> list[str]:
    """内部工具：清洗原始文本为"干净的行列表"（规则 1 + 2）。

    不以下划线开头命名约定：_ 前缀 = 模块私有函数，只在本文件内部使用。
    拆出来的原因：两个公开函数共用同一套清洗逻辑（Rule of Three 的
    反面——出现 2 次就值得抽，因为逻辑完全一致且会一起演化）。
    """
    # ① 按行拆分，去掉每行行尾空白（rstrip 只删右边空白）
    #    split("\n") 保留空行结构；"a\n\n\nb" → ["a", "", "", "b"]
    lines = [line.rstrip() for line in text.split("\n")]

    # ② 压缩连续空行：
    #    遍历每行，如果"当前是空行 且 上一个已加入的结果也是空行"，跳过
    #    （第一个空行保留，从第二个空行开始跳过 = 连续空行只留一个）
    result: list[str] = []
    for line in lines:
        if line == "" and result and result[-1] == "":
            continue              # 连续空行：这个不加入
        result.append(line)       # 普通行 或 第一个空行：加入
    return result


def normalize_markdown(text: str) -> str:
    """公众号文章用：完整 Markdown 规范化（清洗 + 标题前补空行）。

    参数：
        text: 原始文本（可能含行尾空格、连续空行、标题前无空行）
    返回：
        规范化后的 Markdown 文本
    保证：
        空串输入 → 空串输出（不崩，测试用例之一）
    """
    result = _clean_lines(text)  # 公共清洗（规则 1 + 2）

    # ③ 标题前补空行（Markdown 专属规则）：
    #    从第 2 行开始检查（索引 1），标题不可能是开头（开头前面没东西）
    #    条件：当前是标题行（# 开头）且 前一行不是空行
    #    → 在标题前插入一个空行
    i = 1
    while i < len(result):
        if result[i].startswith("#") and result[i - 1] != "":
            result.insert(i, "")  # 插入空行（列表变长，i 位置现在是空行）
            i += 1                # 跳过刚插入的空行（下次检查它后面的行）
        i += 1

    # ④ 组装回文本：join 后 strip（输出不以空行开头/结尾）
    return "\n".join(result).strip()


def normalize_plain(text: str) -> str:
    """小红书笔记用：纯文本清洗（只做规则 1 + 2，不做标题规则）。

    为什么没有标题规则：小红书不渲染 Markdown，# 开头是【话题标签】
    （如 #学习打卡），不是标题——在它前面插空行是错误语义。

    参数：
        text: 原始文本
    返回：
        清洗后的纯文本（行尾无空白、无连续空行）
    """
    return "\n".join(_clean_lines(text)).strip()
