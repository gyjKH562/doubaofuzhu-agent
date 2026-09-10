"""
test_llm.py —— 手动验证大模型调用是否可用（非自动化测试）

用法：python scripts/test_llm.py
预期：
    没配 key  → 打印 "调用失败：未配置 DEEPSEEK_API_KEY..."
    配了 key  → 打印 "模型回复：..."
"""
import asyncio
import sys
from pathlib import Path

# 把项目根目录加进模块搜索路径（scripts/ 是子目录，直接 import 找不到 services）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.llm_service import LLMError, call_llm  # noqa: E402

async def main() -> None:
    """发一条最简单的消息，验证整个调用链路。"""
    messages = [{"role": "user", "content": "用一句话介绍你自己"}]
    try:
        reply = await call_llm(messages, max_tokens=200)
        print("模型回复：", reply)
    except LLMError as e:
        print("调用失败：", e)

if __name__ == "__main__":
    asyncio.run(main())