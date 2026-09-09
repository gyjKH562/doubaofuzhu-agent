import re

# ========== 修改这里！填入你要检查的目标文件路径，例如 reuse_snippets.py ==========
file_path = "reuse_snippets.py"
# =============================================================================

src = open(file_path, encoding="utf-8").read()

# 遍历文件内所有唯一字符
for ch in set(src):
    # 条件：非ASCII，不是中文汉字，排除允许的中文标点
    if ord(ch) > 127 and not ('\u4e00' <= ch <= '\u9fff') and ch not in '，。：；（）——─═、':
        print(f'U+{ord(ch):04X} {ch!r}')