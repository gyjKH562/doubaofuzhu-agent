"""
markdown_service.py —— Markdown 排版规范化（纯后端文本处理）

职责：把大模型输出的"毛坯文本"整理成规范 Markdown。

为什么是纯函数：
    1. 无副作用（不碰数据库/网络/文件）——同输入永远同输出
    2. 确定性 → 最好测（对比测试直接翻译成断言）
    3. 可复用 → 任何项目的文本清洗都能直接拿去用

三条规则（每条对应一个可测行为）：
    1. 每行去掉行尾空白（模型输出常见残留空格）
    2. 连续多个空行压缩成一个空行（模型输出常见空行泛滥）
    3. 标题（# 开头）前必须有空行（Markdown 渲染规范：
       标题前无空行可能导致部分渲染器解析异常）
"""
from __future__ import annotations  # 类型注解兼容（字符串形式注解）

def normalize_markdown(text: str) -> str:
    """把毛坯文本整理成规范 Markdown，返回规范化后的文本。

    参数：
        text: 原始文本（可能含行尾空格、连续空行、标题前无空行）
    返回：
        规范化后的文本
    保证：
        空串输入 → 空串输出（不崩，测试用例之一）
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

    # ③ 标题前补空行：
    #    从第 2 行开始检查（索引 1），因为标题不可能是开头（开头前面没东西）
    #    条件：当前是标题行（# 开头）且 前一行不是空行
    #    → 在标题前插入一个空行
    i = 1
    while i < len(result):
        if result[i].startswith("#") and result[i - 1] != "":
            result.insert(i, "")  # 插入空行（列表变长，i 位置现在是空行）
            i += 1                # 跳过刚插入的空行（下次检查它后面的行）
        i += 1

    # ④ 组装回文本：行之间用 \n 连接，末尾去掉多余换行（strip）
    #    join 结果再 strip：保证输出不以空行开头/结尾（格式干净）
    return "\n".join(result).strip()
