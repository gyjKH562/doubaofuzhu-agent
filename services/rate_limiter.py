"""
rate_limiter.py —— 轻量限流器（固定窗口计数）

为什么不用第三方库：YAGNI。原型阶段一个内存计数器足够，
生产环境再换 Redis 分布式限流或网关限流（记入技术债）。
"""
import time
from collections import defaultdict


class FixedWindowLimiter:
    """固定窗口限流器：每个 key 在时间窗口内最多允许 N 次请求。

    算法：记录 key 的 (窗口起点, 已用次数)。
    请求到来时，若已超出窗口则重置窗口，否则计数 +1，超限拒绝。
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        """初始化限流器。

        参数：
            max_requests: 窗口内最多允许的请求数
            window_seconds: 窗口时长（秒）
        """
        self.max_requests = max_requests          # 窗口内上限
        self.window_seconds = window_seconds      # 窗口时长
        # key -> [窗口起点, 窗口内已用次数]；defaultdict 保证不存在的 key 自动建默认值
        self._records: dict[str, list] = defaultdict(lambda: [0.0, 0])

    def allow(self, key: str) -> bool:
        """判断 key 是否允许通过；允许则计数 +1，超限返回 False。

        参数：
            key: 限流维度（如客户端 IP）
        返回：
            True = 放行（已计入本次请求）；False = 拒绝
        """
        now = time.monotonic()                     # 单调时钟：不受系统改时间影响
        record = self._records[key]                # 取出该 key 的记录
        if now - record[0] >= self.window_seconds: # 已超出窗口：重置起点和计数
            record[0] = now
            record[1] = 0
        record[1] += 1                             # 本次请求计数 +1
        return record[1] <= self.max_requests      # 未超限才放行
