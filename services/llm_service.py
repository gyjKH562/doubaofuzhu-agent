"""
llm_service.py —— 大模型调用服务（DeepSeek，OpenAI 兼容协议，SDK 版）

使用 OpenAI 官方 SDK 的异步客户端（AsyncOpenAI）调用 DeepSeek。

与手写 aiohttp 版对比，各层代码去哪了：
    手写版自己做的                SDK 帮你做的
    ───────────────────────      ─────────────────────────
    拼 URL / headers / payload   create() 内部完成
    序列化 JSON / 解析 JSON      SDK 内部完成（response 对象）
    超时 ClientTimeout           timeout 参数（openai.Timeout）
    重试（手写版没有，记了债）    max_retries 参数（SDK 内置）
    错误分类 except               SDK 抛分类好的异常（见 call_llm）

    我们保留的（SDK 不提供）：
    配置分离、日志、LLMError 统一包装——上层接口只认识 LLMError
"""
import logging  # 日志
import os       # 读取环境变量

import openai   # OpenAI 官方 SDK（DeepSeek 兼容该协议）
from dotenv import load_dotenv  # 加载 .env（幂等，main.py 加载过也无妨）

load_dotenv()

logger = logging.getLogger(__name__)

# 配置从 .env 读取（配置分离：key 绝不硬编码进代码）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")  # API 密钥（敏感！）
# DeepSeek 官方两种 base_url 都兼容（/v1 仅为兼容 OpenAI 而设，无实际意义）
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 超时配置（秒）：connect=建立连接上限，total=整个请求上限
TIMEOUT_CONNECT = 10
TIMEOUT_TOTAL = 120
MAX_RETRIES = 2  # SDK 内置重试：网络抖动时自动重试次数（手写版没有，这里顺手补上）


class LLMError(Exception):
    """大模型调用失败的自定义异常。

    为什么自定义异常：让上层能精确捕获"大模型挂了"，
    而不是把所有异常都当 500 处理——错误分类的第一步。
    """


# 模块级客户端（单例）：AsyncOpenAI 内部有连接池，是"重对象"，创建一次反复用。
# 为什么懒加载：key 没配置时，import 本模块不应报错（test_llm.py 无 key 时
# 要靠 call_llm 的开局检查给出友好提示，而不是 import 阶段就崩）。
_client: "openai.AsyncOpenAI | None" = None


def get_client() -> openai.AsyncOpenAI:
    """懒加载获取 AsyncOpenAI 单例客户端（第一次调用才真正创建）。"""
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            # 超时和重试都交给 SDK 配置——这就是手写版那几十行代码的去向
            # 注意：openai 3.x 底层是 httpx2，Timeout 要么给一个默认值、要么四个参数全设。
            # 写法：默认整体 120s（TIMEOUT_TOTAL），连接阶段单独收紧到 10s（TIMEOUT_CONNECT）
            timeout=openai.Timeout(TIMEOUT_TOTAL, connect=TIMEOUT_CONNECT),
            max_retries=MAX_RETRIES,
        )
    return _client


async def call_llm(messages: list[dict], max_tokens: int = 2000) -> str:
    """调用大模型，返回回复文本。

    参数：
        messages: OpenAI 格式的消息列表，如 [{"role": "user", "content": "你好"}]
        max_tokens: 最大生成 token 数（成本与响应时长的第一道闸门）
    返回：
        模型回复的文本内容
    异常：
        LLMError: 未配置 key / 超时 / 网络错误 / 认证失败 / 接口错误 / 空内容
    """
    # 第 0 步：开局校验——key 没配就不用发请求了（fail fast，与手写版一致）
    if not DEEPSEEK_API_KEY:
        logger.error("未配置 DEEPSEEK_API_KEY")
        raise LLMError("未配置 DEEPSEEK_API_KEY，请在 .env 中填写")

    logger.info("调用大模型：model=%s messages=%d条 max_tokens=%d",
                DEEPSEEK_MODEL, len(messages), max_tokens)

    try:
        # 一行完成手写版"拼请求 + 发送 + 状态检查 + 解析"的全部工作
        resp = await get_client().chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )
    except openai.AuthenticationError as e:
        # 401：key 无效（SDK 已按状态码分类好，直接对应手写版"非 2xx"分支）
        logger.error("大模型认证失败（API key 无效）：%s", e)
        raise LLMError("大模型接口返回 401（API key 无效）") from None
    except openai.APITimeoutError:
        # 超时：注意必须先于 APIConnectionError（它是后者的子类，顺序反了会被接住）
        logger.error("大模型调用超时（连接 %ds / 总 %ds）", TIMEOUT_CONNECT, TIMEOUT_TOTAL)
        raise LLMError("大模型调用超时，请稍后重试") from None
    except openai.APIConnectionError as e:
        # 网络层错误（DNS 失败、连接被拒等）——和超时区分开
        logger.error("大模型网络错误：%s", e)
        raise LLMError("网络错误，无法连接大模型服务") from None
    except openai.APIStatusError as e:
        # 其他非 2xx（429 限流、500 服务端错误等），SDK 已重试过仍失败才到这
        logger.error("大模型接口错误（状态码 %s）：%s", e.status_code, e)
        raise LLMError(f"大模型接口返回 {e.status_code}") from None
    except openai.APIError as e:
        # 兜底：SDK 内部其他错误
        logger.error("大模型 SDK 调用错误：%s", e)
        raise LLMError("大模型调用失败") from None

    # 取结果：SDK 已把 JSON 解析成对象，属性访问即可（手写版是字典下标）
    content = resp.choices[0].message.content
    if not content:
        # 某些思考模型 content 可能为空，只有 reasoning_content——如实记录
        logger.error("大模型返回空内容：%s", resp)
        raise LLMError("大模型返回空内容")

    logger.info("大模型调用成功，返回 %d 字符", len(content))
    return content
